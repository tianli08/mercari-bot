# Architecture (Source of Truth)

> This document supersedes the design sections of `PROJECT.md` for all SaaS work.
> Last updated: Phase 0.

## Product model
- **Centralized, hosted SaaS.** We run all scraping and delivery infrastructure.
  Users never install or run anything locally.
- **Low intended scale** (tens of users), so we deliberately avoid heavy distributed
  systems (no Celery/Redis cluster, no per-user processes, no autoscaling).

## Delivery
- **Discord webhooks.** Each user pastes a webhook URL per destination. No per-user
  bot hosting and no OAuth install required for launch.

## Scraping
- **Shared scrape + fan-out.** Each unique keyword is scraped ONCE from a global,
  deduplicated keyword registry. Matches fan out in-process to every tenant subscribed
  to that keyword. This keeps Mercari request volume proportional to *distinct* demand,
  which is the core anti-ban lever.

## Storage
- **MongoDB is the single store** for everything: users, watchlists, destinations, the
  global keyword registry, canonical listings, and per-destination alert dedupe.

## Runtime topology (target)
- `backend/` Python service, two logical roles sharing one Mongo database:
  1. **Scraper/delivery worker** - the refactored bot engine.
  2. **API** - FastAPI, serves the frontend.
  (At this scale these may run as two processes on one host.)
- `web/` Next.js + Tailwind frontend (landing page + authenticated dashboard).
- `infra/` Docker + deploy configuration.

## Repository layout
- Monorepo: `backend/`, `web/`, `infra/` under one git root.
- Backend run directory is `backend/`; it owns `pyproject.toml`, `uv.lock`,
  `.python-version`, `config/`, and its env files.

## Decisions explicitly deferred
- ML scoring (inserted between scrape-upsert and fan-out - Phase 9).
- Billing/Stripe (only if charging - Phase 8).
- OAuth Discord bot install (webhooks are sufficient for launch).
