"""Testes do sync agendado (app/scheduler.py)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from apscheduler.schedulers.background import BackgroundScheduler

from app import scheduler
from app.hibp_client import HIBPFeedError


def test_start_scheduler_desativado_retorna_none():
    with patch("app.scheduler.settings") as settings:
        settings.enable_scheduled_sync = False

        assert scheduler.start_scheduler() is None


def test_start_scheduler_ativado_agenda_job_de_sync():
    with patch("app.scheduler.settings") as settings:
        settings.enable_scheduled_sync = True
        settings.sync_interval_minutes = 30

        result = scheduler.start_scheduler()

    try:
        assert isinstance(result, BackgroundScheduler)
        assert result.get_job("hibp_sync") is not None
    finally:
        result.shutdown()


def test_run_sync_job_sucesso_chama_sync_breaches_e_fecha_sessao():
    fake_db = MagicMock()

    with (
        patch("app.scheduler.SessionLocal", return_value=fake_db),
        patch("app.scheduler.sync_breaches") as sync_breaches,
    ):
        scheduler.run_sync_job()

    sync_breaches.assert_called_once_with(fake_db)
    fake_db.close.assert_called_once()


def test_run_sync_job_feed_indisponivel_nao_propaga():
    fake_db = MagicMock()

    with (
        patch("app.scheduler.SessionLocal", return_value=fake_db),
        patch("app.scheduler.sync_breaches", side_effect=HIBPFeedError("feed fora do ar")),
    ):
        scheduler.run_sync_job()  # não deve levantar

    fake_db.close.assert_called_once()
