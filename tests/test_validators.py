"""Testes de app/validators.py — casos válidos, inválidos e de limite."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.validators import (
    parse_bool_param,
    parse_date_param,
    parse_non_negative_int_param,
    parse_positive_int_param,
    validate_name_param,
)

# --- parse_date_param --------------------------------------------------


def test_parse_date_param_none_retorna_none():
    assert parse_date_param(None, "breach_date_from") is None


def test_parse_date_param_aceita_yyyy_mm_dd():
    assert parse_date_param("2019-12-31", "breach_date_from") == "2019-12-31"


@pytest.mark.parametrize(
    "valor",
    [
        "2019/12/31",  # separador errado
        "31-12-2019",  # ordem errada
        "2019-13-01",  # mês inválido
        "2021-02-30",  # dia inválido para fevereiro
        "2019-1-1",  # sem zero-padding
        "20191231",  # formato básico ISO, sem hífens
        "2019-12-31T00:00:00",  # datetime, não date
        "not-a-date",
    ],
)
def test_parse_date_param_invalido_levanta_400(valor):
    with pytest.raises(HTTPException) as exc_info:
        parse_date_param(valor, "breach_date_from")
    assert exc_info.value.status_code == 400


# --- parse_non_negative_int_param --------------------------------------


def test_parse_non_negative_int_param_none_retorna_none():
    assert parse_non_negative_int_param(None, "min_pwn_count") is None


def test_parse_non_negative_int_param_aceita_zero():
    assert parse_non_negative_int_param("0", "min_pwn_count") == 0


def test_parse_non_negative_int_param_aceita_inteiro_positivo():
    assert parse_non_negative_int_param("152445165", "min_pwn_count") == 152445165


@pytest.mark.parametrize("valor", ["-1", "abc", "1.5", ""])
def test_parse_non_negative_int_param_invalido_levanta_400(valor):
    with pytest.raises(HTTPException) as exc_info:
        parse_non_negative_int_param(valor, "min_pwn_count")
    assert exc_info.value.status_code == 400


# --- parse_bool_param ----------------------------------------------------


def test_parse_bool_param_none_retorna_none():
    assert parse_bool_param(None, "is_verified") is None


@pytest.mark.parametrize("valor", ["true", "True", "TRUE"])
def test_parse_bool_param_aceita_true(valor):
    assert parse_bool_param(valor, "is_verified") is True


@pytest.mark.parametrize("valor", ["false", "False", "FALSE"])
def test_parse_bool_param_aceita_false(valor):
    assert parse_bool_param(valor, "is_verified") is False


@pytest.mark.parametrize("valor", ["yes", "0", "1", "maybe", ""])
def test_parse_bool_param_invalido_levanta_400(valor):
    with pytest.raises(HTTPException) as exc_info:
        parse_bool_param(valor, "is_verified")
    assert exc_info.value.status_code == 400


# --- validate_name_param --------------------------------------------------


@pytest.mark.parametrize("nome", ["Adobe", "Adult-Friend.Finder", "000webhost", "a"])
def test_validate_name_param_aceita_slug_valido(nome):
    assert validate_name_param(nome) == nome


@pytest.mark.parametrize(
    "nome",
    [
        "",
        "Adobe Inc",  # espaço
        "Adobe;DROP TABLE",  # ponto-e-vírgula
        "Adobe/Inc",  # barra
        "Adobe'OR'1'='1",  # aspas
    ],
)
def test_validate_name_param_invalido_levanta_400(nome):
    with pytest.raises(HTTPException) as exc_info:
        validate_name_param(nome)
    assert exc_info.value.status_code == 400


# --- parse_positive_int_param ---------------------------------------------


def test_parse_positive_int_param_none_retorna_default():
    assert parse_positive_int_param(None, "page", default=1) == 1


def test_parse_positive_int_param_aceita_valor_valido():
    assert parse_positive_int_param("3", "page", default=1) == 3


@pytest.mark.parametrize("valor", ["0", "-1", "abc", "1.5"])
def test_parse_positive_int_param_invalido_levanta_400(valor):
    with pytest.raises(HTTPException) as exc_info:
        parse_positive_int_param(valor, "page", default=1)
    assert exc_info.value.status_code == 400


def test_parse_positive_int_param_respeita_max_value():
    assert parse_positive_int_param("100", "page_size", default=20, max_value=100) == 100


def test_parse_positive_int_param_acima_de_max_value_levanta_400():
    with pytest.raises(HTTPException) as exc_info:
        parse_positive_int_param("101", "page_size", default=20, max_value=100)
    assert exc_info.value.status_code == 400
