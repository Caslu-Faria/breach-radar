"""Testes de paginação de GET /breaches — primeira/última página, página
exagerada, percurso completo com page_size=1 e validação de page/page_size.
"""

from __future__ import annotations

import pytest

from app.models import Breach

TOTAL_BREACHES = 5

# kwargs para Breach(**kwargs) — instâncias novas por teste (ver fixture `seeded`).
BREACHES = [
    dict(
        name=f"Site{i}",
        domain=f"site{i}.example",
        breach_date="2020-01-01",
        added_date="2020-01-01T00:00:00Z",
        pwn_count=i,
        data_classes=["Email addresses"],
        is_verified=False,
        is_sensitive=False,
        is_spam_list=False,
    )
    for i in range(1, TOTAL_BREACHES + 1)
]


@pytest.fixture()
def seeded(db_session):
    db_session.add_all(Breach(**kwargs) for kwargs in BREACHES)
    db_session.commit()


def test_primeira_pagina(client, seeded):
    response = client.get("/breaches", params={"page": "1", "page_size": "2"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] == TOTAL_BREACHES
    assert body["total_pages"] == 3


def test_ultima_pagina_parcial(client, seeded):
    response = client.get("/breaches", params={"page": "3", "page_size": "2"})
    body = response.json()
    assert len(body["items"]) == 1
    assert body["total"] == TOTAL_BREACHES
    assert body["total_pages"] == 3


def test_pagina_exagerada_retorna_vazio_com_total_correto(client, seeded):
    response = client.get("/breaches", params={"page": "100", "page_size": "2"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == TOTAL_BREACHES
    assert body["total_pages"] == 3


def test_page_size_1_percorre_todos_sem_perder_item(client, seeded):
    nomes_vistos = set()
    for page in range(1, TOTAL_BREACHES + 1):
        response = client.get("/breaches", params={"page": str(page), "page_size": "1"})
        body = response.json()
        assert len(body["items"]) == 1
        nomes_vistos.add(body["items"][0]["name"])

    assert nomes_vistos == {f"Site{i}" for i in range(1, TOTAL_BREACHES + 1)}


def test_pagina_alem_do_total_apos_percorrer_tudo_fica_vazia(client, seeded):
    response = client.get("/breaches", params={"page": str(TOTAL_BREACHES + 1), "page_size": "1"})
    body = response.json()
    assert body["items"] == []
    assert body["total_pages"] == TOTAL_BREACHES


def test_pagination_default_retorna_pagina_1_com_tamanho_20(client, seeded):
    response = client.get("/breaches")
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["items"]) == TOTAL_BREACHES


def test_page_size_no_limite_maximo_e_aceito(client, seeded):
    response = client.get("/breaches", params={"page_size": "100"})
    assert response.status_code == 200


@pytest.mark.parametrize("page", ["0", "-1", "abc", "1.5"])
def test_page_invalido_retorna_400(client, seeded, page):
    response = client.get("/breaches", params={"page": page})
    assert response.status_code == 400


@pytest.mark.parametrize("page_size", ["0", "-1", "abc", "101"])
def test_page_size_invalido_retorna_400(client, seeded, page_size):
    response = client.get("/breaches", params={"page_size": page_size})
    assert response.status_code == 400
