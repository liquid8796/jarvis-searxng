from __future__ import annotations

import os
from collections.abc import MutableMapping
from pathlib import Path

MINIMUM_SECRET_LENGTH = 32
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yml"


def configure_environment(
    environ: MutableMapping[str, str] | None = None,
) -> Path:
    """Validate and prepare environment variables before importing SearXNG."""
    target = os.environ if environ is None else environ

    secret = target.get("SEARXNG_SECRET", "")
    if not secret:
        raise RuntimeError(
            "SEARXNG_SECRET is required. Configure it in Vercel Environment Variables."
        )
    if len(secret) < MINIMUM_SECRET_LENGTH:
        raise RuntimeError("SEARXNG_SECRET must contain at least 32 characters.")

    configured_path = target.get("SEARXNG_SETTINGS_PATH")
    settings_path = (
        Path(configured_path).expanduser().resolve()
        if configured_path
        else DEFAULT_SETTINGS_PATH.resolve()
    )
    if not settings_path.is_file():
        raise RuntimeError(f"SearXNG settings file does not exist: {settings_path}")

    target["SEARXNG_SETTINGS_PATH"] = str(settings_path)
    target["SEARXNG_LIMITER"] = "false"
    target["SEARXNG_IMAGE_PROXY"] = "false"
    target["SEARXNG_PUBLIC_INSTANCE"] = "false"
    target["SEARXNG_METHOD"] = "GET"

    return settings_path
