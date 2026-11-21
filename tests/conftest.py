"""Regression tests are offline even when developers configure real credentials."""

import httpx
import pytest


@pytest.fixture(autouse=True)
def block_real_http(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Tests must use MockTransport; real HTTP is disabled")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", reject)
