"""Normalização de telefones brasileiros para o formato 55 + DDD + número."""
from __future__ import annotations

import re


def normalizar(bruto: str) -> str | None:
    """Devolve o telefone como 55DDNNNNNNNNN (celular) ou 55DDNNNNNNNN (fixo), ou None se for inválido.

    Aceita espaços, parênteses, traços, o + inicial, o zero de operadora antes do DDD e celular
    antigo sem o nono dígito.
    """
    digitos = re.sub(r"\D", "", bruto or "")
    digitos = digitos.lstrip("0")
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    if not digitos.startswith("55") or len(digitos) not in (12, 13):
        return None
    ddd, numero = digitos[2:4], digitos[4:]
    if not ("11" <= ddd <= "99") or ddd[1] == "0":
        return None
    if len(numero) == 8 and numero[0] in "6789":
        numero = "9" + numero
    if len(numero) == 9 and numero[0] != "9":
        return None
    if len(numero) == 8 and numero[0] not in "2345":
        return None
    return "55" + ddd + numero
