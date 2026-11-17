import pytest

from app.telefone import normalizar


@pytest.mark.parametrize("entrada, esperado", [
    ("(11) 90000-0001", "5511900000001"),
    ("+55 11 90000-0001", "5511900000001"),
    ("5511900000001", "5511900000001"),
    ("011 90000-0001", "5511900000001"),
    ("11 8000-0001", "5511980000001"),          # celular antigo, sem o nono dígito
    ("(11) 3000-0001", "551130000001"),         # fixo
])
def test_formatos_aceitos(entrada, esperado):
    assert normalizar(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "123", "(10) 99999-0000", "11 1000-0001", "11 80000-0001", "1 11 90000-0001", None])
def test_formatos_recusados(entrada):
    assert normalizar(entrada) is None
