"""Shared logging helpers for terminal-friendly bot output."""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from typing import Any

LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(component)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ComponentFormatter(logging.Formatter):
    """Formatter that guarantees every record has a component tag."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a record, defaulting missing component tags to the logger name."""
        if not hasattr(record, "component"):
            record.component = record.name
        return super().format(record)


class ContextLoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    """Logger adapter that appends compact key-value context to messages."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Add component and structured context before emitting a log record."""
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("component", self.extra["component"])

        context = kwargs.pop("context", None)
        if context:
            msg = f"{msg} {format_context(context)}"
        return msg, kwargs


def configure_logging(level_name: str = "INFO") -> None:
    """Configure process-wide logging for the bot."""
    level = logging.getLevelNamesMapping().get(level_name.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ComponentFormatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    logging.captureWarnings(True)


def get_logger(component: str) -> ContextLoggerAdapter:
    """Return a logger bound to a terminal component tag."""
    return ContextLoggerAdapter(logging.getLogger("mercari_bot"), {"component": component})


def log_exception(
    logger: ContextLoggerAdapter,
    message: str,
    exc: BaseException,
    **context: object,
) -> None:
    """Log an error with exception type, message, context, and traceback."""
    logger.error(
        f"{message}: {type(exc).__name__}: {exc}",
        exc_info=(type(exc), exc, exc.__traceback__),
        context=context,
    )


def format_context(context: Mapping[str, object]) -> str:
    """Format context as stable key=value pairs for terminal scanning."""
    parts: list[str] = []
    for key, value in context.items():
        if value is None:
            continue
        text = str(value).replace("\n", "\\n")
        if any(character.isspace() for character in text):
            text = repr(text)
        parts.append(f"{key}={text}")
    return " ".join(parts)
