"""Where releases come from.

Every Machine Saver program has so far been released from a public GitHub
repository, and the checker and downloader were written straight against that:
the feed URL, the ``Accept`` header, the JSON shape and the host named in an
error were all GitHub's, in three different files.

A private program cannot work that way. The people who run it sign in with a
machinesaver.net Google account and usually have no GitHub account at all, so
its releases have to live somewhere that account can open. Rather than teach
each of those three files a second host, everything that differs between hosts
is gathered here, behind one small interface, and the rest of ``update/``
asks the channel:

* which URL answers "what is the newest release?", with which headers;
* how to read that answer into a :class:`~ms_appkit.update.checker.Release`;
* which headers a download needs (a private host will need a token here);
* the page a person can open when the program cannot fetch the file itself;
* what to call the host in a sentence, so an error does not say "GitHub" about
  a host that is not GitHub.

:class:`GitHubReleases` is the only channel today and behaves exactly as the
code it replaced. The private channel arrives with ms-appkit 1.3.0; the skill's
§1a describes it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ms_appkit.identity import AppInfo, app


class ReleaseChannel:
    """What the checker and the downloader need to know about a release host."""

    #: What to call this host in a sentence the person at the machine reads.
    host: str = "the update server"
    #: Its DNS name, for the "could not be looked up" explanation.
    domain: str = ""
    #: What else a refusal (HTTP 403) usually means on this host.
    refused_hint: str = ""

    @property
    def latest_url(self) -> str:
        raise NotImplementedError

    @property
    def releases_page(self) -> str:
        raise NotImplementedError

    def feed_headers(self) -> dict[str, str]:
        return {"User-Agent": app().user_agent}

    def download_headers(self) -> dict[str, str]:
        return {"User-Agent": app().user_agent}

    def release_from(self, data: dict):
        raise NotImplementedError


@dataclass(frozen=True)
class GitHubReleases(ReleaseChannel):
    """A public repository's GitHub Releases feed. Needs no token."""

    repo: str
    host: str = "GitHub"
    domain: str = "github.com"
    refused_hint: str = ("If several programs share this connection, the hourly "
                         "limit may have been reached.")

    @property
    def latest_url(self) -> str:
        return (f"https://api.github.com/repos/{self.repo}/releases/latest"
                if self.repo else "")

    @property
    def releases_page(self) -> str:
        return f"https://github.com/{self.repo}/releases" if self.repo else ""

    def feed_headers(self) -> dict[str, str]:
        return {"Accept": "application/vnd.github+json", **super().feed_headers()}

    def release_from(self, data: dict):
        from ms_appkit.update.checker import Release

        assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
        return Release(
            version=str(data.get("tag_name", "")).lstrip("vV"),
            tag=data.get("tag_name", ""),
            notes=data.get("body") or "",
            html_url=data.get("html_url", self.releases_page),
            assets=assets,
            checksums_url=assets.get("SHA256SUMS"),
        )


_override: ReleaseChannel | None = None


def for_app(info: AppInfo) -> ReleaseChannel:
    """The channel a program with this identity is released through."""
    return GitHubReleases(info.repo)


def current() -> ReleaseChannel:
    """The channel for the running program."""
    return _override if _override is not None else for_app(app())


def use(channel: ReleaseChannel | None) -> None:
    """Replace the channel -- for tests, and for a simulator. ``None`` restores it."""
    global _override
    _override = channel
