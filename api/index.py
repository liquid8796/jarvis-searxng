from __future__ import annotations

from typing import Any

from api.runtime import configure_environment
from api.version import PROJECT_VERSION

configure_environment()

from searx.webapp import app as app  # noqa: E402


@app.get("/healthz")
def healthz() -> tuple[dict[str, str], int]:
    return {
        "service": "searxng-vercel",
        "status": "ok",
        "version": PROJECT_VERSION,
    }, 200


@app.after_request
def add_serverless_response_headers(response: Any) -> Any:
    response.headers.setdefault("Cache-Control", "no-store, max-age=0")
    return response
