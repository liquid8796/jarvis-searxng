from __future__ import annotations

from pathlib import Path

import pytest

from api.runtime import configure_environment


def test_configure_environment_sets_project_settings_path(monkeypatch: pytest.MonkeyPatch) -> None:
    environ = {"SEARXNG_SECRET": "x" * 32}

    settings_path = configure_environment(environ)

    assert settings_path == Path(__file__).resolve().parents[1] / "config" / "settings.yml"
    assert environ["SEARXNG_SETTINGS_PATH"] == str(settings_path)


def test_configure_environment_preserves_explicit_settings_path(tmp_path: Path) -> None:
    custom_settings = tmp_path / "settings.yml"
    custom_settings.write_text("use_default_settings: true\n", encoding="utf-8")
    environ = {
        "SEARXNG_SECRET": "s" * 32,
        "SEARXNG_SETTINGS_PATH": str(custom_settings),
    }

    settings_path = configure_environment(environ)

    assert settings_path == custom_settings.resolve()
    assert environ["SEARXNG_SETTINGS_PATH"] == str(custom_settings)


def test_configure_environment_rejects_missing_settings_file(tmp_path: Path) -> None:
    environ = {
        "SEARXNG_SECRET": "s" * 32,
        "SEARXNG_SETTINGS_PATH": str(tmp_path / "missing.yml"),
    }

    with pytest.raises(RuntimeError, match="settings file does not exist"):
        configure_environment(environ)


def test_configure_environment_rejects_missing_secret() -> None:
    with pytest.raises(RuntimeError, match="SEARXNG_SECRET is required"):
        configure_environment({})


def test_configure_environment_rejects_weak_secret() -> None:
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        configure_environment({"SEARXNG_SECRET": "too-short"})


def test_configure_environment_applies_serverless_safety_overrides() -> None:
    environ = {"SEARXNG_SECRET": "z" * 32}

    configure_environment(environ)

    assert environ["SEARXNG_LIMITER"] == "false"
    assert environ["SEARXNG_IMAGE_PROXY"] == "false"
    assert environ["SEARXNG_PUBLIC_INSTANCE"] == "false"
    assert environ["SEARXNG_METHOD"] == "GET"
