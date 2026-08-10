# Archive Fashion Monitor & ML Scraper

A high-performance, distributed SaaS application designed to automate the discovery of avant-garde and archival fashion listings across global marketplaces like Mercari. 

This system moves beyond basic keyword matching by utilizing a custom machine learning and computer vision pipeline trained specifically on archival designers (e.g., Carol Christian Poell, Boris Bidjan Saberi, Maison Margiela). It actively filters out noise and low-relevance items, routing high-confidence hits directly to user-configured Discord servers in real time.

## Key Features
* **Intelligent Filtering Pipeline:** Decoupled Python-based scraping engine utilizing Selenium and custom ML datasets to accurately classify niche fashion items.
* **Real-Time Discord Integration:** Instantaneous webhook delivery of targeted listings directly to user-selected servers and channels.
* **SaaS Dashboard:** A scalable web interface for users to authenticate, manage complex keyword matrices, adjust ML confidence thresholds, and configure brand-specific drop-down parameters.
* **Distributed Architecture:** Asynchronous task processing utilizing Celery and Redis to handle concurrent scraping tasks and ML inference without blocking API operations.

## Running the backend services

Run commands from `backend/`. The worker and API are separate processes that share MongoDB:

- Worker: `uv run python -m src.main`
- API (development): `uv run uvicorn src.api.app:app --reload`
- API (settings-based host and port): `uv run python -m src.api_main`

### Authentication configuration

The API exposes `POST /api/v1/auth/signup`, `POST /api/v1/auth/login`,
`POST /api/v1/auth/logout`, and `GET /api/v1/auth/me`. Signup creates an
active account and starts a session. Login is limited to active accounts;
pending and suspended accounts receive the same generic credential error.
Sessions use an expiring JWT in an `HttpOnly` cookie, and rotating the signing
secret signs all users out.

Set these environment variables before importing or starting the backend:

- `JWT_SECRET`: required signing secret containing at least 32 characters.
  Generate a development value with
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `JWT_TOKEN_LIFETIME_SECONDS`: session lifetime from 60 to 86400 seconds
  (default `3600`).
- `AUTH_COOKIE_NAME`: cookie name (default `mercari_session`).
- `AUTH_COOKIE_SECURE`: use `false` only for local HTTP development; production
  requires `true`.
- `AUTH_COOKIE_SAMESITE`: `lax` by default; `none` is accepted only with a
  secure cookie and requires a separately designed CSRF defense before
  authenticated mutations are deployed cross-site.
- `API_ENVIRONMENT`: `development`, `test`, or `production`. Production
  refuses to start unless secure cookies are enabled.
- `JWT_ISSUER` and `JWT_AUDIENCE`: optional expected token metadata with
  defaults for this API and dashboard.

Password inputs must be 12–128 characters. The API stores only Argon2id hashes
and never returns password hashes or raw session tokens.

### Tenant resource API

Authenticated clients can manage watchlists and Discord destinations under
`/api/v1`. Tenant identity always comes from the signed session cookie; request
bodies do not accept owner or tenant fields, and missing and foreign-owned IDs
both return `404`.

- Watchlists: `POST/GET /watchlists`, `GET/PATCH/DELETE /watchlists/{id}`
- Keywords: `POST/DELETE /watchlists/{id}/keywords` and
  `POST /watchlists/{id}/keywords/from-preset`
- Monitoring: `PATCH /watchlists/{id}/monitoring`
- Presets: `GET /presets` (enabled catalog entries only)
- Destinations: `POST/GET /destinations`,
  `GET/PATCH/DELETE /destinations/{id}`, and
  `POST /destinations/{id}/verify`
- Recent alerts: `GET /alerts/recent?limit=20&cursor=...`

Destination responses contain labels, timestamps, type, and verification
state only. Discord webhook URLs are encrypted at rest and are never returned,
including in masked form. The recent-alert feed contains sent alerts only,
sorts newest first by creation time and ID, and uses an opaque cursor with a
maximum page size of 100.
