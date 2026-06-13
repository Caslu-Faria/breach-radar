"""Aplicação FastAPI do Breach Radar."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import (
    database,
    models,  # noqa: F401 — registra Breach em Base.metadata para o create_all
    scheduler,
)
from app.logging_config import configure_logging
from app.routers import breaches, sync

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SQLite (default sem .env, usado em testes e modo local) cria as tabelas
    # automaticamente no startup. Em Postgres, o schema é gerenciado pelo Alembic
    # (`alembic upgrade head` — ver README).
    if database.engine.dialect.name == "sqlite":
        database.Base.metadata.create_all(bind=database.engine)

    sync_scheduler = scheduler.start_scheduler()
    yield
    if sync_scheduler is not None:
        sync_scheduler.shutdown()


app = FastAPI(title="Breach Radar", lifespan=lifespan)
app.include_router(breaches.router)
app.include_router(sync.router)
