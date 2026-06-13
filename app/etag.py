"""Cache HTTP via ETag/If-None-Match para os endpoints GET /breaches*."""

from __future__ import annotations

import hashlib

from fastapi import Request, Response
from pydantic import BaseModel


def compute_etag(model: BaseModel) -> str:
    """Calcula um ETag forte (SHA-256 do JSON do model)."""
    body = model.model_dump_json().encode("utf-8")
    return f'"{hashlib.sha256(body).hexdigest()}"'


def etag_response(request: Request, response: Response, model: BaseModel) -> BaseModel | Response:
    """Define o header `ETag` e responde `304` se `If-None-Match` casar.

    Caso contrário, define `ETag` em `response.headers` e retorna `model`
    (serializado normalmente pelo `response_model` da rota).
    """
    etag = compute_etag(model)
    response.headers["ETag"] = etag

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})

    return model
