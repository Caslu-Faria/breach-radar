"""Testes do formatter de logs em JSON (app/logging_config.py)."""

from __future__ import annotations

import json
import logging
import sys

from app.logging_config import JSONFormatter, configure_logging


def _make_record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.sync",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="sync concluído",
        args=None,
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_format_inclui_campos_basicos_e_extras():
    record = _make_record(total_from_feed=3, breaches_created=2, breaches_updated=1)

    payload = json.loads(JSONFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.sync"
    assert payload["message"] == "sync concluído"
    assert payload["total_from_feed"] == 3
    assert payload["breaches_created"] == 2
    assert payload["breaches_updated"] == 1
    assert "timestamp" in payload


def test_format_nao_inclui_atributos_reservados_do_log_record():
    record = _make_record()

    payload = json.loads(JSONFormatter().format(record))

    # `created` é o timestamp interno do LogRecord, não um campo de negócio.
    assert "created" not in payload


def test_format_inclui_exc_info_quando_presente():
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="app.sync",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="sync falhou",
            args=None,
            exc_info=sys.exc_info(),
        )

    payload = json.loads(JSONFormatter().format(record))

    assert "ValueError: boom" in payload["exc_info"]


def test_configure_logging_define_handler_json_no_logger_raiz():
    configure_logging(level=logging.DEBUG)

    root = logging.getLogger()
    try:
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JSONFormatter)
        assert root.level == logging.DEBUG
    finally:
        configure_logging()  # restaura nível padrão para não afetar outros testes
