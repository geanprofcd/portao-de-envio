import os
import threading

import psycopg
import pytest

from app import portao

TEL = "(87) 99999-0000"


def test_primeiro_envio_e_liberado(conn):
    d = portao.pedir_envio(conn, TEL, "disparo", "disparo-1")
    assert d.pode_enviar and d.motivo == "liberado" and d.reserva_id


def test_segunda_automacao_e_barrada(conn):
    portao.pedir_envio(conn, TEL, "disparo", "disparo-1")
    d = portao.pedir_envio(conn, "+55 87 99999-0000", "followup", "followup-1")
    assert not d.pode_enviar and d.motivo == "enviado_recentemente"


def test_mesma_chave_repetida_devolve_a_mesma_reserva(conn):
    a = portao.pedir_envio(conn, TEL, "disparo", "disparo-1")
    b = portao.pedir_envio(conn, TEL, "disparo", "disparo-1")
    assert b.repetido and b.reserva_id == a.reserva_id and b.pode_enviar


def test_chave_reusada_para_outro_telefone_e_conflito(conn):
    portao.pedir_envio(conn, TEL, "disparo", "disparo-1")
    with pytest.raises(portao.ChaveEmConflito):
        portao.pedir_envio(conn, "(87) 98888-0000", "disparo", "disparo-1")


def test_falha_libera_nova_tentativa(conn):
    d = portao.pedir_envio(conn, TEL, "disparo", "disparo-1")
    assert portao.registrar_falha(conn, d.reserva_id, "erro do provedor")
    nova = portao.pedir_envio(conn, TEL, "disparo", "disparo-2")
    assert nova.pode_enviar


def test_confirmar_duas_vezes_nao_muda_nada(conn):
    d = portao.pedir_envio(conn, TEL, "disparo", "disparo-1")
    assert portao.confirmar_envio(conn, d.reserva_id)
    assert not portao.confirmar_envio(conn, d.reserva_id)
    assert not portao.registrar_falha(conn, d.reserva_id, "tarde demais")


def test_recusa_bloqueia_qualquer_origem(conn):
    portao.registrar_recusa(conn, "87 99999-0000", "pediu para parar")
    for origem in ("disparo", "followup", "ia"):
        d = portao.pedir_envio(conn, TEL, origem, f"{origem}-1")
        assert not d.pode_enviar and d.motivo == "contato_recusou"


def test_telefone_invalido(conn):
    d = portao.pedir_envio(conn, "123", "disparo", "disparo-1")
    assert not d.pode_enviar and d.motivo == "telefone_invalido"


def test_freio_apos_muitas_falhas(conn):
    for i in range(portao.FREIO_FALHAS):
        d = portao.pedir_envio(conn, f"(87) 9{i:04d}-0000", "disparo", f"lote-{i}")
        portao.registrar_falha(conn, d.reserva_id, "recusado pelo provedor")
    d = portao.pedir_envio(conn, "(87) 98888-1111", "disparo", "lote-final")
    assert not d.pode_enviar and d.motivo == "freio_ativo"


def _em_paralelo(qtd, alvo):
    resultados, barreira = [], threading.Barrier(qtd)

    def rodar(i):
        with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as c:
            barreira.wait()
            resultados.append(alvo(c, i))

    ts = [threading.Thread(target=rodar, args=(i,)) for i in range(qtd)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return resultados


def test_concorrencia_um_so_envio_por_telefone(conn):
    """20 automações pedem o mesmo telefone no mesmo instante, cada uma com sua chave: só uma passa."""
    r = _em_paralelo(20, lambda c, i: portao.pedir_envio(c, TEL, "disparo", f"corrida-{i}"))
    assert sum(d.pode_enviar for d in r) == 1
    assert conn.execute("select count(*) from envios").fetchone()[0] == 1


def test_concorrencia_mesma_chave_uma_so_reserva(conn):
    """A mesma chamada repetida 10 vezes ao mesmo tempo gera uma reserva só."""
    r = _em_paralelo(10, lambda c, i: portao.pedir_envio(c, TEL, "disparo", "mesma-chave"))
    assert len({d.reserva_id for d in r}) == 1
    assert conn.execute("select count(*) from envios").fetchone()[0] == 1
