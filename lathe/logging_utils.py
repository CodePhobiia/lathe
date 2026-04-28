"""Structured logging helpers with secret redaction."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from .security import redact_secrets


def redact_log_value(value: Any) -> Any:
    """Return a JSON-friendly log value with sensitive material removed."""
    if isinstance(value, BaseException):
        return {
            "type": type(value).__name__,
            "message": redact_secrets(str(value)),
        }
    if isinstance(value, Path | os.PathLike):
        return redact_secrets(str(value))
    return redact_secrets(value)


def _message_value(value: Any) -> str:
    if isinstance(value, BaseException):
        return str(redact_secrets(str(value)))
    redacted = redact_log_value(value)
    if isinstance(redacted, dict | list | tuple):
        return json.dumps(redacted, sort_keys=True, default=str)
    return str(redacted)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    template: str,
    **details: Any,
) -> None:
    """Emit a structured Lathe log record after redacting dynamic fields."""
    safe_details = {key: redact_log_value(value) for key, value in details.items()}
    message_fields = {key: _message_value(value) for key, value in details.items()}
    try:
        rendered = template.format(**message_fields)
    except (IndexError, KeyError, ValueError):
        rendered = template
    logger.log(level, rendered, extra={"lathe_event": event, "lathe_details": safe_details})


def debug(logger: logging.Logger, event: str, template: str, **details: Any) -> None:
    """Emit a redacted structured debug log."""
    log_event(logger, logging.DEBUG, event, template, **details)


def info(logger: logging.Logger, event: str, template: str, **details: Any) -> None:
    """Emit a redacted structured info log."""
    log_event(logger, logging.INFO, event, template, **details)


def warning(logger: logging.Logger, event: str, template: str, **details: Any) -> None:
    """Emit a redacted structured warning log."""
    log_event(logger, logging.WARNING, event, template, **details)


def error(logger: logging.Logger, event: str, template: str, **details: Any) -> None:
    """Emit a redacted structured error log."""
    log_event(logger, logging.ERROR, event, template, **details)


__all__ = ["debug", "error", "info", "log_event", "redact_log_value", "warning"]
