"""Configuração de logs estruturados em JSON (usados nos eventos de sync)."""

from __future__ import annotations

import json
import logging

# Atributos padrão de um LogRecord — qualquer outro atributo presente em
# `record.__dict__` veio de `extra={...}` no log e é incluído no JSON.
_RESERVED_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
    "message",
}


class JSONFormatter(logging.Formatter):
    """Formata cada `LogRecord` como uma linha JSON.

    Campos fixos: `timestamp`, `level`, `logger`, `message`. Quaisquer
    chaves passadas via `extra={...}` são incluídas no JSON resultante.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        extras = {
            key: value for key, value in record.__dict__.items() if key not in _RESERVED_ATTRS
        }
        payload.update(extras)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Configura o logger raiz para emitir uma linha JSON por log em stdout."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
