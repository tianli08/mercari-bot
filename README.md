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

## Currently INFRA and WEB are being developed.