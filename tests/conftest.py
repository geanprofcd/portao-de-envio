# Telefones usados nos testes são fictícios, só para validar formato e regras. O portão nunca envia mensagens.
import os

import psycopg
import pytest

from app import portao

URL = os.getenv("DATABASE_URL")


@pytest.fixture
def conn():
    if not URL:
        pytest.skip("DATABASE_URL não definida")
    c = psycopg.connect(URL, autocommit=True)
    portao.criar_tabelas(c)
    c.execute("truncate envios, recusas restart identity")
    yield c
    c.close()
