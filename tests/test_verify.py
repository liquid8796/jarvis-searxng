from __future__ import annotations

import json
from pathlib import Path

from scripts.verify import verify_project


def write_valid_project(root: Path) -> None:
    files = {
        "api/index.py": "app = object()\n",
        "api/runtime.py": "def configure_environment():\n    return None\n",
        "config/settings.yml": """
use_default_settings: true
general:
  enable_metrics: false
search:
  autocomplete: ""
  formats: [html, json]
server:
  limiter: false
  public_instance: false
  image_proxy: false
  method: GET
valkey:
  url: false
""".lstrip(),
        "requirements.txt": "./vendor/searxng_source\n",
        "vendor/searxng_source/pyproject.toml": """
[build-system]
requires = ["setuptools", "PyYAML==6.0.3", "msgspec==0.21.1"]
build-backend = "build_backend"
backend-path = ["."]
""".lstrip(),
        "vendor/searxng_source/build_backend.py": (
            'UPSTREAM_REF = "c19d86faa"\n'
            'UPSTREAM_ARCHIVE_URL = "https://codeload.github.com/searxng/searxng/tar.gz/" + UPSTREAM_REF\n'
        ),
        "vercel.json": json.dumps(
            {
                "functions": {
                    "api/index.py": {
                        "maxDuration": 60,
                        "includeFiles": "config/settings.yml",
                    }
                },
                "rewrites": [
                    {"source": "/(.*)", "destination": "/api/index"}
                ],
            }
        ),
        ".python-version": "3.13\n",
        ".env.example": "SEARXNG_SECRET=replace-me\n",
        "README.md": "# Test project\n",
        "LICENSE-NOTICE.md": "# License notice\n",
    }
    for relative_path, content in files.items():
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


def test_verify_project_accepts_valid_project(tmp_path: Path) -> None:
    write_valid_project(tmp_path)

    assert verify_project(tmp_path) == []


def test_verify_project_reports_missing_required_file(tmp_path: Path) -> None:
    write_valid_project(tmp_path)
    (tmp_path / "README.md").unlink()

    errors = verify_project(tmp_path)

    assert "Missing required file: README.md" in errors


def test_verify_project_rejects_stateful_or_public_settings(tmp_path: Path) -> None:
    write_valid_project(tmp_path)
    (tmp_path / "config/settings.yml").write_text(
        """
use_default_settings: true
general:
  enable_metrics: true
search:
  autocomplete: duckduckgo
  formats: [html]
server:
  limiter: true
  public_instance: true
  image_proxy: true
  method: POST
valkey:
  url: valkey://localhost:6379/0
""".lstrip(),
        encoding="utf-8",
    )

    errors = verify_project(tmp_path)

    assert any("general.enable_metrics must be false" in error for error in errors)
    assert any("search.autocomplete must be disabled" in error for error in errors)
    assert any("search.formats must include html and json" in error for error in errors)
    assert any("server.limiter must be false" in error for error in errors)
    assert any("server.public_instance must be false" in error for error in errors)
    assert any("server.image_proxy must be false" in error for error in errors)
    assert any("server.method must be GET" in error for error in errors)
    assert any("valkey.url must be false" in error for error in errors)


def test_verify_project_rejects_unpinned_upstream_dependency(tmp_path: Path) -> None:
    write_valid_project(tmp_path)
    (tmp_path / "vendor/searxng_source/build_backend.py").write_text(
        'UPSTREAM_REF = "master"\n',
        encoding="utf-8",
    )

    errors = verify_project(tmp_path)

    assert any("must pin upstream commit c19d86faa" in error for error in errors)


def test_verify_project_requires_settings_in_function_bundle(tmp_path: Path) -> None:
    write_valid_project(tmp_path)
    config = json.loads((tmp_path / "vercel.json").read_text(encoding="utf-8"))
    del config["functions"]["api/index.py"]["includeFiles"]
    (tmp_path / "vercel.json").write_text(json.dumps(config), encoding="utf-8")

    errors = verify_project(tmp_path)

    assert any("include config/settings.yml" in error for error in errors)


def test_verify_project_requires_local_build_wrapper(tmp_path: Path) -> None:
    write_valid_project(tmp_path)
    (tmp_path / "requirements.txt").write_text(
        "searxng @ git+https://github.com/searxng/searxng.git@c19d86faa\n",
        encoding="utf-8",
    )

    errors = verify_project(tmp_path)

    assert any("local SearXNG build wrapper" in error for error in errors)
