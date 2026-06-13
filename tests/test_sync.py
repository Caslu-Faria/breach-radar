"""Testes de app/sync.py e do endpoint POST /sync."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx

from app.config import settings
from app.models import Breach

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hibp_sample.json"
SAMPLE_BREACHES = json.loads(FIXTURE_PATH.read_text())

# A fixture tem um registro sem "Name" (sempre ignorado/contado em "skipped").
TOTAL_FROM_FEED = len(SAMPLE_BREACHES)
TOTAL_VALIDOS = sum(1 for b in SAMPLE_BREACHES if b.get("Name"))
TOTAL_SEM_NAME = TOTAL_FROM_FEED - TOTAL_VALIDOS


@respx.mock
def test_sync_cria_breaches_e_retorna_contagens(client, db_session):
    respx.get(settings.hibp_api_url).mock(return_value=httpx.Response(200, json=SAMPLE_BREACHES))

    response = client.post("/sync")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "total_from_feed": TOTAL_FROM_FEED,
        "created": TOTAL_VALIDOS,
        "updated": 0,
        "skipped": TOTAL_SEM_NAME,
    }
    assert db_session.query(Breach).count() == TOTAL_VALIDOS


@respx.mock
def test_sync_executado_duas_vezes_nao_duplica(client, db_session):
    respx.get(settings.hibp_api_url).mock(return_value=httpx.Response(200, json=SAMPLE_BREACHES))

    client.post("/sync")
    response = client.post("/sync")

    body = response.json()
    assert body["created"] == 0
    assert body["updated"] == TOTAL_VALIDOS
    assert body["skipped"] == TOTAL_SEM_NAME
    assert db_session.query(Breach).count() == TOTAL_VALIDOS


@respx.mock
def test_sync_aplica_defaults_para_campos_ausentes(client, db_session):
    respx.get(settings.hibp_api_url).mock(return_value=httpx.Response(200, json=SAMPLE_BREACHES))

    client.post("/sync")

    sem_data_classes = db_session.get(Breach, "SemDataClasses")
    assert sem_data_classes.data_classes == []

    sem_dominio = db_session.get(Breach, "SemDominio")
    assert sem_dominio.domain == ""

    sem_breach_date = db_session.get(Breach, "SemBreachDate")
    assert sem_breach_date.breach_date is None


@respx.mock
def test_sync_atualiza_registro_existente(client, db_session):
    route = respx.get(settings.hibp_api_url).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "Name": "Adobe",
                    "Domain": "adobe.com",
                    "BreachDate": "2013-10-04",
                    "AddedDate": "2013-12-04T00:00:00Z",
                    "PwnCount": 100,
                    "DataClasses": ["Email addresses"],
                    "IsVerified": False,
                    "IsSensitive": False,
                    "IsSpamList": False,
                }
            ],
        )
    )
    client.post("/sync")

    route.mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "Name": "Adobe",
                    "Domain": "adobe.com",
                    "BreachDate": "2013-10-04",
                    "AddedDate": "2013-12-04T00:00:00Z",
                    "PwnCount": 152445165,
                    "DataClasses": ["Email addresses", "Passwords"],
                    "IsVerified": True,
                    "IsSensitive": False,
                    "IsSpamList": False,
                }
            ],
        )
    )
    response = client.post("/sync")

    body = response.json()
    assert body == {"total_from_feed": 1, "created": 0, "updated": 1, "skipped": 0}
    assert db_session.query(Breach).count() == 1

    adobe = db_session.get(Breach, "Adobe")
    assert adobe.pwn_count == 152445165
    assert adobe.is_verified is True
    assert adobe.data_classes == ["Email addresses", "Passwords"]


@respx.mock
def test_sync_retorna_503_quando_feed_timeout(client, db_session):
    respx.get(settings.hibp_api_url).mock(side_effect=httpx.TimeoutException("timeout"))

    response = client.post("/sync")

    assert response.status_code == 503
    assert db_session.query(Breach).count() == 0


@respx.mock
def test_sync_retorna_503_quando_feed_responde_500(client, db_session):
    respx.get(settings.hibp_api_url).mock(return_value=httpx.Response(500))

    response = client.post("/sync")

    assert response.status_code == 503
    assert db_session.query(Breach).count() == 0


@respx.mock
def test_sync_retorna_503_quando_json_invalido(client, db_session):
    respx.get(settings.hibp_api_url).mock(
        return_value=httpx.Response(200, content="isto nao e json")
    )

    response = client.post("/sync")

    assert response.status_code == 503
    assert db_session.query(Breach).count() == 0


@respx.mock
def test_sync_nao_altera_banco_apos_sync_anterior_se_novo_sync_falhar(client, db_session):
    route = respx.get(settings.hibp_api_url).mock(
        return_value=httpx.Response(200, json=SAMPLE_BREACHES)
    )
    client.post("/sync")

    route.mock(side_effect=httpx.TimeoutException("timeout"))
    response = client.post("/sync")

    assert response.status_code == 503
    assert db_session.query(Breach).count() == TOTAL_VALIDOS
