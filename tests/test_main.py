"""Testes do esqueleto da aplicação FastAPI."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from app.main import lifespan


def test_docs_responde_200(client):
    response = client.get("/docs")
    assert response.status_code == 200


def _run_lifespan():
    async def run():
        async with lifespan(None):
            pass

    asyncio.run(run())


def test_lifespan_sqlite_chama_create_all():
    with (
        patch("app.main.database.engine") as engine,
        patch("app.main.database.Base.metadata.create_all") as create_all,
    ):
        engine.dialect.name = "sqlite"
        _run_lifespan()

    create_all.assert_called_once_with(bind=engine)


def test_lifespan_postgres_nao_chama_create_all():
    with (
        patch("app.main.database.engine") as engine,
        patch("app.main.database.Base.metadata.create_all") as create_all,
    ):
        engine.dialect.name = "postgresql"
        _run_lifespan()

    create_all.assert_not_called()


def test_lifespan_encerra_scheduler_quando_ativo():
    fake_scheduler = MagicMock()

    with patch("app.main.scheduler.start_scheduler", return_value=fake_scheduler):
        _run_lifespan()

    fake_scheduler.shutdown.assert_called_once()


def test_lifespan_sem_scheduler_nao_chama_shutdown():
    with patch("app.main.scheduler.start_scheduler", return_value=None):
        _run_lifespan()  # não deve levantar AttributeError ao tentar shutdown()
