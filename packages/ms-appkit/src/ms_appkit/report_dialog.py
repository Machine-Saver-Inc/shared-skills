"""The report-a-problem dialog, the same in every Machine Saver program.

An employee who has reported a problem from one of these tools has reported a
problem from all of them: the button is in the same corner, the dialog asks the
same two questions, and the preview shows exactly what will be posted before
anything leaves the machine -- because the repository is public and the report
carries details of this computer.
"""

from __future__ import annotations

import logging
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ms_appkit.diagnostics import Report, issue_url, mail_url, read_log_tail
from ms_appkit.identity import app
from ms_appkit.trail import TRAIL
from ms_appkit.widgets import button

log = logging.getLogger(__name__)

class ReportDialog(QDialog):
    """Pick bug or improvement, describe it, see what will be sent, post it."""

    def __init__(self, context: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Report a problem or an idea")
        self.setMinimumWidth(620)

        self.report = Report(
            context=context, trail=TRAIL.lines(), log_tail=read_log_tail()
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        heading = QLabel("What would you like to report?")
        heading.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(heading)

        self.bug = QRadioButton("A bug — the program did something wrong")
        self.improvement = QRadioButton("An improvement — something would work better")
        self.bug.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.bug)
        group.addButton(self.improvement)
        layout.addWidget(self.bug)
        layout.addWidget(self.improvement)
        self.bug.toggled.connect(self._refresh)

        self.summary = QLineEdit()
        self.summary.setPlaceholderText("One line: what went wrong, or what would help")
        self.summary.textChanged.connect(self._refresh)
        layout.addWidget(self.summary)

        self.description = QPlainTextEdit()
        self.description.setPlaceholderText(
            "What were you doing, and what did you see? Anything you already tried."
        )
        self.description.setMinimumHeight(110)
        self.description.textChanged.connect(self._refresh)
        layout.addWidget(self.description)

        # A private program's operator has no GitHub account; the report goes
        # to the support group by email instead (skill section 1a).
        self.private = app().is_private and app().private is not None
        where = (
            f"It goes by email to {app().private.support_email}."
            if self.private else
            "This repository is public, so check you are happy with it."
        )
        self.note = QLabel(
            "The details below are collected automatically and go with the report, "
            "including which screens you opened and which buttons you pressed. "
            f"Edit anything you like — what is sent is what this box says. {where} "
            "Paths under your home folder are shortened to <code>~</code>, and "
            "anything that looks like a password or sign-in token is removed."
        )
        self.note.setWordWrap(True)
        self.note.setTextFormat(Qt.RichText)
        self.note.setObjectName("Subtitle")
        layout.addWidget(self.note)

        # Editable, not just visible. The report is about to be posted to a
        # public repository under the user's name; being able to add a line or
        # take one out is the difference between showing someone their data
        # and letting them decide about it.
        self.preview = QPlainTextEdit()
        self.preview.setMinimumHeight(180)
        self._edited = False
        self._loading = False
        self.preview.textChanged.connect(self._preview_edited)
        layout.addWidget(self.preview, 1)

        # Built from the shared button so the three read as the same kind of
        # control. They used to be a filled one and two bare words.
        buttons = QDialogButtonBox()
        if self.private:
            self.post = button("Email it to support", "mail", "primary")
        else:
            self.post = button("Open GitHub to post it", "open", "primary")
        buttons.addButton(self.post, QDialogButtonBox.AcceptRole)
        self.copy = button("Copy to clipboard", "copy")
        buttons.addButton(self.copy, QDialogButtonBox.ActionRole)
        buttons.addButton(button("Cancel", "cancel"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._post)
        buttons.rejected.connect(self.reject)
        self.copy.clicked.connect(self._copy)
        layout.addWidget(buttons)

        self._refresh()

    # -- assembling ----------------------------------------------------------
    def _current(self) -> Report:
        self.report.kind = "bug" if self.bug.isChecked() else "improvement"
        self.report.summary = self.summary.text()
        self.report.description = self.description.toPlainText()
        return self.report

    def _preview_edited(self) -> None:
        """Once it has been touched by hand, the program stops rewriting it."""
        if not self._loading:
            self._edited = True
            self.note.setText(
                "You have edited the report below. What is posted is exactly "
                "what it says now."
            )

    def _text(self) -> str:
        """What will actually be posted."""
        if self._edited:
            return self.preview.toPlainText()
        report = self._current()
        return f"{report.title}\n\n{report.body()}"

    def _refresh(self) -> None:
        self.post.setEnabled(bool(self.summary.text().strip()))
        if self._edited:
            return
        report = self._current()
        self._loading = True
        try:
            self.preview.setPlainText(f"{report.title}\n\n{report.body()}")
        finally:
            self._loading = False

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._text())
        QMessageBox.information(
            self, "Copied",
            "The whole report is on your clipboard. Paste it into a new issue.",
        )

    def _post(self) -> None:
        report = self._current()
        edited = self._text() if self._edited else None
        if self.private:
            url, trimmed = mail_url(report, app().private.support_email, edited=edited)
        else:
            url, trimmed = issue_url(report, edited=edited)

        # On the clipboard either way: if the log had to be dropped to fit the
        # address bar, the full text is still one paste away.
        QGuiApplication.clipboard().setText(self._text())

        if not webbrowser.open(url):
            QMessageBox.warning(
                self, "Could not open your browser" if not self.private
                else "Could not open your email",
                "The full report is on your clipboard. Open the repository's "
                "Issues page and paste it into a new issue." if not self.private
                else "The full report is on your clipboard. Paste it into an "
                     f"email to {app().private.support_email}.",
            )
            return

        if trimmed:
            where = "Your email" if self.private else "GitHub"
            QMessageBox.information(
                self, "One thing to paste",
                f"{where} is open with the report started, but it was too long "
                "to fill in completely. The full report is on your clipboard — "
                "paste it in before sending.",
            )
        self.accept()
