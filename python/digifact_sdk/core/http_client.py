"""Generic HTTP helpers for Digifact API communication.

Each provider subclasses :class:`BaseHttpClient` for its country-specific
authentication and endpoint logic.
"""
from __future__ import annotations

from typing import Any

import requests

from .exceptions import DigifactApiError, DigifactAuthError, DigifactError, DigifactValidationError


def _try_json(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {"_text": resp.text}


def _check_response(data: dict) -> dict:
    """Raise DigifactValidationError if the API response indicates failure.

    Uses the same status-code convention as the existing GT SDK.
    Shared by DO which uses the same response format.
    """
    code = data.get("code")
    if code is None:
        # No code field — check for auth_number / authNumber
        auth = data.get("authNumber") or data.get("Autorizacion")
        if auth:
            return data
        return data

    code_int = int(code)
    if code_int == 1:
        return data
    if code_int == 0:
        msg = data.get("description") or data.get("message") or str(data)
        full_msg = f"DTE rejected (code=0): {msg}"
        raise DigifactValidationError(full_msg, code=code_int, raw=data)

    msg = data.get("description") or data.get("message") or str(data)
    full_msg = f"API warning (code={code_int}): {msg}"
    raise DigifactApiError(full_msg, code=code_int, raw=data)


class BaseHttpClient:
    """Minimal shared HTTP logic.

    Concrete providers implement :meth:`authenticate` and custom request helpers.
    """

    def __init__(
        self,
        base_url: str,
        session: requests.Session | None = None,
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout
        self._token: str = ""

    def _post_json(self, path: str, payload: dict) -> dict:
        """POST JSON to a relative *path* and return parsed JSON."""
        resp = self.session.post(
            f"{self.base_url}{path}",
            json=payload,
            headers={"Authorization": self._token, "Content-Type": "application/json"},
            timeout=self.timeout,
        )
        return self._handle_response(resp)

    def _handle_response(self, resp: requests.Response) -> dict:
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise DigifactApiError(f"HTTP error: {exc}", raw=_try_json(resp)) from exc
        data = resp.json()
        return _check_response(data)