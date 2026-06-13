"""Sync agendado do catálogo de breaches (opcional, via APScheduler).

Controlado por `ENABLE_SCHEDULED_SYNC` (default desativado, para não disparar
chamadas à HIBP durante os testes). Quando ativo, roda `sync_breaches` a cada
`SYNC_INTERVAL_MINUTES` minutos.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.hibp_client import HIBPFeedError
from app.sync import sync_breaches


def run_sync_job() -> None:
    """Executa um ciclo de sync isolando falhas do feed (não derruba o agendador).

    `sync_breaches` já loga início/conclusão/falha (ver `app/sync.py`).
    """
    db = SessionLocal()
    try:
        sync_breaches(db)
    except HIBPFeedError:
        pass
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler | None:
    """Inicia o `BackgroundScheduler` se `ENABLE_SCHEDULED_SYNC` estiver ativo.

    Retorna `None` (sem agendar nada) quando desativado.
    """
    if not settings.enable_scheduled_sync:
        return None

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_sync_job,
        "interval",
        minutes=settings.sync_interval_minutes,
        id="hibp_sync",
    )
    scheduler.start()
    return scheduler
