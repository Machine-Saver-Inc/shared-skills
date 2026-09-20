"""The controls every Machine Saver program is built from.

Nothing here is specific to one application. A program that needs a control of
its own builds it in its own package; it does not restyle one of these, because
a button that looks slightly different in one program is how a set of tools
stops feeling like a set of tools.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# A number box holds a reading or a count -- a few characters. Stretched across
# the window it reads as a text field and puts the stepper arrows a hand's
# width from the digits.
NUMBER_WIDTH = 112
TEXT_WIDTH = 360
LABEL_WIDTH = 160


def _tabular(widget: QWidget) -> None:
    """Lining figures of equal width, so a column of readings lines up.

    A proportional 1 beside an 8 in a column of readings is a legibility fault,
    not a matter of taste; instrument readouts have always used tabular figures
    and a screen full of live numbers is an instrument readout.
    """
    font = widget.font()
    try:
        font.setFeature(QFont.Tag("tnum"), 1)   # Qt 6.7 and later
    except (AttributeError, TypeError, ValueError):
        # Older Qt has no font-feature API. The boxes are a fixed width and
        # right-aligned regardless, so the columns still line up at their
        # right edge; only the digits inside them can shift.
        pass
    widget.setFont(font)


def title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Title")
    return label


def subtitle(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Subtitle")
    label.setWordWrap(True)
    return label


def _text_colour(role: str) -> str:
    """The colour the icon has to match: the button's own text."""
    if role == "primary":
        return "#ffffff"
    application = QApplication.instance()
    if role == "danger":
        from ms_appkit.style import BAD

        return BAD
    if application is None:
        return "#1a1a1a"
    return application.palette().color(QPalette.ButtonText).name()


def button(text: str, glyph: str = "", role: str = "secondary") -> QPushButton:
    """A button that looks like one, with its mark on the left.

    Every button in the program comes from here so they cannot drift apart
    again - the complaint that started this was that some were filled, some
    were outlined and some were bare words with nothing to press.
    """
    made = QPushButton(text)
    if role == "primary":
        made.setObjectName("Primary")
    elif role == "danger":
        made.setObjectName("Danger")
    if glyph:
        from ms_appkit.icons import SIZE, icon

        made.setIcon(icon(glyph, _text_colour(role), SIZE))
        made.setIconSize(QSize(SIZE, SIZE))

    # Every button in the program is made here, which is the one place a
    # press can be noted without asking each screen to remember to do it.
    from ms_appkit.trail import TRAIL

    made.clicked.connect(lambda *_, label=text: TRAIL.pressed(label))
    return made


def primary(text: str, glyph: str = "forward") -> QPushButton:
    return button(text, glyph, "primary")


def maker_mark() -> QWidget:
    """Who made this, in the footer of every Machine Saver program."""
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(7)

    logo = QLabel()
    path = Path(__file__).resolve().parent / "resources" / "machine-saver.png"
    if path.is_file():
        pixmap = QPixmap(str(path)).scaledToHeight(
            24, Qt.SmoothTransformation
        )
        logo.setPixmap(pixmap)
    row.addWidget(logo)

    from ms_appkit.identity import app

    text = QLabel(f"Created by {app().organisation}")
    text.setObjectName("Hint")
    row.addWidget(text)
    return holder


def action_bar(back: QPushButton | None = None,
               forward: QPushButton | None = None,
               extras: Sequence[QPushButton] = ()) -> QHBoxLayout:
    """The row of actions at the foot of a screen, in one fixed order.

    **Back on the left, the action that moves forward on the right.** That is
    what every other application on the machine does, and it was the other way
    round here until somebody said so. Built in one place because six screens
    each arranging their own row is six chances to disagree.

        [Back]                        [secondary] [secondary] [Forward]
    """
    row = QHBoxLayout()
    row.setSpacing(10)
    if back is not None:
        row.addWidget(back)
    row.addStretch(1)
    for extra in extras:
        row.addWidget(extra)
    if forward is not None:
        row.addWidget(forward)
    return row


def field_row(label: str, widget: QWidget, hint: str = "",
              stretch: bool = False) -> QWidget:
    """One labelled control, with an optional explanation underneath.

    The label sits against the control rather than across the window, and the
    control keeps the width its value needs. A two-digit number in a box as
    wide as the window tells the reader it expects a sentence.
    """
    holder = QWidget()
    outer = QVBoxLayout(holder)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(3)

    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)
    name = QLabel(label)
    name.setObjectName("FieldLabel")
    name.setFixedWidth(LABEL_WIDTH)
    name.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    name.setWordWrap(True)
    row.addWidget(name, 0, Qt.AlignTop)
    row.addWidget(widget, 1 if stretch else 0)
    if not stretch:
        row.addStretch(1)
    outer.addLayout(row)

    if hint:
        note = QLabel(hint)
        note.setObjectName("Hint")
        note.setWordWrap(True)
        note.setContentsMargins(LABEL_WIDTH + 12, 0, 0, 0)
        outer.addWidget(note)
    return holder


class Disclosure(QWidget):
    """A summary of some settings, with the settings themselves behind a link.

    For a group that states one fact in several fields - a serial link is
    "19200 8-N-1", not four separate decisions. The summary is the answer;
    the fields are there for the rare machine where it is wrong.
    """

    def __init__(self, summary: str, opener: str = "Change") -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        row = QHBoxLayout()
        # Indented to the column the values live in: the summary is a value,
        # not a label, and the column should hold down the page.
        row.setContentsMargins(LABEL_WIDTH + 12, 0, 0, 0)
        row.setSpacing(12)
        self.summary = QLabel(summary)
        self.summary.setObjectName("FieldLabel")
        row.addWidget(self.summary)
        self.opener = button(opener, "edit")
        self.opener.setCheckable(True)
        self.opener.setObjectName("Report")
        self.opener.toggled.connect(self._on_toggled)
        row.addWidget(self.opener)
        row.addStretch(1)
        outer.addLayout(row)

        self.body = QWidget()
        self.body.setVisible(False)
        self.content = QVBoxLayout(self.body)
        self.content.setContentsMargins(0, 0, 0, 0)
        self.content.setSpacing(10)
        outer.addWidget(self.body)

    def _on_toggled(self, shown: bool) -> None:
        self.body.setVisible(shown)

    def add(self, widget: QWidget) -> QWidget:
        self.content.addWidget(widget)
        return widget

    def add_row(self, label: str, widget: QWidget, hint: str = "",
                stretch: bool = False) -> QWidget:
        return self.add(field_row(label, widget, hint, stretch))

    def set_summary(self, text: str) -> None:
        self.summary.setText(text)


class FieldGroup(QWidget):
    """A named set of fields.

    The name sits on a hairline that runs the width of the form and the fields
    are inset beneath it. A rounded card with a shadow round every group would
    give each the same weight, which is the opposite of grouping.
    """

    def __init__(self, name: str, hint: str = "") -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(10)
        legend = QLabel(name)
        legend.setObjectName("GroupName")
        head.addWidget(legend)
        rule = QFrame()
        rule.setObjectName("GroupRule")
        rule.setFixedHeight(1)
        rule.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        head.addWidget(rule, 1)
        outer.addLayout(head)

        if hint:
            note = QLabel(hint)
            note.setObjectName("Hint")
            note.setWordWrap(True)
            outer.addWidget(note)

        self.body = QWidget()
        self.content = QVBoxLayout(self.body)
        self.content.setContentsMargins(0, 2, 0, 0)
        self.content.setSpacing(10)
        outer.addWidget(self.body)

    def add(self, widget: QWidget) -> QWidget:
        self.content.addWidget(widget)
        return widget

    def add_row(self, label: str, widget: QWidget, hint: str = "",
                stretch: bool = False) -> QWidget:
        return self.add(field_row(label, widget, hint, stretch))

    def add_note(self, text: str) -> QWidget:
        note = QLabel(text)
        note.setObjectName("Hint")
        note.setWordWrap(True)
        return self.add(note)


def _number_box(box: QAbstractSpinBox) -> QAbstractSpinBox:
    box.setFixedWidth(NUMBER_WIDTH)
    box.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    _tabular(box)
    return box


def spin(value: float, low: float, high: float, *, step: float = 1.0,
         decimals: int = 0, suffix: str = "") -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(low, high)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setSuffix(suffix)
    box.setValue(value)
    _number_box(box)
    return box


def int_spin(value: int, low: int, high: int, suffix: str = "") -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    box.setSuffix(suffix)
    box.setValue(int(value))
    _number_box(box)
    return box


def choice(options: list[str], current: str) -> QComboBox:
    """A short list of fixed values. Sized to its longest option, not the window."""
    box = QComboBox()
    box.addItems(options)
    if current in options:
        box.setCurrentText(current)
    box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
    box.setMinimumWidth(NUMBER_WIDTH)
    box.setMaximumWidth(TEXT_WIDTH)
    box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    return box


def check(text: str, value: bool) -> QCheckBox:
    box = QCheckBox(text)
    box.setChecked(bool(value))
    return box


def editable_choice(options: list[str], current: str = "",
                    placeholder: str = "") -> QComboBox:
    """A combo you can also type into — pick a known value or enter a new one."""
    box = QComboBox()
    box.setEditable(True)
    box.setInsertPolicy(QComboBox.NoInsert)
    box.addItems([o for o in options if o])
    # An empty list would otherwise size the box to nothing, and the example
    # in the placeholder - the thing telling the user what to type - is the
    # first casualty.
    box.setMinimumWidth(260)
    box.setMaximumWidth(TEXT_WIDTH)
    if placeholder:
        box.lineEdit().setPlaceholderText(placeholder)
    box.setCurrentText(current)
    return box
