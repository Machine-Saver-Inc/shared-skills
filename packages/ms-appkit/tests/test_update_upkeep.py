"""An update leaves nothing behind, and a program left open still hears of one."""
from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

from ms_appkit import configure, settings
from ms_appkit.update.checker import CheckOutcome, Release

DAY = 24 * 60 * 60


@pytest.fixture(scope="module")
def qt():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def temp(tmp_path, monkeypatch):
    """The machine's temp folder, for the length of a test."""
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


@pytest.fixture
def slug():
    configure(name="Upkeep test", repo="Machine-Saver-Inc/test", version="1.0.0",
              slug="upkeep-test")
    return "upkeep-test"


def release(version="2.0.0"):
    return Release(version, f"v{version}", "Changes", "https://example.invalid", {}, None)


# --- the download folder is removed once the installer has finished (1.7.0) ---------


def test_the_helper_removes_the_download_folder_after_a_successful_install(temp, slug):
    """Every update left its installer in a temporary folder for ever."""
    from ms_appkit.update.installer import windows_update_command

    folder = temp / f"{slug}-update-abc123"
    folder.mkdir()
    installer = folder / "Setup-2.0.0.exe"
    exe = temp / "Program" / "Program.exe"
    script = windows_update_command(installer, exe)[-1]
    assert "-PassThru" in script and "ExitCode -eq 0" in script
    assert f"Remove-Item -LiteralPath '{folder}' -Recurse -Force" in script
    assert script.index("-Wait") < script.index("Remove-Item") < \
        script.index(f"Start-Process -FilePath '{exe}'"), \
        "removed after the installer exits, before the new version starts"


def test_the_helper_never_removes_a_folder_the_kit_did_not_make(temp, slug):
    from ms_appkit.update.installer import windows_update_command

    for folder in (temp / "Downloads", temp / "other-app-update-abc", temp / f"{slug}-update",
                   temp / "elsewhere" / f"{slug}-update-abc", temp):
        folder.mkdir(parents=True, exist_ok=True)
        script = windows_update_command(folder / "Setup.exe", None)[-1]
        assert "Remove-Item" not in script, folder.name


@pytest.mark.parametrize("code,kept", [(0, False), (3, True)])
def test_the_helper_really_removes_the_folder_only_when_the_installer_succeeded(
        temp, slug, code, kept):
    """Run the helper's script for real with a stand-in installer. A failed
    install keeps the file so the user can run it by hand. Run for real on
    Windows, where the helper is PowerShell; elsewhere the script's guard is
    checked, because the kit's CI counts a skip as a failure."""
    from ms_appkit.update.installer import windows_update_command

    folder = temp / f"{slug}-update-run{code}"
    folder.mkdir()
    installer = folder / "Setup.cmd"
    installer.write_text(f"@exit /b {code}\r\n")
    command = windows_update_command(installer, None)
    assert "if ($run.ExitCode -eq 0) { Remove-Item" in command[-1]
    if sys.platform == "win32":
        finished = subprocess.run(command, timeout=60)
        assert finished.returncode == 0
        assert folder.exists() is kept


def _age(path, seconds, now):
    os.utime(path, (now - seconds, now - seconds))


def test_leftover_downloads_older_than_a_day_are_removed_at_start(temp, slug):
    """An update interrupted before the installer finished left its folder."""
    from ms_appkit.update import installer as module

    now = time.time()
    old = temp / f"{slug}-update-old"
    old.mkdir()
    (old / "Setup.exe").write_bytes(b"x")
    _age(old / "Setup.exe", 2 * DAY, now)
    _age(old, 2 * DAY, now)

    young = temp / f"{slug}-update-young"
    young.mkdir()
    _age(young, 3600, now)

    touched = temp / f"{slug}-update-touched"   # old folder, file still being written
    touched.mkdir()
    (touched / "Setup.exe").write_bytes(b"x")
    _age(touched, 2 * DAY, now)

    stranger = temp / "other-app-update-old"
    stranger.mkdir()
    _age(stranger, 2 * DAY, now)
    unrelated = temp / f"{slug}-updates"
    unrelated.mkdir()
    _age(unrelated, 2 * DAY, now)
    loose = temp / f"{slug}-update-file"
    loose.write_bytes(b"x")
    _age(loose, 2 * DAY, now)

    nested = temp / "elsewhere" / f"{slug}-update-old"   # only the temp folder itself
    nested.mkdir(parents=True)
    _age(nested, 2 * DAY, now)

    removed = module.remove_leftover_downloads(now=now)

    assert removed == [old]
    assert not old.exists()
    for kept in (young, touched, stranger, unrelated, loose, nested):
        assert kept.exists(), kept.name


def test_the_folder_an_update_is_using_is_never_removed(temp, slug, monkeypatch):
    from ms_appkit.update import installer as module

    monkeypatch.setattr(module, "asset_for_this_platform",
                        lambda r: ("Setup.exe", "https://example.invalid/Setup.exe"))

    class Response:
        headers = {"Content-Length": "1"}
        def __init__(self): self.sent = False
        def read(self, n):
            if self.sent:
                return b""
            self.sent = True
            return b"x"
        def __enter__(self): return self
        def __exit__(self, *a): return False

    path = module.download_asset(release(), opener=lambda *a, **k: Response())
    folder = path.parent
    assert folder.parent == temp and folder.name.startswith(f"{slug}-update-")
    _age(path, 2 * DAY, time.time())
    _age(folder, 2 * DAY, time.time())
    assert module.remove_leftover_downloads() == []
    assert path.exists()


def test_the_window_clears_leftovers_when_it_opens(qt, slug, tmp_path, monkeypatch):
    from ms_appkit import shell

    monkeypatch.setattr(settings, "settings_path", lambda: tmp_path / "settings.json")
    calls = []
    monkeypatch.setattr(shell, "remove_leftover_downloads", lambda: calls.append(1) or [])
    made = shell.AppWindow()
    try:
        assert calls == [1]
    finally:
        made.close()


def test_a_failed_cleanup_never_stops_the_window_opening(qt, slug, tmp_path, monkeypatch):
    from ms_appkit import shell

    monkeypatch.setattr(settings, "settings_path", lambda: tmp_path / "settings.json")

    def broken():
        raise PermissionError("locked")

    monkeypatch.setattr(shell, "remove_leftover_downloads", broken)
    shell.AppWindow().close()


# --- the check runs again while the program stays open (1.7.0) ----------------------


class FakeWorker:
    """Stands in for the network: records each check, answers when told."""

    made: list[FakeWorker] = []

    def __init__(self):
        self._answer = None
        FakeWorker.made.append(self)
        outer = self

        class Done:
            def connect(self, slot, *args):
                outer._answer = slot
        self.done = Done()

    def isRunning(self):
        return False

    def start(self):
        pass

    def answer(self, outcome):
        self._answer(outcome)


@pytest.fixture
def window(qt, slug, tmp_path, monkeypatch):
    from ms_appkit import shell

    monkeypatch.setattr(settings, "settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(shell, "UpdateWorker", FakeWorker)
    monkeypatch.setattr(shell, "remove_leftover_downloads", lambda: [], raising=False)
    FakeWorker.made = []
    made = shell.AppWindow()
    clock = [1000.0]
    made._clock = lambda: clock[0]
    made.clock = clock
    made.start_update_check(delay_ms=60 * 60 * 1000)   # the launch check is driven by hand
    yield made
    made._closing = True
    made.close()


def tick(window, hours):
    window.clock[0] += hours * 3600
    window._recheck_timer.timeout.emit()


def test_a_program_left_open_checks_again_every_twelve_hours(window):
    """A burn-in left running for days never heard of a release."""
    from ms_appkit import shell

    assert shell.RECHECK_INTERVAL_S == 12 * 3600
    assert window._recheck_timer.isActive()
    assert window._recheck_timer.interval() <= 60 * 60 * 1000, "wakes often enough to notice"
    window._check_quietly()
    assert len(FakeWorker.made) == 1
    FakeWorker.made[-1].answer(CheckOutcome(latest=release("1.0.0")))
    tick(window, 11.9)
    assert len(FakeWorker.made) == 1, "not before twelve hours"
    tick(window, 0.2)
    assert len(FakeWorker.made) == 2
    tick(window, 0.5)
    assert len(FakeWorker.made) == 2, "the clock restarts at each check"
    tick(window, 12)
    assert len(FakeWorker.made) == 3


def test_the_recheck_honours_the_automatic_check_setting(window):
    window._check_quietly()
    window.settings["check_for_updates"] = False
    tick(window, 30)
    assert len(FakeWorker.made) == 1
    window.settings["check_for_updates"] = True
    tick(window, 0.5)
    assert len(FakeWorker.made) == 2, "switched back on, it checks at the next tick"


def test_a_recheck_does_not_offer_a_release_already_offered_again(window):
    window._check_quietly()
    FakeWorker.made[-1].answer(CheckOutcome(release=release("2.0.0")))
    assert not window.banner.isHidden()
    window.banner.later.click()
    assert window.banner.isHidden()

    tick(window, 12)
    FakeWorker.made[-1].answer(CheckOutcome(release=release("2.0.0")))
    assert window.banner.isHidden(), "Later is not undone by the next check"
    window.refresh_busy_state()
    assert window.banner.isHidden(), "nor by a job finishing"

    tick(window, 12)
    FakeWorker.made[-1].answer(CheckOutcome(release=release("2.1.0")))
    assert not window.banner.isHidden()
    assert window.banner._release.version == "2.1.0"


def test_asking_by_hand_offers_a_release_put_off_with_later(window):
    window._check_quietly()
    FakeWorker.made[-1].answer(CheckOutcome(release=release("2.0.0")))
    window.banner.later.click()
    window._run_check(announce=True)
    FakeWorker.made[-1].answer(CheckOutcome(release=release("2.0.0")))
    assert not window.banner.isHidden()


def test_a_release_found_by_a_recheck_during_a_job_waits_for_it(window):
    working = [True]
    window.busy = lambda: "a chamber is cycling" if working[0] else None
    window._check_quietly()
    FakeWorker.made[-1].answer(CheckOutcome(latest=release("1.0.0")))
    tick(window, 12)
    FakeWorker.made[-1].answer(CheckOutcome(release=release("2.0.0")))
    assert window.banner.isHidden()
    working[0] = False
    window.refresh_busy_state()
    assert not window.banner.isHidden()
