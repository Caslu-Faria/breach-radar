"""Schemas Pydantic (request/response) da API."""

from __future__ import annotations

from pydantic import BaseModel


class SyncResult(BaseModel):
    """Resultado de uma execução de `POST /sync`."""

    total_from_feed: int
    created: int
    updated: int
    skipped: int


class BreachOut(BaseModel):
    """Representação de um breach na resposta da API (`snake_case`)."""

    name: str
    domain: str | None
    breach_date: str | None
    added_date: str | None
    pwn_count: int
    data_classes: list[str]
    is_verified: bool
    is_sensitive: bool
    is_spam_list: bool


class BreachListResponse(BaseModel):
    """Resposta paginada de `GET /breaches`."""

    items: list[BreachOut]
    page: int
    page_size: int
    total: int
    total_pages: int
