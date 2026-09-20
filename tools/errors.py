"""Uniform JSON error envelope for the nonogram API.

Implements the cross-repo backend contract (see the website repo at
``docs/api-contract/CONTRACT.md``): every 4xx/5xx response body is::

    {"error": {"code": "<slug>", "message": "<human>", "details": <optional>}}

The HTTP status carries the class; the envelope never restates it. ``code`` is a
stable snake_case slug clients may switch on; ``message`` is human text.
"""

from __future__ import annotations

import logging

from flask import jsonify
from werkzeug.exceptions import HTTPException

from nonogram.errors import ValidationError

_log = logging.getLogger(__name__)

# Stable machine codes for framework-raised HTTP errors (404, 405, 500, ...).
_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "unprocessable_entity",
    429: "rate_limited",
    500: "internal_error",
}


def error_body(code: str, message: str, details=None) -> dict:
    """Build the bare error envelope dict (no HTTP wrapping)."""
    payload: dict = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return {"error": payload}


def respond_error(code: str, message: str, status: int, details=None):
    """Return a Flask ``(response, status)`` tuple carrying the error envelope."""
    return jsonify(error_body(code, message, details)), status


def json_object(data) -> dict:
    """Return *data* when it is a JSON object, else raise ValidationError.

    Routes read their fields with ``.get``, which raises AttributeError on a list or a
    scalar body; that is a caller error, so it has to surface as one.
    """
    if not isinstance(data, dict):
        raise ValidationError("request body must be a JSON object")
    return data


def require_int(data: dict, key: str, default, minimum=None, maximum=None) -> int:
    """Return ``data[key]`` as an int, raising ValidationError when it is not one.

    A missing key takes *default*. Bounds are inclusive. ``bool`` is rejected: it is an
    int subclass, so ``True`` would otherwise silently mean 1.
    """
    raw = data.get(key, default)
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise ValidationError(f"{key} must be an integer, got {type(raw).__name__}")
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError(f"{key} must be an integer, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ValidationError(f"{key} must be at least {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{key} must be at most {maximum}, got {value}")
    return value


def register_error_handlers(app):
    """Make framework-raised errors (404/405/500, validation, ...) use the envelope too."""

    @app.errorhandler(HTTPException)
    def _http_exception(exc: HTTPException):
        code = _STATUS_CODES.get(exc.code, "http_error")
        return respond_error(code, exc.description or exc.name, exc.code or 500)

    @app.errorhandler(Exception)
    def _unhandled(exc: Exception):
        _log.exception("Unhandled error: %s", exc)
        return respond_error("internal_error", "Internal server error.", 500)

    return app
