"""Shared client for the examples.

Set ``WSIGN_API_KEY`` (use a test key, ``sk_test_...``) and optionally ``WSIGN_API_BASE``.
"""

from __future__ import annotations

import os

import wsign


def client() -> wsign.Client:
    return wsign.Client(
        os.environ.get("WSIGN_API_KEY"),
        base_url=os.environ.get("WSIGN_API_BASE", wsign.DEFAULT_BASE_URL),
        app_info={"name": "wsign-python-examples"},
    )
