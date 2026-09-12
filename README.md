Static Archive fullstack app.

Searches Mercari for archive fashion listings (Carol Christian Poell, Boris Bidjan Saberi, Margiela, etc.) and posts matches to Discord. Each user signs up on the dashboard, sets up watchlists of keywords, and gets alerts sent to their own Discord webhooks.

Everything runs with [uv](https://docs.astral.sh/uv/) from `backend/`:

```bash
# scraper worker
uv run python -m src.main

# API, dev mode with reload
uv run uvicorn src.api.app:app --reload

# API, host/port from settings
uv run python -m src.api_main
```

The web app lives in `web/` (Node 22, npm). API-dependent behavior expects the backend running above. The public landing page lives in `web/src/app/(marketing)/`.

```bash
cd web
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE_URL; default is the local API
npm install
npm run dev                  # http://localhost:3000
npm run build                # production build
```

## Currently INFRA is being developed.

https://www.archivestatic.com/