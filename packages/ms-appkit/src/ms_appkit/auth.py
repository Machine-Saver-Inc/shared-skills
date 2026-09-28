"""Signing in to a private Machine Saver program with a machinesaver.net account.

A private program's downloads, updates and credentials sit behind the person's
own Google sign-in (skill section 1a). This module is that sign-in, and it is
free of Qt so every path through it -- signed in, offline inside the grace
period, offline past it, suspended, wrong account -- can be tested without a
window or a network.

How it works:

* **Sign in** through the system browser, never an embedded one: Google blocks
  embedded browsers, and the person should see their own address bar. PKCE and
  a loopback redirect to ``127.0.0.1`` on a free port, the flow Google documents
  for desktop applications.
* **Only the configured domain gets in.** The consent screen is *Internal*, so
  Google refuses other accounts itself; the ID token is checked here as well
  (``hd``, ``email_verified``, audience, issuer, expiry). The token comes
  straight from Google's token endpoint over TLS, which is what makes checking
  its claims without its signature sound (OpenID Connect Core 3.1.3.7).
* **The refresh token lives in the operating system's credential store** --
  Windows Credential Manager, Secret Service on Linux -- through ``keyring``.
  Never in ``settings.json``, never in the log, never in a problem report. So
  does the time Google last confirmed the account, so nobody can lengthen the
  grace period by editing a file.
* **Offline is not refused, but it is counted.** If Google cannot be reached,
  the program opens for ``grace_days`` after the last confirmation.
* **A refusal is not an outage.** If Google answers ``invalid_grant`` -- the
  account was suspended, the token revoked -- the stored sign-in is deleted at
  once, whatever is left of the grace period.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import logging
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass

from ms_appkit.identity import PrivateConfig, app
from ms_appkit.update.net import open_url

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
SCOPES = (
    "openid",
    "email",
    # Releases. cloud-platform below would cover it; stating it says why.
    "https://www.googleapis.com/auth/devstorage.read_only",
    # Secret Manager accepts nothing narrower. The Internal consent screen is
    # what makes a broad scope acceptable here.
    "https://www.googleapis.com/auth/cloud-platform",
)
DAY_S = 86_400
TIMEOUT_S = 15.0
SIGN_IN_TIMEOUT_S = 300.0


class SignInError(Exception):
    """A sign-in problem, in a sentence the person at the machine can act on."""


class Revoked(SignInError):
    """Google says this sign-in is no longer valid."""


class WrongAccount(SignInError):
    """The account is not one this program lets in."""


class Offline(SignInError):
    """Google could not be reached."""


# -- where the sign-in is kept ---------------------------------------------------


class MemoryStore:
    """A credential store that forgets on exit. For tests and simulators."""

    def __init__(self) -> None:
        self.value: str | None = None

    def get(self) -> str | None:
        return self.value

    def set(self, value: str) -> None:
        self.value = value

    def delete(self) -> None:
        self.value = None


class KeyringStore:
    """The operating system's credential store, through ``keyring``."""

    USERNAME = "google-sign-in"

    def __init__(self, service: str) -> None:
        self.service = service

    @staticmethod
    def _keyring():
        import keyring  # only a private program installs it: ms-appkit[private]

        return keyring

    def get(self) -> str | None:
        try:
            return self._keyring().get_password(self.service, self.USERNAME)
        except Exception as exc:  # noqa: BLE001 - a broken store means "signed out"
            log.warning("could not read the credential store: %s", exc)
            return None

    def set(self, value: str) -> None:
        self._keyring().set_password(self.service, self.USERNAME, value)

    def delete(self) -> None:
        try:
            self._keyring().delete_password(self.service, self.USERNAME)
        except Exception as exc:  # noqa: BLE001 - already gone is the goal
            log.info("nothing to delete from the credential store: %s", exc)


# -- what the program should do at startup --------------------------------------


@dataclass(frozen=True)
class Status:
    """Where the sign-in stands. ``kind`` decides whether the window opens."""

    kind: str                  # signed_in | offline | signed_out | expired | revoked
    email: str = ""
    days_left: int = 0
    message: str = ""

    @property
    def may_open(self) -> bool:
        """The only two states in which the program's window is built."""
        return self.kind in ("signed_in", "offline")

    def footer_text(self) -> str:
        if self.kind == "signed_in":
            return f"Signed in as {self.email}"
        if self.kind == "offline":
            days = "day" if self.days_left == 1 else "days"
            return (f"Signed in as {self.email} · working offline, "
                    f"{self.days_left} {days} left")
        return "Not signed in"


def claims(id_token: str) -> dict:
    """The payload of an ID token that came straight from Google's endpoint."""
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError) as exc:
        raise SignInError("Google's answer could not be read. Try again.") from exc


def check_claims(found: dict, config: PrivateConfig, now: float) -> str:
    """The account's email, or WrongAccount/SignInError saying why not."""
    email = str(found.get("email", ""))
    if found.get("hd") != config.domain or not email.endswith("@" + config.domain):
        raise WrongAccount(
            f"{email or 'That account'} is not a {config.domain} account. Sign in "
            f"with your Machine Saver Google account."
        )
    if found.get("email_verified") is not True:
        raise WrongAccount(f"Google has not verified {email}. Ask IT to check it.")
    if found.get("aud") != config.client_id or found.get("iss") not in ISSUERS:
        raise SignInError("That sign-in was meant for a different program.")
    if float(found.get("exp", 0)) < now:
        raise SignInError("That sign-in had already expired. Try again.")
    return email


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


class Auth:
    """One program's sign-in. Everything outside it is injectable for tests."""

    def __init__(self, config: PrivateConfig, store=None,
                 opener: Callable = open_url, clock: Callable[[], float] = time.time,
                 browser: Callable[[str], bool] = webbrowser.open) -> None:
        self.config = config
        self.store = store if store is not None else KeyringStore(f"ms-appkit:{app().slug}")
        self.opener = opener
        self.clock = clock
        self.browser = browser
        self._access: str = ""
        self._access_until: float = 0.0
        self.last: Status = Status("signed_out")

    # -- the stored record ------------------------------------------------------
    def _saved(self) -> dict | None:
        raw = self.store.get()
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return data if data.get("refresh_token") else None
        except ValueError:
            return None

    def _save(self, refresh_token: str, email: str) -> None:
        self.store.set(json.dumps({
            "refresh_token": refresh_token,
            "email": email,
            "confirmed_at": self.clock(),
        }))

    def _forget(self) -> None:
        self.store.delete()
        self._access, self._access_until = "", 0.0

    # -- talking to Google ------------------------------------------------------
    def _post(self, url: str, fields: dict) -> dict:
        """POST a form; return the JSON answer. Offline on no answer at all."""
        request = urllib.request.Request(
            url, data=urllib.parse.urlencode(fields).encode("ascii"),
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent": app().user_agent},
            method="POST",
        )
        try:
            with self.opener(request, timeout=TIMEOUT_S) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                answer = json.loads(exc.read().decode("utf-8"))
            except (ValueError, OSError):
                answer = {}
            if answer.get("error") in ("invalid_grant", "unauthorized_client"):
                raise Revoked(
                    "Your sign-in is no longer valid. Sign in again; if that "
                    "fails, your account may have been suspended."
                ) from exc
            if exc.code >= 500:
                raise Offline(f"Google is not answering properly ({exc.code}).") from exc
            raise SignInError(
                f"Google refused the sign-in: {answer.get('error_description') or exc}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise Offline(f"Google could not be reached: {exc}") from exc

    def _refresh(self, saved: dict) -> str:
        answer = self._post(TOKEN_URL, {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "refresh_token": saved["refresh_token"],
            "grant_type": "refresh_token",
        })
        email = saved.get("email", "")
        if answer.get("id_token"):
            email = check_claims(claims(answer["id_token"]), self.config, self.clock())
        self._access = answer.get("access_token", "")
        self._access_until = self.clock() + float(answer.get("expires_in", 0)) - 60
        self._save(saved["refresh_token"], email)
        return email

    # -- what the program asks ----------------------------------------------------
    def status(self) -> Status:
        """Ask Google whether this sign-in still stands; decide what to do."""
        saved = self._saved()
        if saved is None:
            self.last = Status("signed_out")
            return self.last
        try:
            email = self._refresh(saved)
            self.last = Status("signed_in", email=email)
        except Revoked as exc:
            self._forget()
            self.last = Status("revoked", message=str(exc))
        except WrongAccount as exc:
            self._forget()
            self.last = Status("revoked", message=str(exc))
        except (Offline, SignInError) as exc:
            since = self.clock() - float(saved.get("confirmed_at", 0))
            left = self.config.grace_days - int(since // DAY_S)
            if 0 <= since and left > 0:
                self.last = Status("offline", email=saved.get("email", ""),
                                   days_left=left, message=str(exc))
            else:
                self.last = Status(
                    "expired", email=saved.get("email", ""),
                    message=(f"This computer has not been able to confirm your "
                             f"sign-in with Google for {self.config.grace_days} "
                             f"days. Connect it to the internet and sign in again."),
                )
        return self.last

    def access_token(self) -> str:
        """A current access token, refreshing if needed. Raises SignInError."""
        if self._access and self.clock() < self._access_until:
            return self._access
        saved = self._saved()
        if saved is None:
            raise SignInError("You are not signed in.")
        try:
            self._refresh(saved)
        except Revoked:
            self._forget()
            raise
        return self._access

    def sign_in(self, timeout: float = SIGN_IN_TIMEOUT_S) -> Status:
        """Open the browser, wait for Google to send the person back, keep it.

        Blocking: run it off the interface thread.
        """
        if not self.config.client_secret:
            raise SignInError(
                "This copy of the program was built without its sign-in key, so it "
                "cannot sign you in. Install a released version, or report a problem."
            )
        verifier, challenge = _pkce()
        state = secrets.token_urlsafe(24)
        got: dict[str, str] = {}
        name = app().name

        class Back(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - the name http.server calls
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if "code" not in query and "error" not in query:
                    self.send_response(404)
                    self.end_headers()
                    return
                got.update({k: v[0] for k, v in query.items()})
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    f"<html><body style='font-family:sans-serif;margin:3em'>"
                    f"<h2>You can close this tab.</h2><p>Go back to {name}.</p>"
                    f"</body></html>".encode()
                )

            def log_message(self, *args):  # keep the code out of the log
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Back)
        redirect = f"http://127.0.0.1:{server.server_port}"
        server.timeout = 0.5
        url = AUTH_URL + "?" + urllib.parse.urlencode({
            "client_id": self.config.client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",           # always hands back a refresh token
            "hd": self.config.domain,      # a hint; the claims check is the rule
        })
        try:
            if not self.browser(url):
                raise SignInError("Your web browser could not be opened.")
            deadline = self.clock() + timeout
            while not got and self.clock() < deadline:
                server.handle_request()
        finally:
            server.server_close()

        if not got:
            raise SignInError("Sign-in was not finished in time. Try again.")
        if got.get("error"):
            raise SignInError("Sign-in was cancelled."
                              if got["error"] == "access_denied"
                              else f"Google said: {got['error']}")
        if got.get("state") != state:
            raise SignInError("That sign-in did not come from this program. Try again.")

        answer = self._post(TOKEN_URL, {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": got["code"],
            "code_verifier": verifier,
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
        })
        if not answer.get("refresh_token"):
            raise SignInError("Google did not let this computer stay signed in. Try again.")
        email = check_claims(claims(answer.get("id_token", "")), self.config, self.clock())
        self._access = answer.get("access_token", "")
        self._access_until = self.clock() + float(answer.get("expires_in", 0)) - 60
        self._save(answer["refresh_token"], email)
        self.last = Status("signed_in", email=email)
        return self.last

    def sign_out(self) -> None:
        """Forget this computer's sign-in, and tell Google to as well."""
        saved = self._saved()
        if saved:
            try:
                self._post(REVOKE_URL, {"token": saved["refresh_token"]})
            except SignInError as exc:
                log.info("could not revoke at Google (%s); forgetting locally", exc)
        self._forget()
        self.last = Status("signed_out")


_current: Auth | None = None
_lock = threading.Lock()


def current() -> Auth:
    """The running program's sign-in. Only a private program has one."""
    global _current
    with _lock:
        if _current is None:
            info = app()
            if not info.is_private or info.private is None:
                raise SignInError("A public program has nothing to sign in to.")
            _current = Auth(info.private)
        return _current


def use(auth: Auth | None) -> None:
    """Replace the program's sign-in -- for tests. ``None`` resets it."""
    global _current
    _current = auth
