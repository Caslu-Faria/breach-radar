"""Testes de GET /breaches — cada um dos 12 filtros isolado + combinações AND.

A base de dados é semeada diretamente via ORM (sem depender de /sync), com um
conjunto pequeno e controlado de breaches que cobre os limites de cada filtro.
"""

from __future__ import annotations

import pytest

from app.models import Breach

# kwargs para Breach(**kwargs) — uma instância nova é criada por teste (ver
# fixture `seeded`), evitando reusar objetos ORM já vinculados a outra sessão.
BREACHES = [
    dict(
        name="Adobe",
        domain="adobe.com",
        breach_date="2013-10-04",
        added_date="2013-12-04T00:00:00Z",
        pwn_count=152445165,
        data_classes=["Email addresses", "Password hints", "Passwords", "Usernames"],
        is_verified=True,
        is_sensitive=False,
        is_spam_list=False,
    ),
    dict(
        name="Dropbox",
        domain="dropbox.com",
        breach_date="2012-07-01",
        added_date="2016-08-31T00:00:00Z",
        pwn_count=68648009,
        data_classes=["Email addresses", "Passwords"],
        is_verified=True,
        is_sensitive=False,
        is_spam_list=False,
    ),
    dict(
        name="AdultFriendFinder",
        domain="",
        breach_date="2016-10-15",
        added_date="2016-11-13T09:04:00Z",
        pwn_count=412214295,
        data_classes=[
            "Browser user agent details",
            "Email addresses",
            "Passwords",
            "Sexual orientations",
        ],
        is_verified=True,
        is_sensitive=True,
        is_spam_list=True,
    ),
    dict(
        name="ExploitIn",
        domain="exploit.in",
        breach_date="2016-10-13",
        added_date="2017-05-19T08:14:00Z",
        pwn_count=593427119,
        data_classes=["Email addresses", "Passwords"],
        is_verified=False,
        is_sensitive=False,
        is_spam_list=True,
    ),
    dict(
        name="MySpace",
        domain="myspace.com",
        breach_date="2008-07-01",
        added_date="2016-05-27T00:00:00Z",
        pwn_count=359420698,
        data_classes=["Email addresses", "Passwords", "Usernames"],
        is_verified=True,
        is_sensitive=False,
        is_spam_list=False,
    ),
]


@pytest.fixture()
def seeded(db_session):
    db_session.add_all(Breach(**kwargs) for kwargs in BREACHES)
    db_session.commit()


def names(response):
    return {item["name"] for item in response.json()["items"]}


# --- domain ---------------------------------------------------------------


def test_filtro_domain_match_parcial(client, seeded):
    response = client.get("/breaches", params={"domain": "dropbox"})
    assert response.status_code == 200
    assert names(response) == {"Dropbox"}


def test_filtro_domain_case_insensitive(client, seeded):
    response = client.get("/breaches", params={"domain": "DROPBOX"})
    assert names(response) == {"Dropbox"}


def test_filtro_domain_substring_comum(client, seeded):
    response = client.get("/breaches", params={"domain": ".com"})
    assert names(response) == {"Adobe", "Dropbox", "MySpace"}


# --- name -------------------------------------------------------------------


def test_filtro_name_match_exato(client, seeded):
    response = client.get("/breaches", params={"name": "Adobe"})
    assert names(response) == {"Adobe"}


def test_filtro_name_case_sensitive_nao_casa(client, seeded):
    response = client.get("/breaches", params={"name": "adobe"})
    assert names(response) == set()


def test_filtro_name_invalido_retorna_400(client, seeded):
    response = client.get("/breaches", params={"name": "Adobe Inc"})
    assert response.status_code == 400


# --- breach_date_from / breach_date_to ---------------------------------------


def test_filtro_breach_date_janela_inclusiva(client, seeded):
    response = client.get(
        "/breaches",
        params={"breach_date_from": "2013-01-01", "breach_date_to": "2016-12-31"},
    )
    assert names(response) == {"Adobe", "AdultFriendFinder", "ExploitIn"}


def test_filtro_breach_date_to_inclui_data_limite(client, seeded):
    response = client.get("/breaches", params={"breach_date_to": "2016-10-13"})
    assert "ExploitIn" in names(response)
    assert "AdultFriendFinder" not in names(response)


def test_filtro_breach_date_from_invalido_retorna_400(client, seeded):
    response = client.get("/breaches", params={"breach_date_from": "2020/01/01"})
    assert response.status_code == 400


# --- added_date_from / added_date_to -----------------------------------------


def test_filtro_added_date_janela_inclusiva(client, seeded):
    response = client.get(
        "/breaches",
        params={"added_date_from": "2016-01-01", "added_date_to": "2016-12-31"},
    )
    assert names(response) == {"Dropbox", "AdultFriendFinder", "MySpace"}


def test_filtro_added_date_to_invalido_retorna_400(client, seeded):
    response = client.get("/breaches", params={"added_date_to": "not-a-date"})
    assert response.status_code == 400


# --- data_class --------------------------------------------------------------


def test_filtro_data_class_comum_a_varios(client, seeded):
    response = client.get("/breaches", params={"data_class": "passwords"})
    assert names(response) == {"Adobe", "Dropbox", "AdultFriendFinder", "ExploitIn", "MySpace"}


def test_filtro_data_class_case_insensitive_e_especifico(client, seeded):
    response = client.get("/breaches", params={"data_class": "Sexual Orientations"})
    assert names(response) == {"AdultFriendFinder"}


# --- min_pwn_count / max_pwn_count --------------------------------------------


def test_filtro_min_pwn_count(client, seeded):
    response = client.get("/breaches", params={"min_pwn_count": "200000000"})
    assert names(response) == {"AdultFriendFinder", "ExploitIn", "MySpace"}


def test_filtro_max_pwn_count(client, seeded):
    response = client.get("/breaches", params={"max_pwn_count": "100000000"})
    assert names(response) == {"Dropbox"}


def test_filtro_pwn_count_faixa(client, seeded):
    response = client.get(
        "/breaches",
        params={"min_pwn_count": "100000000", "max_pwn_count": "400000000"},
    )
    assert names(response) == {"Adobe", "MySpace"}


def test_filtro_min_pwn_count_negativo_retorna_400(client, seeded):
    response = client.get("/breaches", params={"min_pwn_count": "-1"})
    assert response.status_code == 400


def test_filtro_max_pwn_count_nao_inteiro_retorna_400(client, seeded):
    response = client.get("/breaches", params={"max_pwn_count": "abc"})
    assert response.status_code == 400


# --- is_verified / is_sensitive / is_spam_list --------------------------------


def test_filtro_is_verified_true(client, seeded):
    response = client.get("/breaches", params={"is_verified": "true"})
    assert names(response) == {"Adobe", "Dropbox", "AdultFriendFinder", "MySpace"}


def test_filtro_is_verified_false(client, seeded):
    response = client.get("/breaches", params={"is_verified": "false"})
    assert names(response) == {"ExploitIn"}


def test_filtro_is_sensitive_true(client, seeded):
    response = client.get("/breaches", params={"is_sensitive": "true"})
    assert names(response) == {"AdultFriendFinder"}


def test_filtro_is_spam_list_true(client, seeded):
    response = client.get("/breaches", params={"is_spam_list": "true"})
    assert names(response) == {"AdultFriendFinder", "ExploitIn"}


def test_filtro_is_verified_invalido_retorna_400(client, seeded):
    response = client.get("/breaches", params={"is_verified": "maybe"})
    assert response.status_code == 400


# --- combinação de filtros (semântica AND) -------------------------------------


def test_combinacao_de_filtros_em_and(client, seeded):
    response = client.get(
        "/breaches",
        params={
            "is_verified": "true",
            "data_class": "passwords",
            "min_pwn_count": "100000000",
        },
    )
    assert names(response) == {"Adobe", "AdultFriendFinder", "MySpace"}


def test_combinacao_sem_resultados(client, seeded):
    response = client.get(
        "/breaches",
        params={"domain": "dropbox", "is_sensitive": "true"},
    )
    assert response.json()["items"] == []
    assert response.json()["total"] == 0
