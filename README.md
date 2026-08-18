Static Archive fullstack app.

Searches Mercari for archive fashion listings (Carol Christian Poell, Boris Bidjan Saberi, Margiela, etc.) and posts matches to Discord. Each user signs up on the dashboard, sets up watchlists of keywords, and gets alerts sent to their own Discord webhooks.

The repo has three parts:

- `backend/` – the scraper worker and the FastAPI app, sharing MongoDB
- `web/` – the dashboard frontend
- `infra/` – deployment config

## Running the backend

Everything runs with [uv](https://docs.astral.sh/uv/) from `backend/`:

```bash
# scraper worker
uv run python -m src.main

# API, dev mode with reload
uv run uvicorn src.api.app:app --reload

# API, host/port from settings
uv run python -m src.api_main
```

The worker and the API are separate processes. Both need MongoDB.

## Auth

The API has `POST /api/v1/auth/signup`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, and `GET /api/v1/auth/me`. Signup creates an active account and starts a session. Login only works for active accounts; pending and suspended accounts get the same generic credential error so you can't probe account state.

Sessions are an expiring JWT in an `HttpOnly` cookie. Rotating the signing secret logs everyone out.

Environment variables (set these before starting anything):

- `JWT_SECRET` – required, at least 32 characters. For local dev:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `JWT_TOKEN_LIFETIME_SECONDS` – 60 to 86400, default `3600`
- `AUTH_COOKIE_NAME` – default `mercari_session`
- `AUTH_COOKIE_SECURE` – only set `false` for local HTTP dev; production requires `true`
- `AUTH_COOKIE_SAMESITE` – default `lax`. `none` only works with a secure cookie, and don't use it cross-site without a real CSRF defense in place first
- `API_ENVIRONMENT` – `development`, `test`, or `production`. Production refuses to start without secure cookies
- `JWT_ISSUER` / `JWT_AUDIENCE` – optional, have sensible defaults

Passwords are 12–128 characters, stored as Argon2id hashes. The API never returns hashes or raw session tokens.

## Tenant API

Logged-in users manage their own watchlists and Discord destinations under `/api/v1`. The tenant always comes from the session cookie — request bodies don't take owner/tenant fields, and both missing and foreign-owned IDs come back as `404`.

- Watchlists: `POST/GET /watchlists`, `GET/PATCH/DELETE /watchlists/{id}`
- Keywords: `POST/DELETE /watchlists/{id}/keywords`, `POST /watchlists/{id}/keywords/from-preset`
- Monitoring: `PATCH /watchlists/{id}/monitoring`
- Presets: `GET /presets` (enabled catalog entries only)
- Destinations: `POST/GET /destinations`, `GET/PATCH/DELETE /destinations/{id}`, `POST /destinations/{id}/verify`
- Recent alerts: `GET /alerts/recent?limit=20&cursor=...`

Webhook URLs are encrypted at rest and never returned by the API, not even masked. Destination responses only include the label, type, timestamps, and verification state. The alerts feed is sent alerts only, newest first, opaque cursor, max page size 100.

## Currently INFRA and WEB are being developed.