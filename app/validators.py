"""Validadores dos query params de `GET /breaches` e `GET /breaches/{name}`.

Os filtros são declarados nas rotas como `str | None = Query(None)` (evita o
422 automático do FastAPI). Cada validador recebe esse valor bruto e devolve
o tipo já convertido (ou `None`/`default`, se o filtro não foi informado), ou
levanta `HTTPException(400, ...)` com uma mensagem clara se o valor for
inválido.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException

from legacy.breach_matcher import is_valid_breach_name


def parse_date_param(value: str | None, field_name: str) -> str | None:
    """Valida uma data no formato `YYYY-MM-DD`, devolvendo-a sem alterações.

    `None` é devolvido como `None` (filtro não informado). Levanta
    `HTTPException(400)` se `value` não estiver no formato `YYYY-MM-DD` ou não
    representar uma data válida (ex.: `2021-02-30`).
    """
    if value is None:
        return None
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} inválido: '{value}' (esperado YYYY-MM-DD)",
        ) from exc
    if len(value) != len("YYYY-MM-DD"):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} inválido: '{value}' (esperado YYYY-MM-DD)",
        )
    return value


def parse_non_negative_int_param(value: str | None, field_name: str) -> int | None:
    """Valida um inteiro >= 0. `None` é devolvido como `None` (filtro não
    informado). Levanta `HTTPException(400)` se `value` não for um inteiro ou
    for negativo."""
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} inválido: '{value}' (esperado inteiro >= 0)",
        ) from exc
    if parsed < 0:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} inválido: '{value}' (esperado inteiro >= 0)",
        )
    return parsed


def parse_bool_param(value: str | None, field_name: str) -> bool | None:
    """Valida um booleano (`true`/`false`, case-insensitive). `None` é
    devolvido como `None` (filtro não informado). Levanta
    `HTTPException(400)` para qualquer outro valor."""
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise HTTPException(
        status_code=400,
        detail=f"{field_name} inválido: '{value}' (esperado true ou false)",
    )


def validate_name_param(name: str) -> str:
    """Valida que `name` é um slug de breach válido (letras, dígitos, `.` e
    `-`, não vazio — ver `legacy.breach_matcher.is_valid_breach_name`).
    Levanta `HTTPException(400)` se `name` for inválido."""
    if not is_valid_breach_name(name):
        raise HTTPException(status_code=400, detail=f"name inválido: '{name}'")
    return name


def parse_positive_int_param(
    value: str | None,
    field_name: str,
    *,
    default: int,
    max_value: int | None = None,
) -> int:
    """Valida um inteiro >= 1 (opcionalmente limitado a `max_value`). `None`
    devolve `default`. Levanta `HTTPException(400)` se `value` não for um
    inteiro, for < 1 ou maior que `max_value`."""
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} inválido: '{value}' (esperado inteiro >= 1)",
        ) from exc
    if parsed < 1 or (max_value is not None and parsed > max_value):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{field_name} inválido: '{value}' (esperado inteiro entre 1 e {max_value})"
                if max_value is not None
                else f"{field_name} inválido: '{value}' (esperado inteiro >= 1)"
            ),
        )
    return parsed
