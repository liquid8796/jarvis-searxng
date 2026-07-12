from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass, field
from typing import Any, Callable

import pytest


@dataclass
class FakeApp:
    routes: dict[str, Callable[..., Any]] = field(default_factory=dict)
    after_request_handlers: list[Callable[..., Any]] = field(default_factory=list)

    def get(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.routes[path] = func
            return func

        return decorator

    def after_request(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self.after_request_handlers.append(func)
        return func


class FakeHeaders(dict[str, str]):
    pass


@dataclass
class FakeResponse:
    headers: FakeHeaders = field(default_factory=FakeHeaders)


def import_index(monkeypatch: pytest.MonkeyPatch) -> tuple[types.ModuleType, FakeApp]:
    fake_app = FakeApp()
    searx_module = types.ModuleType("searx")
    webapp_module = types.ModuleType("searx.webapp")
    webapp_module.app = fake_app
    searx_module.webapp = webapp_module

    monkeypatch.setenv("SEARXNG_SECRET", "s" * 32)
    monkeypatch.setitem(sys.modules, "searx", searx_module)
    monkeypatch.setitem(sys.modules, "searx.webapp", webapp_module)
    sys.modules.pop("api.index", None)

    return importlib.import_module("api.index"), fake_app


def test_index_exports_upstream_wsgi_app(monkeypatch: pytest.MonkeyPatch) -> None:
    module, fake_app = import_index(monkeypatch)

    assert module.app is fake_app


def test_healthz_reports_service_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _, fake_app = import_index(monkeypatch)

    payload, status = fake_app.routes["/healthz"]()

    assert status == 200
    assert payload == {"service": "searxng-vercel", "status": "ok"}


def test_after_request_disables_response_caching(monkeypatch: pytest.MonkeyPatch) -> None:
    _, fake_app = import_index(monkeypatch)
    response = FakeResponse()

    result = fake_app.after_request_handlers[0](response)

    assert result is response
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
