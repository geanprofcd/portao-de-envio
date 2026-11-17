"""Regras do portão. Toda decisão roda numa transação com trava por telefone no PostgreSQL."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import psycopg

from app.telefone import normalizar

JANELA_HORAS = float(os.getenv("PORTAO_JANELA_HORAS", "24"))
FREIO_FALHAS = int(os.getenv("PORTAO_FREIO_FALHAS", "10"))
FREIO_MINUTOS = int(os.getenv("PORTAO_FREIO_MINUTOS", "10"))


@dataclass
class Decisao:
    pode_enviar: bool
    motivo: str
    reserva_id: int | None = None
    repetido: bool = False


class ChaveEmConflito(Exception):
    """A chave de idempotência já foi usada para outro telefone."""


def criar_tabelas(conn: psycopg.Connection) -> None:
    conn.execute((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def pedir_envio(conn: psycopg.Connection, telefone: str, origem: str, chave: str) -> Decisao:
    tel = normalizar(telefone)
    if tel is None:
        return Decisao(False, "telefone_invalido")
    with conn.transaction():
        # Duas automações pedindo o mesmo telefone ao mesmo tempo esperam uma pela outra aqui.
        conn.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (tel,))

        existente = conn.execute(
            "select id, telefone, status from envios where chave = %s", (chave,)
        ).fetchone()
        if existente:
            if existente[1] != tel:
                raise ChaveEmConflito(chave)
            return Decisao(existente[2] == "reservado", "repetido", existente[0], repetido=True)

        if conn.execute("select 1 from recusas where telefone = %s", (tel,)).fetchone():
            return Decisao(False, "contato_recusou")

        recente = conn.execute(
            """select 1 from envios
               where telefone = %s and status in ('reservado', 'enviado')
                 and criado_em > now() - make_interval(secs => %s)""",
            (tel, JANELA_HORAS * 3600),
        ).fetchone()
        if recente:
            return Decisao(False, "enviado_recentemente")

        falhas = conn.execute(
            """select count(*) from envios
               where status = 'falhou' and atualizado_em > now() - make_interval(mins => %s)""",
            (FREIO_MINUTOS,),
        ).fetchone()[0]
        if falhas >= FREIO_FALHAS:
            return Decisao(False, "freio_ativo")

        rid = conn.execute(
            "insert into envios (telefone, origem, chave, status) values (%s, %s, %s, 'reservado') returning id",
            (tel, origem, chave),
        ).fetchone()[0]
        return Decisao(True, "liberado", rid)


def _mudar_status(conn: psycopg.Connection, reserva_id: int, novo: str, erro: str | None = None) -> bool:
    with conn.transaction():
        linha = conn.execute(
            """update envios set status = %s, erro = %s, atualizado_em = now()
               where id = %s and status = 'reservado' returning id""",
            (novo, erro, reserva_id),
        ).fetchone()
    return linha is not None


def confirmar_envio(conn: psycopg.Connection, reserva_id: int) -> bool:
    return _mudar_status(conn, reserva_id, "enviado")


def registrar_falha(conn: psycopg.Connection, reserva_id: int, erro: str) -> bool:
    """A falha libera o telefone para uma nova tentativa e conta para o freio."""
    return _mudar_status(conn, reserva_id, "falhou", erro[:500])


def registrar_recusa(conn: psycopg.Connection, telefone: str, motivo: str | None = None) -> str | None:
    tel = normalizar(telefone)
    if tel is None:
        return None
    with conn.transaction():
        conn.execute(
            "insert into recusas (telefone, motivo) values (%s, %s) on conflict (telefone) do nothing",
            (tel, motivo),
        )
    return tel
