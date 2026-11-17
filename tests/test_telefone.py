import pytest

from app.telefone import normalizar


@pytest.mark.parametrize("entrada, esperado", [
    ("(87) 99999-0000", "5587999990000"),
    ("+55 87 99999-0000", "5587999990000"),
    ("5587999990000", "5587999990000"),
    ("087 99999-0000", "5587999990000"),
    ("87 9999-0000", "5587999990000"),          # celular antigo, sem o nono dígito
    ("(87) 3861-0000", "558738610000"),         # fixo
])
def test_formatos_aceitos(entrada, esperado):
    assert normalizar(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "123", "(10) 99999-0000", "87 1999-0000", "87 89999-0000", "1 87 99999-0000", None])
def test_formatos_recusados(entrada):
    assert normalizar(entrada) is None
