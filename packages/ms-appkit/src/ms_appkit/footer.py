"""The standing footer every Machine Saver program carries.

    [Report a problem]        (logo) Created by Machine Saver Inc        Version 1.4.0 - last checked 18 Sep 2026 14:02  [Check for updates]

Three things, in these three places, on every screen of every program, never
scrolling away:

* **Report a problem**, bottom left, because someone who has found the button
  in one of these tools has found it in all of them.
* **Who made it**, in the middle, with the mark.
* **Which version is running**, bottom right, with the means to change it. A
  machine with no internet is never told about a release, so somebody has to be
  able to read the version out over the phone from whichever screen they are
  on. This is why the version line does not live on the home page.

The footer is built here rather than on each window so that it cannot drift.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ms_appkit.identity import app
from ms_appkit.widgets import button, maker_mark

SEPARATOR = "·"


class Footer(QWidget):
    """Report, maker mark, version, check for updates. In that order."""

    report_requested = Signal()
    check_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 6, 14, 10)
        row.setSpacing(10)

        self.report_button = button("Report a problem", "report")
        self.report_button.setObjectName("Report")
        self.report_button.setToolTip(
            "Report a bug or suggest an improvement, with the program's current "
            "state filled in for you"
        )
        self.report_button.clicked.connect(self.report_requested)
        row.addWidget(self.report_button)

        row.addStretch(1)
        row.addWidget(maker_mark())
        row.addStretch(1)

        self.version_label = QLabel("")
        self.version_label.setObjectName("Hint")
        row.addWidget(self.version_label)

        self.check_now = button("Check for updates", "refresh")
        self.check_now.clicked.connect(self.check_requested)
        row.addWidget(self.check_now)

        self.set_version_line(None)

    def set_version_line(self, last_checked: str | None,
                         failed: bool = False, version: str = "") -> None:
        """The version, and when it was last measured against the releases feed.

        "Could not reach GitHub" and "you are up to date" are different facts,
        and showing the reassuring one when the truthful one is the other is how
        a broken updater goes unnoticed for a year.
        """
        if failed:
            when = f" {SEPARATOR} could not reach GitHub to check"
        elif last_checked:
            when = f" {SEPARATOR} last checked {last_checked}"
        else:
            when = f" {SEPARATOR} not checked yet"
        self.version_label.setText(f"Version {version or app().version}{when}")
        self.version_label.setObjectName("StatusWarn" if failed else "Hint")
        self.version_label.style().polish(self.version_label)
