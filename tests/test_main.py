"""Testes do esqueleto da aplicação FastAPI."""

from __future__ import annotations


def test_docs_responde_200(client):
    response = client.get("/docs")
    assert response.status_code == 200
