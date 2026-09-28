"""Who this program is.

Everything else in the kit needs three facts: what the program is called, which
GitHub repository it is released from, and which version is running. The first
of these programs imported those straight from its own package, which is
exactly what made the shell hard to lift out of it. Here they are stated once, at startup, and every
other module asks for them.

    import ms_appkit
    ms_appkit.configure(
        name="Gateway Provisioning",
        repo="Machine-Saver-Inc/gateway-provisioning",
        version=__version__,
        slug="gateway-provisioning",
    )

Nothing raises if this is skipped -- a report or an update check with a
placeholder name is better than a crash on a shop-floor PC -- but a warning is
logged, because a program reporting itself as "A Machine Saver program" is a
mistake nobody meant to make.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

ORGANISATION = "Machine Saver Inc"
VISIBILITIES = ("public", "private")


@dataclass(frozen=True)
class PrivateConfig:
    """Where a private program signs in, fetches releases and reads credentials.

    None of these values is a secret in the sense a password is -- a desktop
    OAuth client's "secret" is not confidential by Google's own account of it --
    but they identify Machine Saver's infrastructure, so a private program
    keeps them in its own private repository and never in this public one.
    See the ``ms-desktop-app`` skill, section 1a.
    """

    client_id: str
    client_secret: str
    project: str                      # Google Cloud project for Secret Manager
    bucket: str                       # release bucket, readable by the domain
    support_email: str                # where "Email it to support" goes
    domain: str = "machinesaver.net"  # the only accounts allowed in
    grace_days: int = 14              # a policy, not a setting (section 1a)


@dataclass(frozen=True)
class AppInfo:
    """The identity of the running program."""

    name: str = "A Machine Saver program"
    repo: str = ""
    version: str = "0.0.0"
    slug: str = "machine-saver-app"
    organisation: str = ORGANISATION
    configured: bool = False
    visibility: str = "public"
    private: PrivateConfig | None = None

    @property
    def is_private(self) -> bool:
        return self.visibility == "private"

    # The three GitHub addresses below describe the public repository. The
    # update code no longer reads them: it asks ms_appkit.update.channel, which
    # is where a private program's host will differ.
    @property
    def releases_page(self) -> str:
        return f"https://github.com/{self.repo}/releases" if self.repo else ""

    @property
    def new_issue_url(self) -> str:
        return f"https://github.com/{self.repo}/issues/new" if self.repo else ""

    @property
    def latest_release_api(self) -> str:
        return (f"https://api.github.com/repos/{self.repo}/releases/latest"
                if self.repo else "")

    @property
    def user_agent(self) -> str:
        return f"{self.slug}/{self.version}"

    @property
    def home(self) -> Path:
        """Where this program keeps its log and settings on this machine."""
        return Path.home() / f".{self.slug}"

    @property
    def log_path(self) -> Path:
        return self.home / f"{self.slug}.log"


_app = AppInfo()


def configure(name: str, repo: str, version: str, slug: str = "",
              organisation: str = ORGANISATION, visibility: str = "public",
              private: PrivateConfig | None = None) -> AppInfo:
    """State who this program is. Call once, before the window is built.

    A private program must say how it signs in. That mistake is the author's,
    not the operator's, so it raises here -- where the house-rules tests will
    find it -- rather than being papered over on a shop-floor PC.
    """
    global _app
    if visibility not in VISIBILITIES:
        raise ValueError(f"visibility must be one of {VISIBILITIES}, not {visibility!r}")
    if visibility == "private" and private is None:
        raise ValueError("a private program needs a PrivateConfig (skill section 1a)")
    if visibility == "public" and private is not None:
        raise ValueError("a public program has nothing to sign in to; drop PrivateConfig")
    _app = AppInfo(
        name=name,
        repo=repo,
        version=version,
        slug=slug or name.lower().replace(" ", "-"),
        organisation=organisation,
        configured=True,
        visibility=visibility,
        private=private,
    )
    return _app


def app() -> AppInfo:
    """The identity that was configured, or a placeholder with a warning."""
    if not _app.configured:
        log.warning(
            "ms_appkit.configure() was never called; this program will report "
            "itself as %r with no repository, so updates and problem reports "
            "will not work", _app.name,
        )
    return _app
