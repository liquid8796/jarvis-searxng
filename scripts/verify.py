from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

import yaml

PINNED_COMMIT = "c19d86faa"
PROJECT_VERSION = "1.0.4"
LOCAL_SEARXNG_REQUIREMENT = "searxng @ ./vendor/searxng_source"
REQUIRED_FILES = (
    "api/index.py",
    "api/runtime.py",
    "api/version.py",
    "config/settings.yml",
    "requirements.txt",
    "vendor/searxng_source/pyproject.toml",
    "vendor/searxng_source/build_backend.py",
    "vercel.json",
    ".python-version",
    ".env.example",
    "README.md",
    "LICENSE-NOTICE.md",
)


def _read_yaml(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"Invalid YAML in {path.relative_to(path.parents[1])}: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append("config/settings.yml must contain a YAML mapping")
        return {}
    return parsed


def _read_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid JSON in vercel.json: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append("vercel.json must contain a JSON object")
        return {}
    return parsed


def _nested(settings: dict[str, Any], section: str, key: str) -> Any:
    value = settings.get(section, {})
    return value.get(key) if isinstance(value, dict) else None


def _verify_settings(settings: dict[str, Any], errors: list[str]) -> None:
    if settings.get("use_default_settings") is not True:
        errors.append("use_default_settings must be true")
    if _nested(settings, "general", "enable_metrics") is not False:
        errors.append("general.enable_metrics must be false")
    if _nested(settings, "search", "autocomplete") not in ("", False, None):
        errors.append("search.autocomplete must be disabled")

    formats = _nested(settings, "search", "formats")
    if not isinstance(formats, list) or not {"html", "json"}.issubset(set(formats)):
        errors.append("search.formats must include html and json")

    for key in ("limiter", "public_instance", "image_proxy"):
        if _nested(settings, "server", key) is not False:
            errors.append(f"server.{key} must be false")
    if str(_nested(settings, "server", "method")).upper() != "GET":
        errors.append("server.method must be GET")
    if _nested(settings, "valkey", "url") is not False:
        errors.append("valkey.url must be false")


def _read_assigned_string(path: Path, name: str, errors: list[str]) -> str | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        errors.append(f"Invalid Python syntax in {path}: {exc}")
        return None

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Name)
            and target.id == name
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


def _verify_requirements(root: Path, errors: list[str]) -> None:
    requirements_path = root / "requirements.txt"
    requirement_lines = {
        line.strip()
        for line in requirements_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if LOCAL_SEARXNG_REQUIREMENT not in requirement_lines:
        errors.append(
            "requirements.txt must install the local SearXNG build wrapper "
            "and declare distribution name searxng"
        )

    backend_path = root / "vendor/searxng_source/build_backend.py"
    upstream_ref = _read_assigned_string(backend_path, "UPSTREAM_REF", errors)
    if upstream_ref != PINNED_COMMIT:
        errors.append(f"build wrapper must pin upstream commit {PINNED_COMMIT}")

    backend_source = backend_path.read_text(encoding="utf-8")
    if "write_frozen_version(source_root)" not in backend_source:
        errors.append("build wrapper must generate searx.version_frozen")

    pyproject = (root / "vendor/searxng_source/pyproject.toml").read_text(
        encoding="utf-8"
    )
    if 'build-backend = "build_backend"' not in pyproject:
        errors.append("build wrapper must use build_backend as its PEP 517 backend")


def _verify_vercel(config: dict[str, Any], errors: list[str]) -> None:
    functions = config.get("functions")
    function_config = functions.get("api/index.py") if isinstance(functions, dict) else None
    if not isinstance(function_config, dict):
        errors.append("vercel.json must configure functions.api/index.py")
    elif not isinstance(function_config.get("maxDuration"), int):
        errors.append("vercel.json must set an integer maxDuration for api/index.py")
    elif "config/settings.yml" not in str(function_config.get("includeFiles", "")):
        errors.append("vercel.json must include config/settings.yml in the function bundle")

    rewrites = config.get("rewrites")
    expected_rewrite = {"source": "/(.*)", "destination": "/api/index"}
    if not isinstance(rewrites, list) or expected_rewrite not in rewrites:
        errors.append("vercel.json must rewrite /(.*) to /api/index")


def _verify_python_syntax(root: Path, errors: list[str]) -> None:
    for relative_path in ("api/index.py", "api/runtime.py", "api/version.py"):
        path = root / relative_path
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except (OSError, SyntaxError) as exc:
            errors.append(f"Invalid Python syntax in {relative_path}: {exc}")


def verify_project(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []

    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    errors.extend(f"Missing required file: {relative}" for relative in missing)
    if missing:
        return errors

    _verify_settings(_read_yaml(root / "config/settings.yml", errors), errors)
    _verify_requirements(root, errors)
    _verify_vercel(_read_json(root / "vercel.json", errors), errors)
    _verify_python_syntax(root, errors)

    project_version = _read_assigned_string(
        root / "api/version.py", "PROJECT_VERSION", errors
    )
    if project_version != PROJECT_VERSION:
        errors.append(f"project version must be {PROJECT_VERSION}")

    if (root / ".python-version").read_text(encoding="utf-8").strip() != "3.13":
        errors.append(".python-version must be 3.13")
    if "SEARXNG_SECRET=" not in (root / ".env.example").read_text(encoding="utf-8"):
        errors.append(".env.example must document SEARXNG_SECRET")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = verify_project(root)
    if errors:
        print("Project verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Project verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
