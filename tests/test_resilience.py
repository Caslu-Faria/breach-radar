"""Testes de resiliência: GET /breaches e GET /breaches/{name} continuam
respondendo a partir do banco local mesmo com o feed da HIBP fora do ar.

Cenário: um `/sync` anterior (feed OK) já populou o banco; em seguida o feed
da HIBP fica indisponível (timeout ou 500). As leituras (`GET /breaches*`)
nunca chamam a HIBP, então continuam `200` com os dados já sincronizados. Um
novo `POST /sync` nesse cenário retorna `503` e não altera o banco.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx

from app.config import settings
from app.models import Breach

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hibp_sample.json"
SAMPLE_BREACHES = json.loads(FIXTURE_PATH.read_text())
TOTAL_VALIDOS = sum(1 for b in SAMPLE_BREACHES if b.get("Name"))


def _seed_via_sync(client) -> respx.Route:
    """Popula o banco local via `/sync` com um feed (mockado) que responde OK.

    Deve ser chamado dentro de um teste decorado com `@respx.mock`. Retorna a
    `Route` registrada, para que o teste troque o comportamento depois (ex.:
    simular o feed indisponível) via `route.mock(...)`.
    """
    route = respx.get(settings.hibp_api_url).mock(
        return_value=httpx.Response(200, json=SAMPLE_BREACHES)
    )
    response = client.post("/sync")
    assert response.status_code == 200
    return route


@respx.mock
def test_get_breaches_continua_200_com_feed_hibp_em_timeout(client, db_session):
    route = _seed_via_sync(client)

    route.mock(side_effect=httpx.TimeoutException("timeout"))

    response = client.get("/breaches")

    assert response.status_code == 200
    assert response.json()["total"] == TOTAL_VALIDOS


@respx.mock
def test_get_breaches_continua_200_com_feed_hibp_respondendo_500(client, db_session):
    route = _seed_via_sync(client)

    route.mock(return_value=httpx.Response(500))

    response = client.get("/breaches")

    assert response.status_code == 200
    assert response.json()["total"] == TOTAL_VALIDOS


@respx.mock
def test_get_breach_detail_continua_200_com_feed_hibp_indisponivel(client, db_session):
    route = _seed_via_sync(client)

    route.mock(side_effect=httpx.TimeoutException("timeout"))

    response = client.get("/breaches/Adobe")

    assert response.status_code == 200
    assert response.json()["name"] == "Adobe"


@respx.mock
def test_novo_sync_com_feed_indisponivel_retorna_503_e_nao_altera_banco(client, db_session):
    route = _seed_via_sync(client)

    route.mock(side_effect=httpx.TimeoutException("timeout"))

    sync_response = client.post("/sync")
    assert sync_response.status_code == 503
    assert db_session.query(Breach).count() == TOTAL_VALIDOS

    # GET /breaches continua respondendo com os dados do /sync anterior.
    list_response = client.get("/breaches")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == TOTAL_VALIDOS
