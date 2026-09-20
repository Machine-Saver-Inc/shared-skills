"""The window every Machine Saver program is built inside.

    +--------------------------------------------------+
    |  a newer version is available            [banner] |
    +--------------------------------------------------+
    |                                                   |
    |   the screen the program is showing               |
    |                                                   |
    +--------------------------------------------------+
    |  [Report a problem]   (mark)        Version ...   |
    +--------------------------------------------------+

Subclass it, add screens, and the footer, the update banner, the report dialog,
the breadcrumb trail and the version line are all already there and already
behave the same as they do in every other Machine Saver tool.

    class MainWindow(AppWindow):
        def __init__(self):
            super().__init__()
            self.home = HomePage()
            self.HOME = self.add_screen(self.home, "Home")
            self.show_screen(self.HOME)

        def report_context(self):
            return {"Printer": self.printer_name or "none selected"}

        def busy(self):
            return "a label is printing" if self.printing else None

What a program must not do is rebuild any of this. Two of these tools that
disagree about where the report button lives are two tools an employee has to
learn twice.
"""

from __future__ import annotations

import logging
import webbrowser
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ms_appkit import settings as settings_mod
from ms_appkit.footer import Footer
from ms_appkit.identity import app
from ms_appkit.report_dialog import ReportDialog
from ms_appkit.trail import TRAIL
from ms_appkit.update.checker import CheckOutcome, Release, outcome_kind
from ms_appkit.update.installer import Applied, UpdateError, apply_update, relaunch
from ms_appkit.update.ui import DownloadWorker, UpdateBanner, UpdateWorker

log = logging.getLogger(__name__)

# Long enough that it is not competing with the program opening, short enough
# that somebody who opens the tool, does one thing and closes it still hears
# about a release.
CHECK_DELAY_MS = 4000


class AppWindow(QMainWindow):
    """Banner, screens, footer. The parts that are the same everywhere."""

    def __init__(self, defaults: dict | None = None) -> None:
        super().__init__()
        this = app()
        self.setWindowTitle(f"{this.name} {this.version}")
        self.resize(940, 720)

        self.settings = settings_mod.load(defaults)
        self._screen_names: dict[int, str] = {}
        self._pending_release: Release | None = None
        self._check: UpdateWorker | None = None
        self._download: DownloadWorker | None = None
        self._updating = False

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.banner = UpdateBanner()
        self.banner.update_requested.connect(self.download_update)
        outer.addWidget(self.banner)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        self.footer = Footer()
        self.footer.report_requested.connect(self.report_problem)
        self.footer.check_requested.connect(self.check_now)
        outer.addWidget(self.footer)

        self.setCentralWidget(container)

        # Screens are switched from a dozen places; noting it once here means a
        # new route between two screens cannot forget to be recorded.
        self.stack.currentChanged.connect(
            lambda index: TRAIL.opened(self._screen_names.get(index, "?"))
        )
        self.refresh_version_line()

    # -- screens -------------------------------------------------------------
    def add_screen(self, widget: QWidget, name: str) -> int:
        """Add a screen and return its index. The name is what a report says.

        The name is recorded *before* the widget goes in: adding the first
        screen makes it current, which fires the signal that writes the trail,
        and a name recorded afterwards arrives too late -- the first line of
        every report read "opened ?".
        """
        index = self.stack.count()
        self._screen_names[index] = name
        self.stack.addWidget(widget)
        return index

    def show_screen(self, index: int) -> None:
        self.stack.setCurrentIndex(index)

    def current_screen(self) -> str:
        return self._screen_names.get(self.stack.currentIndex(), "?")

    # -- what a program overrides -------------------------------------------
    def report_context(self) -> dict[str, str]:
        """Extra rows for the state table in a problem report.

        Whatever would otherwise be the first question back: which device is
        connected, what it was doing, which file was open.
        """
        return {}

    def busy(self) -> str | None:
        """A reason this is a bad moment, or None.

        Returned as a phrase that completes "Updates are not offered while
        ...". A program that is driving hardware says so here, and the kit will
        not restart it out from under a job.
        """
        return None

    # -- reporting -----------------------------------------------------------
    def report_problem(self) -> None:
        context = {"Screen": self.current_screen(), **self.report_context()}
        ReportDialog(context, self).exec()

    # -- updates -------------------------------------------------------------
    def start_update_check(self, delay_ms: int = CHECK_DELAY_MS) -> None:
        """Check shortly after the window opens, if the user wants that.

        Call this at the end of a subclass's ``__init__``. It is not automatic:
        a program may have something it needs to do first.
        """
        if not self.settings.get("check_for_updates", True):
            return
        from PySide6.QtCore import QTimer

        QTimer.singleShot(delay_ms, self._check_quietly)

    def _check_quietly(self) -> None:
        self._run_check(announce=False)

    def check_now(self) -> None:
        """The footer's button: somebody asking rather than waiting."""
        reason = self.busy()
        if reason:
            QMessageBox.information(
                self, "Not just now",
                f"Updates are not offered while {reason}.",
            )
            return
        self._run_check(announce=True)

    def _run_check(self, announce: bool) -> None:
        self._check = UpdateWorker()
        self._check.done.connect(
            lambda outcome: self._on_check_done(outcome, announce),
            Qt.QueuedConnection,
        )
        self._check.start()

    def _on_check_done(self, outcome: CheckOutcome, announce: bool) -> None:
        kind = outcome_kind(outcome)
        self._record_check(ok=outcome.reached_github)
        if kind == "update" and outcome.release is not None:
            self.banner.offer(outcome.release)
            return
        if not announce:
            return
        if kind == "current":
            QMessageBox.information(
                self, "Up to date",
                f"You are running version {app().version}, which is the newest "
                "release.",
            )
            return
        # "I could not ask" is not "there is nothing new", and saying the
        # second when the first is true is how a broken updater goes unnoticed.
        box = QMessageBox(self)
        box.setWindowTitle("Could not check")
        box.setText(outcome.error or "The update check did not complete.")
        open_page = box.addButton("Open the releases page", QMessageBox.ActionRole)
        box.addButton("Close", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_page and app().releases_page:
            webbrowser.open(app().releases_page)

    def _record_check(self, ok: bool = True) -> None:
        if ok:
            self.settings["last_update_check"] = datetime.now().strftime(
                "%d %b %Y %H:%M"
            )
            self.settings["last_update_check_failed"] = False
        else:
            self.settings["last_update_check_failed"] = True
        settings_mod.save(self.settings)
        self.refresh_version_line()

    def refresh_version_line(self) -> None:
        self.footer.set_version_line(
            self.settings.get("last_update_check"),
            failed=bool(self.settings.get("last_update_check_failed", False)),
        )

    def download_update(self, release: Release) -> None:
        reason = self.busy()
        if reason:
            QMessageBox.information(
                self, "Not just now",
                f"The update will wait until {reason} has finished.",
            )
            return
        self._pending_release = release

        progress = QProgressDialog(
            f"Downloading version {release.version}...", "Cancel", 0, 100, self
        )
        progress.setWindowTitle("Update")
        progress.setAutoClose(False)
        progress.setMinimumDuration(0)

        self._download = DownloadWorker(release)
        self._download.progress.connect(
            lambda done, total: progress.setValue(
                int(done * 100 / total) if total else 0
            ),
            Qt.QueuedConnection,
        )
        self._download.failed.connect(
            lambda message: (progress.close(), self._download_failed(message)),
            Qt.QueuedConnection,
        )
        self._download.ready.connect(
            lambda path: (progress.close(), self._apply(path)),
            Qt.QueuedConnection,
        )
        progress.canceled.connect(self._download.cancel)
        self._download.start()

    def _download_failed(self, message: str) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("The update could not be downloaded")
        box.setText(message)
        open_page = box.addButton("Open the releases page", QMessageBox.ActionRole)
        box.addButton("Close", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_page and app().releases_page:
            webbrowser.open(app().releases_page)

    def _apply(self, path) -> None:
        try:
            result = apply_update(path)
        except UpdateError as exc:
            self._download_failed(str(exc))
            return
        if result.outcome is Applied.MANUAL:
            QMessageBox.information(self, "Downloaded", result.message)
            return
        QMessageBox.information(self, "Updating", result.message)
        if result.outcome is Applied.RESTARTING:
            relaunch(result.path)
        # The installer needs this process gone before it can replace the files
        # it is sitting on, and an AppImage has already been swapped.
        self._updating = True
        self.close()
