"""Credentials a private program needs, fetched after sign-in.

A private program never keeps a password, an API key or a login in its
repository or its settings file (skill section 1a). Each value is a secret in
Google Secret Manager, readable by the signed-in person's own account, fetched
when first asked for and held only in memory:

    from ms_appkit import secrets
    password = secrets.get("wipom-password")

A public program has no secrets to hold, and asking is a mistake in the program,
so it raises rather than returning nothing.
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from ms_appkit.identity import app
from ms_appkit.update.net import open_url

log = logging.getLogger(__name__)

API = "https://secretmanager.googleapis.com/v1"
TIMEOUT_S = 15.0
_cache: dict[str, str] = {}


class SecretUnavailable(Exception):
    """A credential could not be fetched, in a sentence someone can act on."""


def get(name: str, opener: Callable = open_url, token: Callable[[], str] | None = None) -> str:
    """The latest version of the named secret, as text."""
    info = app()
    if not info.is_private or info.private is None:
        raise RuntimeError("a public program holds no secrets (skill section 1a)")
    if name in _cache:
        return _cache[name]

    from ms_appkit import auth

    try:
        bearer = (token or auth.current().access_token)()
    except auth.SignInError as exc:
        raise SecretUnavailable(f"{exc} The program needs you signed in to fetch {name}.") \
            from exc

    project = urllib.parse.quote(info.private.project, safe="")
    url = f"{API}/projects/{project}/secrets/{urllib.parse.quote(name, safe='')}" \
          "/versions/latest:access"
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {bearer}", "User-Agent": info.user_agent,
    })
    try:
        with opener(request, timeout=TIMEOUT_S) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise SecretUnavailable(
                f"Your account is not allowed to read {name}. Ask whoever looks "
                f"after the program's Google Cloud project to grant it."
            ) from exc
        if exc.code == 404:
            raise SecretUnavailable(f"There is no secret called {name}.") from exc
        raise SecretUnavailable(f"Google refused to hand over {name} ({exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise SecretUnavailable(
            f"{name} could not be fetched; this computer may be offline. ({exc})"
        ) from exc

    value = base64.b64decode(data["payload"]["data"]).decode("utf-8")
    _cache[name] = value
    return value


def forget() -> None:
    """Drop every fetched value -- on sign-out."""
    _cache.clear()
