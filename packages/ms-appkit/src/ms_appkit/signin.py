"""The sign-in screen a private program shows before anything else.

:func:`gate` is what ``bootstrap.run`` calls for a private program before it
builds the window. It asks Google whether the stored sign-in still stands; if it
does -- or the computer is offline inside the grace period -- it returns at
once and the program opens. Otherwise it shows :class:`SignInDialog`, and the
program's window is built only if the person signs in with an account from the
right domain.

The flow itself lives in :mod:`ms_appkit.auth`, which has no Qt in it. This
module is only the screen and the thread the browser round trip waits on.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from ms_appkit import auth
from ms_appkit.identity import app
from ms_appkit.widgets import action_bar, button, subtitle, title


class _SignInWorker(QThread):
    finished_ok = Signal(object)      # auth.Status
    failed = Signal(str)

    def __init__(self, session: auth.Auth) -> None:
        super().__init__()
        self.session = session

    def run(self) -> None:
        try:
            self.finished_ok.emit(self.session.sign_in())
        except auth.SignInError as exc:
            self.failed.emit(str(exc))


class SignInDialog(QDialog):
    """Name the program, say why, one button to Google."""

    def __init__(self, session: auth.Auth, reason: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.status: auth.Status | None = None
        info = app()
        self.setWindowTitle(f"{info.name} {info.version}")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(title(info.name))
        layout.addWidget(subtitle(
            f"Sign in with your {session.config.domain} Google account to use "
            f"this program. Your browser will open; come back here when it says "
            f"you can close the tab."
        ))
        self.message = QLabel(reason)
        self.message.setWordWrap(True)
        self.message.setObjectName("StatusWarn" if reason else "Hint")
        layout.addWidget(self.message)

        # No Back on this screen, so the action that leaves it takes Back's
        # place on the left (skill section 1).
        self.cancel = button("Cancel", "cancel")
        self.sign_in = button("Sign in with Google", "user", "primary")
        self.cancel.clicked.connect(self.reject)
        self.sign_in.clicked.connect(self._start)
        layout.addLayout(action_bar(back=self.cancel, forward=self.sign_in))
        self._worker: _SignInWorker | None = None

    def _start(self) -> None:
        self.sign_in.setEnabled(False)
        self.message.setObjectName("Hint")
        self.message.setText("Waiting for you to finish signing in in your browser…")
        self._restyle()
        self._worker = _SignInWorker(self.session)
        self._worker.finished_ok.connect(self._done)
        self._worker.failed.connect(self._failed)
        self._worker.start()

    def _done(self, status: auth.Status) -> None:
        self.status = status
        self.accept()

    def _failed(self, reason: str) -> None:
        self.sign_in.setEnabled(True)
        self.message.setObjectName("StatusWarn")
        self.message.setText(reason)
        self._restyle()

    def _restyle(self) -> None:
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)


def gate(session: auth.Auth | None = None, dialog=SignInDialog) -> bool:
    """Whether a private program may build its window. Blocks on the dialog."""
    session = session or auth.current()
    status = session.status()
    if status.may_open:
        return True
    shown = dialog(session, reason=status.message)
    return bool(shown.exec()) and shown.status is not None and shown.status.may_open
