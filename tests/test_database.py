"""Testes de app/database.py: criação do engine e generator get_db()."""

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import _create_engine, get_db


def test_create_engine_sqlite_em_memoria_usa_static_pool():
    engine = _create_engine("sqlite://")

    assert engine.dialect.name == "sqlite"
    assert isinstance(engine.pool, StaticPool)


def test_create_engine_postgres_usa_create_engine_padrao():
    engine = _create_engine("postgresql+psycopg://user:pass@localhost/db")

    assert engine.dialect.name == "postgresql"
    assert not isinstance(engine.pool, StaticPool)


def test_get_db_produz_sessao_e_fecha_ao_finalizar():
    generator = get_db()

    db = next(generator)
    assert isinstance(db, Session)

    # Esgotar o generator executa o `finally` (db.close()) sem levantar erro.
    next(generator, None)
