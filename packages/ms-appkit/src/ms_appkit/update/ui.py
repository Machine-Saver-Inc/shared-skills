"""The update banner, the window behind **What's new**, and the threads.

The check runs off the GUI thread, because a shop-floor PC behind a corporate
proxy can take fifteen seconds to be told there is nothing new.
"""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ms_appkit.update.checker import Release, check_for_update_detailed
from ms_appkit.update.installer import UpdateError, download_asset, verify_download
from ms_appkit.update.notes import what_changed
from ms_appkit.widgets import action_bar, button

# A window taller than this much of the screen has nowhere left to go, and on
# a laptop it runs off the bottom edge with the buttons on it.
SCREEN_SHARE = 0.6
NOTES_WIDTH = 660
MIN_HEIGHT = 260


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


class NotesWindow(QDialog):
    """What changed in a release, for somebody already running the program.

    It replaces a `QMessageBox.information` holding the raw release body. That
    grew to whatever the text needed -- 2042 pixels on a release with install
    instructions in it -- and a message box does not scroll, so on a laptop the
    bottom half simply was not reachable. It also showed the Markdown as
    source: `## What's new`, `**bold**`, a table drawn in pipes.

    So: the changes only, rendered, in a window that scrolls, resizes, and is
    never taller than part of the screen it has to fit on.
    """

    def __init__(self, release: Release, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.release = release
        self.setWindowTitle(f"What's new in {release.version}")
        self.setSizeGripEnabled(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(12)

        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(True)
        text = what_changed(release.notes)
        if text:
            self.body.setMarkdown(text)
        else:
            self.body.setPlainText("No release notes were provided.")
        outer.addWidget(self.body, 1)

        close = button("Close", "cancel")
        close.clicked.connect(self.reject)
        page = button("Open the release page", "open")
        page.clicked.connect(self._open_page)
        # No Back here, so the action that leaves takes the left-hand place.
        outer.addLayout(action_bar(back=close, forward=page))

        self.resize(NOTES_WIDTH, self._height_that_fits())

    def _height_that_fits(self) -> int:
        """Tall enough for the notes, never taller than the screen allows."""
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry().height() if screen else 800
        ceiling = max(MIN_HEIGHT, int(available * SCREEN_SHARE))
        # What the rendered text actually needs, plus the buttons and margins.
        self.body.document().setTextWidth(NOTES_WIDTH - 60)
        wanted = int(self.body.document().size().height()) + 130
        return max(MIN_HEIGHT, min(wanted, ceiling))

    def _open_page(self) -> None:
        if self.release.html_url:
            webbrowser.open(self.release.html_url)


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
            NotesWindow(self._release, self).exec()

    def _open_release(self) -> None:
        if self._release:
            self.update_requested.emit(self._release)
