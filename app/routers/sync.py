"""Endpoint `POST /sync` — sincroniza o catálogo local com o feed da HIBP."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.hibp_client import HIBPFeedError
from app.schemas import SyncResult
from app.sync import sync_breaches

router = APIRouter()


@router.post("/sync", response_model=SyncResult)
def sync(db: Session = Depends(get_db)) -> SyncResult:
    """Sincroniza o catálogo local com o feed da HIBP (upsert por `Name`).

    Retorna `503` se o feed da HIBP estiver indisponível ou responder com
    dados inválidos — o banco local não é alterado nesse caso.
    """
    try:
        return sync_breaches(db)
    except HIBPFeedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
