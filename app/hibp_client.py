"""Cliente HTTP para o feed público de breaches da HIBP."""

from __future__ import annotations

import httpx

from app.config import settings


class HIBPFeedError(Exception):
    """Erro ao buscar ou interpretar o feed de breaches da HIBP."""


def fetch_breaches() -> list[dict]:
    """Busca o catálogo completo de breaches em `settings.hibp_api_url`.

    Envia o header `User-Agent` exigido pela HIBP (sem ele a resposta é 403).

    Levanta `HIBPFeedError` se a requisição falhar (timeout, erro de conexão),
    se o status HTTP não for 200, ou se o corpo não for um JSON válido
    contendo uma lista.
    """
    headers = {"User-Agent": settings.hibp_user_agent}
    try:
        response = httpx.get(
            settings.hibp_api_url,
            headers=headers,
            timeout=settings.hibp_timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        raise HIBPFeedError(f"timeout ao buscar feed da HIBP: {exc}") from exc
    except httpx.RequestError as exc:
        raise HIBPFeedError(f"erro de conexão ao buscar feed da HIBP: {exc}") from exc

    if response.status_code != 200:
        raise HIBPFeedError(f"feed da HIBP retornou status {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        raise HIBPFeedError(f"feed da HIBP retornou JSON inválido: {exc}") from exc

    if not isinstance(data, list):
        raise HIBPFeedError("feed da HIBP retornou um JSON que não é uma lista")

    return data
