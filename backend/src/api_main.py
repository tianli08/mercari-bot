"""Service entrypoint for the marketplace monitor FastAPI process."""

from __future__ import annotations

import uvicorn

from .config import settings


def main() -> None:
    """Run the API service with environment-backed host and port settings."""
    uvicorn.run(
        "src.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
