"""Shared helpers for the live-HTTP API contract tests.

Each test module points ``<SERVICE>_URL`` at a running backend (or uses the
default localhost port) and validates real HTTP responses against the JSON
Schemas in ``docs/api-contract/schemas/``. Tests auto-skip when the service is
unreachable, so the suite is safe to run with only some backends up.

Requires ``jsonschema`` — the suite skips entirely if it is not installed.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytest.importorskip("jsonschema", reason="contract tests require jsonschema")
from jsonschema import Draft202012Validator

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
_VALIDATORS: dict = {}


def _validator(name: str) -> Draft202012Validator:
    if name not in _VALIDATORS:
        schema = json.loads((_SCHEMA_DIR / f"{name}.schema.json").read_text())
        _VALIDATORS[name] = Draft202012Validator(schema)
    return _VALIDATORS[name]


def assert_matches(schema_name: str, instance) -> None:
    """Assert *instance* validates against ``schemas/<schema_name>.schema.json``."""
    errors = sorted(_validator(schema_name).iter_errors(instance), key=str)
    assert not errors, (
        f"{schema_name} schema violation: {errors[0].message}\n"
        f"instance: {json.dumps(instance)[:400]}"
    )


def base_url(env_var: str, default: str) -> str:
    """Resolve a service base URL from an env var, falling back to *default*."""
    return os.environ.get(env_var, default).rstrip("/")


def reachable(base: str) -> bool:
    parsed = urlparse(base)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def skip_unless_reachable(base: str, env_var: str):
    """A module-level ``pytestmark`` that skips when the service isn't reachable."""
    return pytest.mark.skipif(
        not reachable(base), reason=f"{env_var} not reachable at {base} (set {env_var})"
    )


def http_get(base: str, path: str, timeout: int = 15):
    return _request("GET", base + path, None, timeout)


def http_post(base: str, path: str, body=None, timeout: int = 60):
    return _request("POST", base + path, body, timeout)


def _request(method: str, url: str, body, timeout: int):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _parse(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _parse(exc.read())


def _parse(raw: bytes):
    text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except ValueError:
        return text
