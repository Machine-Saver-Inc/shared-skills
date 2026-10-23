"""The report-a-problem dialog, the same in every Machine Saver program.

An employee who has reported a problem from one of these tools has reported a
problem from all of them, and from the apps catalog on the web and the mobile
apps too: the button is in the same corner, the form asks the same questions
in the same words (``resources/report_form.json``, one file for the whole
family), screenshots can be pasted or files attached, and the preview shows
exactly what will be sent before anything leaves the machine. The report goes
to Machine Saver's report intake, which files it; the person never needs a
GitHub account or an email program.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QObject, Qt, QThread, Signal
from PySide6.QtGui import QGuiApplication, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ms_appkit import report_form
from ms_appkit.diagnostics import Report, read_log_tail
from ms_appkit.identity import app
from ms_appkit.report_form import Attachment, IntakeError, Submission
from ms_appkit.trail import TRAIL
from ms_appkit.widgets import button

log = logging.getLogger(__name__)

THUMB = 40


class _Sender(QObject):
    """Posts the report off the interface thread; the dialog stays responsive."""

    done = Signal(object)        # Sent
    failed = Signal(str)

    def __init__(self, submission: Submission) -> None:
        super().__init__()
        self.submission = submission

    def run(self) -> None:
        try:
            self.done.emit(report_form.send(self.submission))
        except IntakeError as error:
            self.failed.emit(str(error))
        except Exception as error:  # noqa: BLE001 - a report must never crash the program
            log.exception("sending a report failed")
            self.failed.emit(str(error))


class ReportDialog(QDialog):
    """The family's form: kind, one line, what happened, email, files; then send."""

    def __init__(self, context: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.form = report_form.form()
        words, fields = self.form["wording"], self.form["fields"]
        info = app()
        self.setWindowTitle(words["heading"].replace("{app}", info.name))
        self.setMinimumWidth(640)
        self.setAcceptDrops(True)

        self.report = Report(context=context, trail=TRAIL.lines(), log_tail=read_log_tail())
        self.attachments: list[Attachment] = []
        self._thread: QThread | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        heading = QLabel(words["heading"].replace("{app}", info.name))
        heading.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(heading)
        intro = QLabel(words["intro"])
        intro.setWordWrap(True)
        intro.setObjectName("Subtitle")
        layout.addWidget(intro)

        grid = QFormLayout()
        grid.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.kind = QComboBox()
        for kind in self.form["kinds"]:
            self.kind.addItem(kind["label"], kind["value"])
        self.kind.currentIndexChanged.connect(self._refresh)
        grid.addRow(fields["kind"]["label"], self.kind)

        version = QLabel(info.version)
        grid.addRow(fields["app_version"]["label"], version)

        self.summary = QLineEdit()
        self.summary.setMaxLength(fields["title"]["max_length"])
        self.summary.setPlaceholderText(fields["title"]["placeholder"])
        self.summary.textChanged.connect(self._refresh)
        grid.addRow(fields["title"]["label"], self.summary)

        self.description = QPlainTextEdit()
        self.description.setPlaceholderText(fields["body_markdown"]["placeholder"])
        self.description.setMinimumHeight(90)
        self.description.textChanged.connect(self._refresh)
        grid.addRow(fields["body_markdown"]["label"], self.description)

        self.email = QLineEdit()
        self.email.setPlaceholderText(fields["email"]["note"])
        grid.addRow(fields["email"]["label"], self.email)
        layout.addLayout(grid)

        # Files: paste (Ctrl+V anywhere in the dialog, or the button), drop, choose.
        files_label = QLabel(f"{fields['files']['label']} ({fields['files']['note']})")
        files_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(files_label)
        row = QHBoxLayout()
        self.paste = button("Paste a screenshot", "clipboard")
        self.paste.clicked.connect(self.paste_screenshot)
        self.choose = button("Choose files", "upload")
        self.choose.clicked.connect(self._choose)
        self.remove = button("Remove", "remove")
        self.remove.clicked.connect(self._remove)
        self.remove.setEnabled(False)
        row.addWidget(self.paste)
        row.addWidget(self.choose)
        row.addWidget(self.remove)
        row.addStretch(1)
        layout.addLayout(row)
        self.files = QListWidget()
        self.files.setMaximumHeight(96)
        self.files.setIconSize(QPixmap(THUMB, THUMB).size())
        self.files.itemSelectionChanged.connect(
            lambda: self.remove.setEnabled(bool(self.files.selectedItems())))
        layout.addWidget(self.files)
        hint = QLabel(self.form["attachments"]["hint"])
        hint.setObjectName("Subtitle")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.refused = QLabel("")
        self.refused.setWordWrap(True)
        self.refused.setStyleSheet("color: #b42318;")
        self.refused.hide()
        layout.addWidget(self.refused)
        QShortcut(QKeySequence.Paste, self, activated=self._paste_shortcut)

        self.note = QLabel(words["details_note"])
        self.note.setWordWrap(True)
        self.note.setObjectName("Subtitle")
        layout.addWidget(self.note)

        # Editable, not just visible: what is sent is what this box says.
        self.preview = QPlainTextEdit()
        self.preview.setMinimumHeight(140)
        self._edited = False
        self._loading = False
        self.preview.textChanged.connect(self._preview_edited)
        layout.addWidget(self.preview, 1)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)

        buttons = QDialogButtonBox()
        self.post = button(words["send"], "send", "primary")
        buttons.addButton(self.post, QDialogButtonBox.AcceptRole)
        self.copy = button(words["copy"], "copy")
        buttons.addButton(self.copy, QDialogButtonBox.ActionRole)
        buttons.addButton(button(words["cancel"], "cancel"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._post)
        buttons.rejected.connect(self.reject)
        self.copy.clicked.connect(self._copy)
        layout.addWidget(buttons)

        self._refresh()

    # -- the text ------------------------------------------------------------
    def _current(self) -> Report:
        self.report.kind = self.kind.currentData() or "bug"
        self.report.summary = self.summary.text()
        self.report.description = self.description.toPlainText()
        return self.report

    def _preview_edited(self) -> None:
        """Once it has been touched by hand, the program stops rewriting it."""
        if not self._loading:
            self._edited = True
            self.note.setText("You have edited the report below. What is sent is exactly "
                              "what it says now.")

    def _text(self) -> str:
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

    # -- files ---------------------------------------------------------------
    def add_attachment(self, attachment: Attachment) -> bool:
        """Attach a file if the family's limits allow it; say why otherwise."""
        why = report_form.refusal(self.attachments, attachment, self.form["attachments"])
        if why:
            self.refused.setText(why)
            self.refused.show()
            return False
        self.refused.hide()
        self.attachments.append(attachment)
        item = QListWidgetItem(f"{attachment.name}  ({len(attachment.data) / 1024:.0f} KB)")
        image = QImage.fromData(attachment.data) if attachment.content_type.startswith("image/") else QImage()
        if not image.isNull():
            # QIcon(QImage) yields a null icon silently; go through QPixmap.
            item.setIcon(QPixmap.fromImage(image.scaled(THUMB, THUMB, Qt.KeepAspectRatio)))
        self.files.addItem(item)
        return True

    def paste_screenshot(self) -> bool:
        """The clipboard's image, if it holds one, as paste-N.png."""
        image = QGuiApplication.clipboard().image()
        if image.isNull():
            self.refused.setText(f"{self.form['wording']['refused_prefix']}there is no picture on "
                                 "the clipboard. Take a screenshot first (Windows: Win+Shift+S).")
            self.refused.show()
            return False
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        return self.add_attachment(
            Attachment(report_form.next_paste_name(self.attachments), bytes(buffer.data())))

    def _paste_shortcut(self) -> None:
        # Ctrl+V in a text box pastes text there; only a picture becomes a file.
        if not QGuiApplication.clipboard().image().isNull():
            self.paste_screenshot()
        elif focused := self.focusWidget():
            if hasattr(focused, "paste"):
                focused.paste()

    def _choose(self) -> None:
        extensions = " ".join(f"*.{e}" for e in self.form["attachments"]["extensions"])
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Choose files", "", f"Screenshots and files ({extensions})")
        for path in paths:
            self.add_attachment(Attachment.from_path(Path(path)))

    def _remove(self) -> None:
        for item in self.files.selectedItems():
            index = self.files.row(item)
            self.files.takeItem(index)
            del self.attachments[index]
        self.refused.hide()

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt's name
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt's name
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.add_attachment(Attachment.from_path(Path(url.toLocalFile())))
        event.acceptProposedAction()

    # -- sending -------------------------------------------------------------
    def submission(self) -> Submission:
        return Submission(report=self._current(), email=self.email.text(),
                          attachments=list(self.attachments),
                          edited_text=self._text() if self._edited else None)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._text())
        QMessageBox.information(self, "Copied", "The whole report is on your clipboard.")

    def _post(self) -> None:
        # On the clipboard first: whatever the network does, nothing is lost.
        QGuiApplication.clipboard().setText(self._text())
        self.post.setEnabled(False)
        self.status.setText(self.form["wording"]["sending"])
        self.status.show()
        self._thread = QThread(self)
        self._sender = _Sender(self.submission())
        self._sender.moveToThread(self._thread)
        self._thread.started.connect(self._sender.run)
        self._sender.done.connect(self._sent)
        self._sender.failed.connect(self._not_sent)
        self._thread.start()

    def _finish_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
            self._thread = None

    def _sent(self, sent) -> None:
        self._finish_thread()
        QMessageBox.information(self, "Sent", report_form.received_wording(sent))
        self.accept()

    def _not_sent(self, why: str) -> None:
        self._finish_thread()
        self.post.setEnabled(True)
        words = self.form["wording"]
        support = app().private.support_email if app().private else "software-support@machinesaver.net"
        self.status.setText(words["failed"].replace("{support_email}", support) + f"\n({why})")
        self.status.show()
        log.warning("report not sent: %s", why)
