"""A shared shell must not disappear or interrupt a hardware job."""
from __future__ import annotations

import gc
import weakref
from unittest.mock import Mock

import pytest

from ms_appkit import bootstrap, configure, settings
from ms_appkit.shell import AppWindow
from ms_appkit.update.checker import CheckOutcome, Release


@pytest.fixture(scope="module")
def qt():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt, tmp_path, monkeypatch):
    configure(name="Lifecycle test", repo="Machine-Saver-Inc/test", version="1.0.0")
    monkeypatch.setattr(settings, "settings_path", lambda: tmp_path / "settings.json")
    made = AppWindow()
    yield made
    made.close()


def release():
    return Release("2.0.0", "v2.0.0", "Changes", "https://example.invalid", {}, None)


def test_bootstrap_keeps_the_window_alive_during_the_event_loop(qt, monkeypatch):
    from PySide6.QtWidgets import QApplication, QWidget

    references = []
    def make():
        widget = QWidget()
        references.append(weakref.ref(widget))
        return widget

    def event_loop(self):
        gc.collect()
        assert references[0]() is not None
        references[0]().close()
        return 0

    monkeypatch.setattr(bootstrap, "start_logging", lambda: None)
    monkeypatch.setattr(QApplication, "exec", event_loop)
    assert bootstrap.run("Test", "owner/repo", "1.0.0", make, argv=["test"]) == 0


def test_update_found_during_work_waits_until_the_job_finishes(window):
    working = True
    window.busy = lambda: "a job is running" if working else None
    offered = release()
    window._on_check_done(CheckOutcome(release=offered), announce=False)
    assert window.banner.isHidden()
    working = False
    window.refresh_busy_state()
    assert not window.banner.isHidden()
    assert window.banner._release is offered


def test_finished_download_cannot_install_after_work_starts(window, monkeypatch, tmp_path):
    from ms_appkit import shell

    window.busy = lambda: "a job is running"
    install = Mock()
    monkeypatch.setattr(shell, "apply_update", install)
    monkeypatch.setattr(shell.QMessageBox, "information", lambda *args: None)
    window._apply(tmp_path / "installer.exe")
    install.assert_not_called()
    assert not window._updating


def test_reporting_still_opens_when_application_context_is_broken(window, monkeypatch):
    from ms_appkit import shell

    window.report_context = Mock(side_effect=RuntimeError("broken chamber record"))
    dialog = Mock()
    monkeypatch.setattr(shell, "ReportDialog", dialog)
    window.report_problem()
    dialog.return_value.exec.assert_called_once()
    assert "Could not gather state" in dialog.call_args.args[0]


def test_repeated_check_does_not_discard_a_running_worker(window, monkeypatch):
    from ms_appkit import shell

    worker = Mock()
    worker.isRunning.return_value = True
    window._check = worker
    factory = Mock()
    monkeypatch.setattr(shell, "UpdateWorker", factory)
    window._run_check(announce=True)
    factory.assert_not_called()
    window._check = None


@pytest.mark.parametrize("attribute", ["_check", "_download"])
def test_close_keeps_running_network_workers_alive(window, attribute):
    from PySide6.QtGui import QCloseEvent
    worker = Mock()
    worker.isRunning.return_value = True
    setattr(window, attribute, worker)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    worker.finished.connect.assert_called_once_with(window.close)
    if attribute == "_download":
        worker.cancel.assert_called_once()
    worker.isRunning.return_value = False
    window.closeEvent(event)
    assert event.isAccepted()
    setattr(window, attribute, None)


@pytest.mark.parametrize("dark,background", [(False, "#efefef"), (True, "#24282e")])
def test_helper_and_status_text_have_readable_contrast(dark, background):
    import re

    from ms_appkit.style import build_stylesheet

    def luminance(color):
        rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722), strict=True))

    stylesheet = build_stylesheet(dark)
    for role in ("Hint", "Subtitle", "StatusGood", "StatusWarn", "StatusBad"):
        rule = re.search(r"QLabel#" + role + r"\s*\{([^}]+)", stylesheet).group(1)
        color = re.search(r"color:\s*(#[0-9a-f]+)", rule).group(1)
        low, high = sorted((luminance(color), luminance(background)))
        assert (high + .05) / (low + .05) >= 4.5, (role, dark)
