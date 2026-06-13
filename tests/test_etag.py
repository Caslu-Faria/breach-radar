"""Testes do cache HTTP via ETag/If-None-Match (app/etag.py)."""

from __future__ import annotations

import pytest

from app.models import Breach


@pytest.fixture()
def seeded(db_session):
    db_session.add(
        Breach(
            name="Adobe",
            domain="adobe.com",
            breach_date="2013-10-04",
            added_date="2013-12-04T00:00:00Z",
            pwn_count=152445165,
            data_classes=["Email addresses", "Password hints", "Passwords", "Usernames"],
            is_verified=True,
            is_sensitive=False,
            is_spam_list=False,
        )
    )
    db_session.commit()


def test_list_breaches_define_header_etag(client, seeded):
    response = client.get("/breaches")
    assert response.status_code == 200
    assert response.headers["etag"]


def test_list_breaches_if_none_match_igual_responde_304_sem_corpo(client, seeded):
    primeira = client.get("/breaches")
    etag = primeira.headers["etag"]

    segunda = client.get("/breaches", headers={"If-None-Match": etag})

    assert segunda.status_code == 304
    assert segunda.content == b""
    assert segunda.headers["etag"] == etag


def test_list_breaches_if_none_match_diferente_responde_200(client, seeded):
    response = client.get("/breaches", headers={"If-None-Match": '"etag-antigo"'})
    assert response.status_code == 200
    assert response.headers["etag"]


def test_get_breach_define_header_etag(client, seeded):
    response = client.get("/breaches/Adobe")
    assert response.status_code == 200
    assert response.headers["etag"]


def test_get_breach_if_none_match_igual_responde_304_sem_corpo(client, seeded):
    primeira = client.get("/breaches/Adobe")
    etag = primeira.headers["etag"]

    segunda = client.get("/breaches/Adobe", headers={"If-None-Match": etag})

    assert segunda.status_code == 304
    assert segunda.content == b""
    assert segunda.headers["etag"] == etag


def test_get_breach_if_none_match_diferente_responde_200(client, seeded):
    response = client.get("/breaches/Adobe", headers={"If-None-Match": '"etag-antigo"'})
    assert response.status_code == 200
    assert response.headers["etag"]
