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


@dataclass(frozen=True)
class AppInfo:
    """The identity of the running program."""

    name: str = "A Machine Saver program"
    repo: str = ""
    version: str = "0.0.0"
    slug: str = "machine-saver-app"
    organisation: str = ORGANISATION
    configured: bool = False

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
              organisation: str = ORGANISATION) -> AppInfo:
    """State who this program is. Call once, before the window is built."""
    global _app
    _app = AppInfo(
        name=name,
        repo=repo,
        version=version,
        slug=slug or name.lower().replace(" ", "-"),
        organisation=organisation,
        configured=True,
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
