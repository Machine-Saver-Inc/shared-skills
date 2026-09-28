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

:class:`GitHubReleases` serves a public program and behaves exactly as the code
it replaced. :class:`GoogleCloudStorage` serves a private one: the files live in
a bucket only the company's Google accounts can read, and every request carries
the signed-in person's own token (skill section 1a).
"""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field

from ms_appkit.identity import AppInfo, app


class NotSignedIn(OSError):
    """A private release host was asked for something before sign-in.

    An ``OSError`` so the checker and the downloader treat it exactly like any
    other failure to reach the host: say so in a sentence, change nothing.
    """


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


STORAGE = "https://storage.googleapis.com/storage/v1/b"


def _signed_in_token() -> str:
    from ms_appkit import auth

    try:
        return auth.current().access_token()
    except auth.SignInError as exc:
        raise NotSignedIn(str(exc)) from exc


@dataclass(frozen=True)
class GoogleCloudStorage(ReleaseChannel):
    """A private program's releases, in a bucket only the domain can read.

    Layout, one folder per program::

        <slug>/latest.json        written last, so it never names missing files
        <slug>/v1.2.0/<files>     the installers and SHA256SUMS
    """

    bucket: str
    slug: str
    token: Callable[[], str] = field(default=_signed_in_token, compare=False)
    host: str = "the Machine Saver release store"
    domain: str = "storage.googleapis.com"
    refused_hint: str = ("Your account may not be allowed to read releases. Sign "
                         "out and sign in again with your machinesaver.net account.")

    def object_url(self, path: str) -> str:
        return f"{STORAGE}/{self.bucket}/o/{urllib.parse.quote(path, safe='')}?alt=media"

    @property
    def latest_url(self) -> str:
        return self.object_url(f"{self.slug}/latest.json") if self.bucket else ""

    @property
    def releases_page(self) -> str:
        return (f"https://console.cloud.google.com/storage/browser/{self.bucket}/{self.slug}"
                if self.bucket else "")

    def _signed(self, headers: dict[str, str]) -> dict[str, str]:
        return {**headers, "Authorization": f"Bearer {self.token()}"}

    def feed_headers(self) -> dict[str, str]:
        return self._signed(super().feed_headers())

    def download_headers(self) -> dict[str, str]:
        return self._signed(super().download_headers())

    def release_from(self, data: dict):
        from ms_appkit.update.checker import Release

        tag = str(data.get("tag") or f"v{data.get('version', '')}")
        assets = {name: self.object_url(f"{self.slug}/{tag}/{name}")
                  for name in data.get("files", [])}
        return Release(
            version=str(data.get("version") or tag).lstrip("vV"),
            tag=tag,
            notes=data.get("notes") or "",
            html_url=self.releases_page,
            assets=assets,
            checksums_url=assets.get("SHA256SUMS"),
        )


def feed(version: str, notes: str, files: list[str]) -> str:
    """The ``latest.json`` a private release publishes, in the one shape the
    channel reads. Called by the release workflow, so the writer and the reader
    cannot drift apart."""
    if "SHA256SUMS" not in files:
        raise ValueError("a release without SHA256SUMS cannot be verified")
    version = version.lstrip("vV")
    return json.dumps({"version": version, "tag": f"v{version}", "notes": notes,
                       "files": sorted(files)}, indent=2)


_override: ReleaseChannel | None = None


def for_app(info: AppInfo) -> ReleaseChannel:
    """The channel a program with this identity is released through."""
    if info.is_private and info.private is not None:
        return GoogleCloudStorage(bucket=info.private.bucket, slug=info.slug)
    return GitHubReleases(info.repo)


def current() -> ReleaseChannel:
    """The channel for the running program."""
    return _override if _override is not None else for_app(app())


def use(channel: ReleaseChannel | None) -> None:
    """Replace the channel -- for tests, and for a simulator. ``None`` restores it."""
    global _override
    _override = channel
