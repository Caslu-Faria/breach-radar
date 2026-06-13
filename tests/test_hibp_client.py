"""Testes de app/hibp_client.py — sucesso e cenários de falha do feed da HIBP."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.config import settings
from app.hibp_client import HIBPFeedError, fetch_breaches


@respx.mock
def test_fetch_breaches_sucesso():
    respx.get(settings.hibp_api_url).mock(
        return_value=httpx.Response(200, json=[{"Name": "Adobe"}, {"Name": "Dropbox"}])
    )

    breaches = fetch_breaches()

    assert breaches == [{"Name": "Adobe"}, {"Name": "Dropbox"}]


@respx.mock
def test_fetch_breaches_envia_user_agent():
    route = respx.get(settings.hibp_api_url).mock(return_value=httpx.Response(200, json=[]))

    fetch_breaches()

    assert route.calls.last.request.headers["User-Agent"] == settings.hibp_user_agent


@respx.mock
def test_fetch_breaches_timeout_levanta_hibp_feed_error():
    respx.get(settings.hibp_api_url).mock(side_effect=httpx.TimeoutException("timeout"))

    with pytest.raises(HIBPFeedError):
        fetch_breaches()


@respx.mock
def test_fetch_breaches_erro_conexao_levanta_hibp_feed_error():
    respx.get(settings.hibp_api_url).mock(side_effect=httpx.ConnectError("conexão recusada"))

    with pytest.raises(HIBPFeedError):
        fetch_breaches()


@respx.mock
def test_fetch_breaches_status_500_levanta_hibp_feed_error():
    respx.get(settings.hibp_api_url).mock(return_value=httpx.Response(500))

    with pytest.raises(HIBPFeedError):
        fetch_breaches()


@respx.mock
def test_fetch_breaches_json_invalido_levanta_hibp_feed_error():
    respx.get(settings.hibp_api_url).mock(
        return_value=httpx.Response(200, content="isto nao e json")
    )

    with pytest.raises(HIBPFeedError):
        fetch_breaches()


@respx.mock
def test_fetch_breaches_json_nao_lista_levanta_hibp_feed_error():
    respx.get(settings.hibp_api_url).mock(
        return_value=httpx.Response(200, json={"erro": "nao e uma lista"})
    )

    with pytest.raises(HIBPFeedError):
        fetch_breaches()
