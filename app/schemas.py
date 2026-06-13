"""Schemas Pydantic (request/response) da API."""

from __future__ import annotations

from pydantic import BaseModel


class SyncResult(BaseModel):
    """Resultado de uma execução de `POST /sync`."""

    total_from_feed: int
    created: int
    updated: int
    skipped: int
