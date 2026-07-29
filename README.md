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
