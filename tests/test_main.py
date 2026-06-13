"""Testes do esqueleto da aplicação FastAPI."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

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
