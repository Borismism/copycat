"""Structured JSON logging utilities for Cloud Run.

Cloud Run splits logs by newline, creating separate log entries.
This module provides utilities to log exceptions as single JSON entries.
"""

import json
import logging
import traceback
from typing import Any


def log_exception_json(
    logger: logging.Logger,
    message: str,
    exc: Exception,
    severity: str = "ERROR",
    **extra_fields: Any
) -> None:
    """
    Log an exception as a single structured JSON entry for Cloud Run.

    Cloud Run will keep this as ONE log entry and Error Reporting will
    properly parse the stack trace.

    Args:
        logger: Logger instance to use
        message: Human-readable error message
        exc: The exception to log
        severity: Log severity (ERROR, WARNING, etc.)
        **extra_fields: Additional fields to include in jsonPayload

    Example:
        log_exception_json(
            logger,
            "Failed to process video",
            exc,
            video_id="abc123",
            service="vision-analyzer"
        )
    """
    # Get the full stack trace as a single string
    stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    # Build the structured log entry
    log_entry = {
        "severity": severity,
        "message": f"{message}: {exc!s}",
        "stack_trace": stack_trace,
        "exception": {
            "type": type(exc).__name__,
            "message": str(exc),
        },
        **extra_fields
    }

    # Log as a single JSON line (Cloud Run won't split this)
    logger.error(json.dumps(log_entry))


def format_exception_for_response(exc: Exception) -> str:
    """
    Format exception for HTTP response (user-facing).

    Returns a clean error message without exposing full stack traces
    to end users.
    """
    return f"{type(exc).__name__}: {exc!s}"
