import os

import pytest
from fastapi.testclient import TestClient

if not os.getenv("DATABASE_URL"):
    pytest.skip("DATABASE_URL não definida", allow_module_level=True)

os.environ.setdefault("PORTAO_CHAVE", "chave-de-teste")

from app.main import app  # noqa: E402

H = {"X-Chave-Api": os.environ["PORTAO_CHAVE"]}


@pytest.fixture
def cliente(conn):
    with TestClient(app) as c:
        yield c


def test_sem_chave_recusa(cliente):
    assert cliente.post("/envios/autorizar", json={"telefone": "11900000001", "origem": "disparo", "chave": "abcdefgh"}).status_code == 401


def test_fluxo_completo(cliente):
    r = cliente.post("/envios/autorizar", headers=H, json={"telefone": "(11) 90000-0001", "origem": "disparo", "chave": "envio-0001"}).json()
    assert r["pode_enviar"]
    assert cliente.post(f"/envios/{r['reserva_id']}/confirmar", headers=H).status_code == 200
    r2 = cliente.post("/envios/autorizar", headers=H, json={"telefone": "11900000001", "origem": "ia", "chave": "envio-0002"}).json()
    assert not r2["pode_enviar"] and r2["motivo"] == "enviado_recentemente"


def test_recusa_pela_api(cliente):
    assert cliente.post("/contatos/recusas", headers=H, json={"telefone": "(11) 90000-0004"}).json() == {"telefone": "5511900000004"}
    r = cliente.post("/envios/autorizar", headers=H, json={"telefone": "11900000004", "origem": "followup", "chave": "envio-0003"}).json()
    assert r["motivo"] == "contato_recusou"
