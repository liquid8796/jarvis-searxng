# SearXNG Vercel Serverless Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deployable ZIP that runs the upstream SearXNG Flask app as an experimental stateless Vercel Python Function.

**Architecture:** A small runtime adapter validates environment configuration before importing `searx.webapp.app`. A project-local PEP 517 backend downloads and builds the pinned upstream source without requiring a custom Vercel install command. A project-local settings file disables stateful and public-instance features, and Vercel rewrites every path to the WSGI entrypoint.

**Tech Stack:** Python 3.13, Flask/WSGI via upstream SearXNG, YAML, Vercel Functions, pytest.

## Global Constraints

- Pin SearXNG to upstream commit `c19d86faa`.
- Require `SEARXNG_SECRET` with at least 32 characters.
- Do not use Valkey/Redis.
- Disable limiter, public-instance mode, image proxy, metrics, and autocomplete.
- Support HTML and JSON search formats.
- Do not claim that live Vercel deployment or upstream searches were verified without network access.

---

### Task 1: Runtime configuration adapter

**Files:**
- Create: `tests/test_runtime.py`
- Create: `api/runtime.py`

**Interfaces:**
- Produces: `configure_environment(environ: MutableMapping[str, str] | None = None) -> Path`

- [x] Write tests for default settings-path resolution, preserving an explicit path, missing settings file, missing secret, weak secret, and valid environment.
- [x] Run tests and confirm they fail because `api.runtime` is missing.
- [x] Implement the minimal runtime adapter.
- [x] Run tests and confirm they pass.

### Task 2: WSGI entrypoint and SearXNG configuration

**Files:**
- Create: `api/__init__.py`
- Create: `api/index.py`
- Create: `config/settings.yml`
- Create: `requirements.txt`
- Create: `vendor/searxng_source/pyproject.toml`
- Create: `vendor/searxng_source/build_backend.py`
- Create: `tests/test_build_backend.py`
- Create: `.python-version`
- Create: `vercel.json`
- Create: `.vercelignore`
- Create: `.gitignore`
- Create: `.env.example`

**Interfaces:**
- Consumes: `configure_environment()` from Task 1.
- Produces: top-level WSGI variable `app`.

- [x] Add the upstream application import only after runtime configuration succeeds.
- [x] Register `/healthz` and add no-store response headers.
- [x] Add stateless SearXNG settings and Vercel routing/runtime configuration.
- [x] Pin the upstream dependency and Python version.
- [x] Add a tested PEP 517 wrapper that safely downloads and builds the pinned source archive.

### Task 3: Verification and documentation

**Files:**
- Create: `scripts/verify.py`
- Create: `tests/test_verify.py`
- Create: `README.md`
- Create: `LICENSE-NOTICE.md`

**Interfaces:**
- Produces: `verify_project(root: Path) -> list[str]` and a CLI returning non-zero on validation failures.

- [x] Write failing tests for required-file checks and safe configuration validation.
- [x] Implement verification logic and run tests.
- [x] Document local setup, Vercel deployment, environment variables, API usage, limitations, and troubleshooting.
- [x] Run syntax, unit, and project verification checks.
- [x] Create a clean ZIP with `searxng-vercel/` as the archive root.
