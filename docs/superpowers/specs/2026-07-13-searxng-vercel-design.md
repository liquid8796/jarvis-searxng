# SearXNG on Vercel — Experimental Serverless Design

## Goal

Run the upstream SearXNG Flask application inside a Vercel Python Function as a stateless experimental deployment.

## Architecture

- `api/index.py` is the Vercel WSGI entrypoint and exposes the upstream `searx.webapp.app` Flask application.
- `api/runtime.py` resolves the project-local settings file, validates required environment variables, and configures SearXNG before the upstream application is imported.
- `config/settings.yml` inherits upstream defaults and overrides only serverless-safe settings.
- `vercel.json` rewrites all incoming paths to the Python entrypoint so SearXNG routes and static assets remain reachable.
- `requirements.txt` installs a local PEP 517 build-wrapper. The wrapper downloads the pinned upstream source archive and delegates wheel generation to the upstream setuptools backend with the required build dependencies already isolated.

## Serverless Constraints

- No Valkey/Redis or persistent filesystem state.
- Limiter, public-instance mode, image proxy, metrics, and autocomplete are disabled.
- Search result formats are limited to HTML and JSON.
- Outbound request and connection-pool limits are reduced for a short-lived function runtime.
- `SEARXNG_SECRET` is mandatory and must be supplied through Vercel Environment Variables.
- This is not intended to be a public high-traffic instance.

## Verification

- Unit tests cover environment validation and settings-path resolution without importing SearXNG.
- Unit tests cover the PEP 517 wrapper, including safe archive extraction and upstream hook delegation.
- A verification script checks JSON/YAML syntax, required files, pinning, bundle inclusion, settings safety, and Python syntax.
- Full SearXNG import and live searches require dependency installation and outbound internet access.
