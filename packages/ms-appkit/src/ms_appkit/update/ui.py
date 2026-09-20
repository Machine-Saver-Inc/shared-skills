"""The update banner and the threads behind it.

Off the GUI thread, because a chamber PC behind a corporate proxy can take
fifteen seconds to be told there is nothing new.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox

from ms_appkit.update.checker import Release, check_for_update_detailed
from ms_appkit.update.installer import UpdateError, download_asset, verify_download
from ms_appkit.widgets import button


class UpdateWorker(QThread):
    """Reports what the check established, not just the happy case."""

    done = Signal(object)          # CheckOutcome

    def run(self) -> None:
        self.done.emit(check_for_update_detailed())


class DownloadWorker(QThread):
    """Fetch and verify an update off the GUI thread."""

    progress = Signal(int, int)
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, release: Release) -> None:
        super().__init__()
        self.release = release
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        def report(done: int, total: int) -> None:
            if self._cancelled:
                raise UpdateError("cancelled")
            self.progress.emit(done, total)

        try:
            path = download_asset(self.release, progress=report)
            verify_download(path, self.release)
        except UpdateError as exc:
            if not self._cancelled:
                self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self.failed.emit(str(exc))
            return
        self.ready.emit(path)


class UpdateBanner(QFrame):
    """A strip above the content saying a newer version exists.

    Above the content and not in it, so no screen has to make room for it and
    no screen can hide it.
    """

    update_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Banner")
        self.hide()
        self._release: Release | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        self.label = QLabel("")
        layout.addWidget(self.label)
        layout.addStretch(1)

        notes = button("What's new", "notes")
        notes.clicked.connect(self._show_notes)
        layout.addWidget(notes)

        update = button("Update now", "download", "primary")
        update.clicked.connect(self._open_release)
        layout.addWidget(update)

        later = button("Later", "later")
        later.clicked.connect(self.hide)
        layout.addWidget(later)

    def offer(self, release: Release) -> None:
        self._release = release
        self.label.setText(f"Version {release.version} is available.")
        self.show()

    def _show_notes(self) -> None:
        if self._release:
            QMessageBox.information(
                self, f"What's new in {self._release.version}",
                self._release.notes or "No release notes were provided.",
            )

    def _open_release(self) -> None:
        if self._release:
            self.update_requested.emit(self._release)
