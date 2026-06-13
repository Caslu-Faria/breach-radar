"""Testes de GET /breaches/{name} — encontrado, não encontrado e slug inválido."""

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


def test_breach_encontrado_retorna_200_com_dados_em_snake_case(client, seeded):
    response = client.get("/breaches/Adobe")
    assert response.status_code == 200
    assert response.json() == {
        "name": "Adobe",
        "domain": "adobe.com",
        "breach_date": "2013-10-04",
        "added_date": "2013-12-04T00:00:00Z",
        "pwn_count": 152445165,
        "data_classes": ["Email addresses", "Password hints", "Passwords", "Usernames"],
        "is_verified": True,
        "is_sensitive": False,
        "is_spam_list": False,
    }


def test_breach_nao_encontrado_retorna_404(client, seeded):
    response = client.get("/breaches/NaoExiste")
    assert response.status_code == 404


@pytest.mark.parametrize("slug", ["Invalid%20Name", "Adobe;DROP"])
def test_slug_invalido_retorna_400(client, seeded, slug):
    response = client.get(f"/breaches/{slug}")
    assert response.status_code == 400
