"""The screens. Everything on them comes from the kit's widgets."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ms_appkit.widgets import (
    FieldGroup,
    action_bar,
    button,
    check,
    editable_choice,
    primary,
    subtitle,
    title,
)


class HomePage(QWidget):
    start_requested = Signal()
    settings_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 18)
        outer.setSpacing(14)

        outer.addWidget(title("Example Tool"))
        outer.addWidget(subtitle(
            "One sentence saying what this tool does and when somebody would "
            "reach for it."
        ))
        outer.addStretch(1)

        start = primary("Start", "start")
        start.clicked.connect(self.start_requested)
        settings = button("Settings", "settings")
        settings.clicked.connect(self.settings_requested)
        # Nothing to go back to from the first screen, so the leftmost slot
        # stays empty and the forward action keeps its place on the right.
        outer.addLayout(action_bar(forward=start, extras=[settings]))


class SettingsPage(QWidget):
    saved = Signal(dict)
    back = Signal()

    def __init__(self, settings: dict) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 18)
        outer.setSpacing(14)

        outer.addWidget(title("Settings"))

        group = FieldGroup("Device", "Which one this computer talks to.")
        self.port = editable_choice(["COM3", "COM4"], settings.get("port") or "",
                                    placeholder="COM3")
        group.add_row("Port", self.port,
                      "Remembered by the adapter, not by the number Windows "
                      "happens to give it today.")
        outer.addWidget(group)

        updates = FieldGroup("Updates")
        self.check_updates = check(
            "Check for a newer version when the program opens",
            settings.get("check_for_updates", True),
        )
        updates.add(self.check_updates)
        outer.addWidget(updates)
        outer.addStretch(1)

        back = button("Back", "back")
        back.clicked.connect(self.back)
        save = primary("Save", "save")
        save.clicked.connect(self._save)
        outer.addLayout(action_bar(back=back, forward=save))

    def _save(self) -> None:
        self.saved.emit({
            "port": self.port.currentText().strip() or None,
            "check_for_updates": self.check_updates.isChecked(),
        })
