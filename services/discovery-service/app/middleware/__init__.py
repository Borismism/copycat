"""Middleware for the discovery service."""

from .logging import RequestLoggingMiddleware, setup_logging

__all__ = ["RequestLoggingMiddleware", "setup_logging"]
