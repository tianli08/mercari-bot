# PROJECT.md - Discord Marketplace Monitor Bot (Mercari-first, Rakuma/Rakuten planned)

Adding app .exe functionality so that users can add to their own discord along with plan own keywords for search.

Currently setting ai datasets for only fashion items. Other items will not have the chance to be filtered.

## Project Overview
This repository currently contains a **Python-based Discord bot** focused on **Mercari Japan**. It polls Mercari search pages for **newly listed items** matching configured keywords and posts alerts to Discord.  
Rakuma and Rakuten are part of the planned direction, but are **not implemented yet** beyond placeholder constants and roadmap notes.

**Core Goal**: Enable users to catch "fresh drops" quickly (e.g., rare collectibles, limited sneakers, vintage fashion, electronics) before they're sold out.

**Current State** (as of March 2026):
- Working Mercari-only bot using **Selenium + discord.py**.
- Keywords are loaded from static JSON config (`config/config.json`), not per-user watchlists.
- Mercari search URLs are generated with newest-first sorting, then polled sequentially in a loop.
- New listings are deduplicated in MongoDB by listing URL and sent to fixed Discord channels.
- Alerts currently include title, image, Mercari URL, and a Buyee proxy link when derivable.
- A partial refactor exists under `src/data`, `src/models`, `src/scrapers`, `src/services`, and `prisma/`, but that path is not the main runtime yet.
- Not implemented yet: multi-marketplace scraping, slash commands for watchlists, proxy rotation, stealth hardening, CAPTCHA handling, centralized scheduling, or per-user alert preferences.

**Target Scale** (planned, not current capability):
- ~20 searches per minute total (across all keywords/users).
- Only care about **newest posted items** — poll sorted by "newest" / latest first.
- Focus on first 1–2 pages per search (Mercari often caps results at ~600 items total anyway; new listings appear early).
- Users manage their own watchlists (keywords, price filters?, categories?, Discord mention preferences).

## Key Technical Requirements & Architecture Goals

### Database (MongoDB)
**Current implementation**:
- MongoDB is used for simple deduplication of seen Mercari listings.
- The active runtime stores a small record keyed by listing URL with basic item metadata.
- A newer Prisma Mongo schema exists for `ProductLink`, but it is not the primary runtime path yet.

**Target design**:
- Store:
  - User watchlists: user_id (Discord), keywords list, optional filters (min/max price, category, condition), channel_id for alerts.
  - Seen items: item_id (Mercari/Rakuma/etc.), title, url, posted_timestamp, price, thumbnail, keyword_matched.
  - Deduplication: prevent duplicate alerts (key on item_id + marketplace).
  - Proxy stats: success/failure rates, last ban time (if using rotating proxies).
  - Bot config: global rate limits, polling intervals.

### Scraping Engine
**Current implementation**:
- Selenium with headless Chrome is used for Mercari scraping.
- The scraper extracts listing URL, image, title, and raw text content from Mercari item cards.
- The current code only targets Mercari JP.

**Target design**:
- **Selenium** (headless Chrome/undetected-chromedriver or Playwright) for reliability — Mercari JP heavily uses JS, dynamic loading, and anti-bot.
- **Targets**:
  - Mercari JP: https://jp.mercari.com (primary)
  - Rakuma (Fril): https://item.fril.jp (or rakuma.fril.jp)
  - Rakuten (various shops/auctions — focus on relevant sections)
- **Search Strategy**:
  - Sort by newest: Use URL params like `?sort=newest` or `sort_order=desc_created_time` (verify current exact param via browser dev tools — structure changes occasionally).
  - Poll **first page only** (or first 2 max) per keyword.
  - Extract: item ID, title, price, URL, thumbnail, posted time (relative → convert to absolute), condition, seller info if available.
- **Deduplication**: Hash or store item_id + timestamp; alert only on new items since last poll.

### Scheduling & Concurrency
**Current implementation**:
- A single Discord bot task loops forever, reuses one Selenium driver, and scans all configured Mercari URLs sequentially.
- The current delay is randomized to roughly 60-120 seconds per cycle, not 8-15 seconds per keyword.

**Target design**:
- **Centralized scheduler**: Use APScheduler, Celery (with Redis/Mongo beat), or asyncio-based loop.
- Distribute load: Per-keyword queues, round-robin across proxies/sessions.
- **Polling frequency**:
  - Target: ~25 total searches/minute.
  - Per-keyword: 1 request every 8–15 seconds (with jitter: e.g., base 10s ± random 2–8s).
  - Supports ~10–20 active keywords comfortably at this rate.
  - Start conservative (10–15/min total) → monitor → ramp up.

### Anti-Ban & Rate Limit Mitigation (Critical!)
Mercari JP has **no public/hard rate limit** — it's **behavior-based anti-bot**:
- Aggressive fingerprinting: user-agent, headers, JS execution, mouse/scroll patterns, IP reputation.
- Common blocks: 429 Too Many Requests, CAPTCHA, soft IP bans, reduced results.
- robots.txt: Disallows /mypage/, /purchase/, etc. — search/browse pages generally allowed, no Crawl-delay.

**Current implementation gap**:
- The current bot only uses basic headless Chrome options and randomized polling delay.
- It does **not** yet implement stealth tooling, rotating proxies, adaptive throttling, CAPTCHA solving, or proxy health monitoring.

**Target strategies**:
1. **Japanese residential proxies** (not datacenter/AWS alone — Mercari detects AWS ranges fast).
   - Rotate every 1–5 requests or per keyword session.
   - Providers: Bright Data, Oxylabs, Smartproxy, SOAX, IPRoyal, NetNut, 911Proxy (Japan-targeted residential).
   - Budget: $50–200+/month depending on volume/GB.
   - Sticky sessions: 1–10 min if possible.
2. **Browser Stealth**:
   - undetected-chromedriver / Playwright stealth.
   - Rotate user-agents (Japanese browser strings).
   - Set timezone Asia/Tokyo, Accept-Language: ja,en-US;q=0.9.
   - Random waits, light scrolling, human-like navigation.
   - Fresh profiles/cookies per session.
3. **Rate Limiting in Code**:
   - `asyncio.sleep(random.uniform(8, 15))` or ratelimit lib.
   - Exponential backoff on 429/CAPTCHA (tenacity/backoff lib).
   - Dynamic throttling: reduce rate if error rate >5–10%.
4. **CAPTCHA Handling** (last resort): 2Captcha/Anti-Captcha integration.
5. **Monitoring**: Log success/failure per proxy → pause bad ones → Discord webhook alerts on high errors.

### Discord Integration
**Current implementation**:
- Uses `discord.py` with a fixed bot token and fixed channel IDs from environment/config.
- Sends embeds for newly detected Mercari items.
- Includes a persistent "Save Item" button that forwards the embed to a saved-items channel.
- Does not currently expose slash commands or user-managed watchlists.

**Target design**:
- Commands: /watch add keyword, /watch list, /watch remove, /watch set_channel.
- Alerts: Embed with title, price, URL, thumbnail, posted time, matched keyword.
- Mention user/role if configured.
- Use discord.py or nextcord.

## Development Guidelines
- Python 3.13 currently required by `pyproject.toml`.
- Current libs in use: `selenium`, `discord.py`, `motor`, `pydantic`, `pydantic-settings`, `pymongo`.
- Planned additions likely include: Playwright or undetected-chromedriver, APScheduler or Celery, tenacity/backoff, fake-useragent.
- Docker/deployment setup is not defined yet.
- Logging is currently basic stdlib logging rather than structured `structlog`.
- Testing is currently minimal and focused on utility helpers, with parser/integration coverage still to be built.

## Roadmap / Next Steps
1. Clean up the split between the current runtime path and the partial refactor so there is one clear application entrypoint.
2. Implement MongoDB schema & user watchlist CRUD.
3. Build keyword → search URL generators per marketplace.
4. Expand the Mercari scraper to capture stronger metadata, then add Rakuma/Rakuten support.
5. Replace the sequential loop with a scheduler/queue model that can scale safely.
6. Add stealth, proxy rotation, throttling, and failure monitoring.
7. Add Discord slash commands and per-user/channel alert preferences.
8. Test at low volume, measure scrape reliability, then scale toward the target request rate.
