"""API HTTP do portão de envio."""
from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field

from app import portao

pool: ConnectionPool | None = None


@asynccontextmanager
async def ciclo(_app: FastAPI):
    global pool
    # autocommit: cada regra abre a própria transação com conn.transaction()
    pool = ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=10, kwargs={"autocommit": True}, open=True)
    with pool.connection() as conn:
        portao.criar_tabelas(conn)
    yield
    pool.close()


app = FastAPI(title="Portão de envio", lifespan=ciclo)


def autenticar(x_chave_api: str = Header(default="")) -> None:
    esperada = os.getenv("PORTAO_CHAVE", "")
    if not esperada:
        raise HTTPException(503, "PORTAO_CHAVE não configurada")
    if not hmac.compare_digest(x_chave_api.encode(), esperada.encode()):
        raise HTTPException(401, "chave inválida")


class Pedido(BaseModel):
    telefone: str = Field(examples=["(87) 99999-0000"])
    origem: str = Field(examples=["disparo", "followup", "ia"], max_length=40)
    chave: str = Field(description="Chave de idempotência da automação", min_length=8, max_length=200)


class Falha(BaseModel):
    erro: str = Field(max_length=500)


class Recusa(BaseModel):
    telefone: str
    motivo: str | None = Field(default=None, max_length=200)


@app.get("/saude")
def saude():
    return {"ok": True}


@app.post("/portao", dependencies=[Depends(autenticar)])
def pedir(p: Pedido):
    with pool.connection() as conn:
        try:
            d = portao.pedir_envio(conn, p.telefone, p.origem, p.chave)
        except portao.ChaveEmConflito:
            raise HTTPException(409, "chave já usada para outro telefone")
    return d.__dict__


@app.post("/portao/{reserva_id}/enviado", dependencies=[Depends(autenticar)])
def enviado(reserva_id: int):
    with pool.connection() as conn:
        if not portao.confirmar_envio(conn, reserva_id):
            raise HTTPException(409, "reserva inexistente ou já encerrada")
    return {"ok": True}


@app.post("/portao/{reserva_id}/falhou", dependencies=[Depends(autenticar)])
def falhou(reserva_id: int, f: Falha):
    with pool.connection() as conn:
        if not portao.registrar_falha(conn, reserva_id, f.erro):
            raise HTTPException(409, "reserva inexistente ou já encerrada")
    return {"ok": True}


@app.post("/recusas", dependencies=[Depends(autenticar)])
def recusar(r: Recusa):
    with pool.connection() as conn:
        tel = portao.registrar_recusa(conn, r.telefone, r.motivo)
    if tel is None:
        raise HTTPException(422, "telefone inválido")
    return {"telefone": tel}
