"""Downloading and applying an update.

The same three routes in every Machine Saver program: a Windows installer runs
under a detached helper that starts the program again afterwards, an AppImage
replaces itself in place, and a .deb is downloaded for the user to install
because no program of ours asks for root.

Kept free of Qt so the download, the checksum check and the decision about how
to install can be tested without a running application.

Nothing here runs while the program is in the middle of something it should
not be interrupted during; the caller enforces that.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ms_appkit.identity import app
from ms_appkit.update import channel as channels
from ms_appkit.update.checker import (
    Release,
    asset_for_this_platform,
    describe_failure,
    sha256,
    verify_against_checksums,
)
from ms_appkit.update.net import open_url

log = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT_S = 60
CHUNK = 256 * 1024


class UpdateError(Exception):
    """Something went wrong that the user needs to be told about."""


class Applied(str, Enum):
    RESTARTING = "restarting"      # the program is about to close and come back
    INSTALLER_RUNNING = "installer_running"
    MANUAL = "manual"              # the file is downloaded; the user finishes


@dataclass
class ApplyResult:
    outcome: Applied
    message: str
    path: Path


def running_appimage() -> Path | None:
    """The AppImage we were launched from, if that is how we are running."""
    value = os.environ.get("APPIMAGE")
    return Path(value) if value else None


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def download_asset(
    release: Release,
    destination: Path | None = None,
    progress: Callable[[int, int], None] | None = None,
    opener: Callable = open_url,
    channel: channels.ReleaseChannel | None = None,
) -> Path:
    """Fetch the file for this platform. Raises UpdateError with a readable reason."""
    chosen = asset_for_this_platform(release)
    if chosen is None:
        raise UpdateError(
            "This release has no download for this type of computer. "
            "Open the release page and pick a file by hand."
        )
    name, url = chosen
    source = channel or channels.current()
    folder = destination or Path(tempfile.mkdtemp(prefix=f"{app().slug}-update-"))
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name

    try:
        request = urllib.request.Request(url, headers=source.download_headers())
        with opener(request, timeout=DOWNLOAD_TIMEOUT_S) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with target.open("wb") as handle:
                while True:
                    block = response.read(CHUNK)
                    if not block:
                        break
                    handle.write(block)
                    done += len(block)
                    if progress:
                        progress(done, total)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # The same wording the check uses. A certificate failure here reads as
        # gibberish on its own, and this is the one the user actually hits:
        # the check goes to api.github.com and the download to the asset host,
        # so a trust store that satisfies one can still fail the other.
        raise UpdateError(
            f"The download did not finish.\n\n{describe_failure(exc, source)}"
        ) from exc
    return target


def fetch_checksums(release: Release, opener: Callable = open_url,
                    channel: channels.ReleaseChannel | None = None) -> str:
    if not release.checksums_url:
        return ""
    source = channel or channels.current()
    try:
        request = urllib.request.Request(
            release.checksums_url, headers=source.download_headers()
        )
        with opener(request, timeout=DOWNLOAD_TIMEOUT_S) as response:
            return response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("could not fetch SHA256SUMS: %s", exc)
        return ""


def verify_download(path: Path, release: Release, opener=open_url,
                    channel: channels.ReleaseChannel | None = None) -> None:
    """Refuse to run anything whose hash is not the one the release published."""
    text = fetch_checksums(release, opener, channel)
    if not text:
        raise UpdateError(
            "Could not fetch the checksum list for this release, so the download "
            "was not verified and will not be installed. Try again later, or "
            "install it by hand from the release page."
        )
    if not verify_against_checksums(path, text):
        raise UpdateError(
            f"The downloaded file does not match the checksum published with the "
            f"release, so it will not be installed.\n\n{path.name}\n"
            f"got {sha256(path)[:16]}…"
        )


INSTALLER_FLAGS = ("/SILENT", "/CLOSEAPPLICATIONS", "/NOCANCEL")


def running_executable() -> Path | None:
    """The frozen program we were launched from, or None when running from source."""
    return Path(sys.executable) if is_frozen() else None


def windows_update_command(installer: Path, target: Path | None) -> list[str]:
    """A detached helper that runs the installer, waits for it, then starts
    the new version.

    Inno Setup's ``/RESTARTAPPLICATIONS`` only restarts programs registered
    with the Windows Restart Manager, which a Qt program is not, so a program
    that relied on it closed and never came back (AirVibe Power Profiler
    0.2.0 -> 0.2.1, the family's first update through the store). The program
    cannot relaunch itself either: it has to be gone before the installer can
    replace its files. So a PowerShell that outlives both does it: wait for
    the installer, then start the program. PowerShell is on every Windows.
    """
    quoted_flags = ",".join(f"'{flag}'" for flag in INSTALLER_FLAGS)
    script = (f"Start-Process -FilePath '{installer}' -ArgumentList {quoted_flags} -Wait")
    if target is not None:
        script += f"; Start-Process -FilePath '{target}'"
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
            "-Command", script]


def unblock(path: Path) -> bool:
    """Remove Windows' mark of the web from a downloaded file, if it has one.

    A file saved by a browser carries a ``Zone.Identifier`` stream, and the
    shell then asks "The publisher could not be verified. Are you sure?"
    before running it, a dialog a hidden helper would wait behind for ever.
    Files this program downloads itself carry no mark; one handed to it by
    other means might. True when a mark was removed.
    """
    if sys.platform != "win32":
        return False
    try:
        os.remove(f"{path}:Zone.Identifier")
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        log.warning("could not remove the mark of the web from %s: %s", path, exc)
        return False


def _detached() -> dict:
    """Popen options that let the helper outlive this process, on Windows."""
    if sys.platform != "win32":
        return {}
    return {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            "close_fds": True}


def apply_update(path: Path, *, launcher: Callable = subprocess.Popen,
                 target: Path | None = None) -> ApplyResult:
    """Install the verified download, as far as this platform allows.

    ``target`` is the program to start again once a Windows installer has
    finished; by default the frozen executable this process was launched
    from. From a source checkout there is nothing to restart, and the
    installer runs on its own.
    """
    name = path.name.lower()

    if name.endswith(".exe"):
        restart = target if target is not None else running_executable()
        if unblock(path):
            log.info("removed the mark of the web from %s", path.name)
        try:
            launcher(windows_update_command(path, restart), **_detached())
        except OSError as exc:
            raise UpdateError(f"The installer would not start: {exc}") from exc
        return ApplyResult(
            Applied.INSTALLER_RUNNING,
            "The installer is running. This program will close and reopen on the "
            "new version." if restart is not None else
            "The installer is running. This program will close; open it again "
            "when the installer has finished.",
            path,
        )

    if name.endswith(".appimage"):
        current = running_appimage()
        if current is None:
            return ApplyResult(
                Applied.MANUAL,
                f"Downloaded to {path}. Replace your current AppImage with it, "
                f"then make it executable with chmod +x.",
                path,
            )
        try:
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            staged = current.with_suffix(current.suffix + ".new")
            shutil.copy2(path, staged)
            os.replace(staged, current)   # atomic on the same filesystem
        except OSError as exc:
            raise UpdateError(
                f"Could not replace {current}: {exc}. You may not have permission "
                f"to write there."
            ) from exc
        return ApplyResult(
            Applied.RESTARTING,
            "Updated. This program will restart on the new version.",
            current,
        )

    if name.endswith(".deb"):
        return ApplyResult(
            Applied.MANUAL,
            "Downloaded. Install it with:\n\n"
            f"    sudo apt install {path}\n\n"
            "This program cannot install system packages on your behalf.",
            path,
        )

    return ApplyResult(Applied.MANUAL, f"Downloaded to {path}.", path)


def relaunch(target: Path | None = None) -> None:
    """Start the new version and let this process exit."""
    executable = target or running_appimage()
    if executable is None:
        executable = Path(sys.executable)
    try:
        subprocess.Popen([str(executable)], close_fds=True)
    except OSError as exc:  # noqa: BLE001 - the user can reopen it themselves
        log.warning("could not relaunch: %s", exc)
