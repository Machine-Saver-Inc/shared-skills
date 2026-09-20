"""One stylesheet for every Machine Saver program, light and dark.

The window surface stays the operating system's -- a lab PC set to dark is set
that way for a reason -- so colours here are either theme-independent or come in
a pair and are chosen at startup from the palette the machine hands us.

A program adds its own rules through ``extra``; it does not fork this file.
That is what keeps two Machine Saver applications looking like two Machine
Saver applications rather than two unrelated Qt forms.
"""

from __future__ import annotations

ACCENT = "#2f6feb"
GOOD = "#1a7f37"
WARN = "#9a6700"
BAD = "#b4232c"


def is_dark(application=None) -> bool:
    """Whether the machine is set to a dark theme.

    Asked once at startup and handed to :func:`build_stylesheet`. Reading the
    window colour is more reliable than any per-platform theme query, and it is
    the colour the text actually has to survive against.
    """
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication

    application = application or QApplication.instance()
    if application is None:
        return False
    return application.palette().color(QPalette.Window).lightness() < 128


def build_stylesheet(dark: bool = False, extra: str = "") -> str:
    """The shared look, plus whatever this program adds on top."""
    # palette(mid) is too faint for a border on some Windows themes and too
    # loud on others, so the edge is stated rather than borrowed.
    edge = "#5a6570" if dark else "#bcc3cb"
    sunk = "#2b3138" if dark else "#e9edf1"
    muted = "#2f4470" if dark else "#a9c1ef"
    muted_text = "#8fa3c4" if dark else "#f2f6fd"
    focus_ring = "#9db8ee" if dark else "#14357f"
    danger_wash = "#3a1f22" if dark else "#fdf0f1"
    return f"""
QWidget {{ font-size: 14px; }}
QLabel#Title {{ font-size: 26px; font-weight: 600; }}
QLabel#Subtitle {{ font-size: 15px; color: palette(mid); }}
QLabel#Hint {{ color: palette(mid); font-size: 12px; }}
QLabel#StatusGood {{ color: {GOOD}; font-weight: 600; }}
QLabel#StatusWarn {{ color: {WARN}; font-weight: 600; }}
QLabel#StatusBad {{ color: {BAD}; font-weight: 600; }}

/* Buttons ---------------------------------------------------------------
   Setting padding and a radius without also setting a border and a background
   makes Qt drop the native button look entirely, which is how every secondary
   button in the first of these programs came to render as bare text with
   nothing to click. Each role is described in full here, including its states,
   and the house rules test refuses a partial restyle anywhere else. */
QPushButton {{
    background: palette(base);
    color: palette(text);
    border: 1px solid {edge};
    border-radius: 6px;
    padding: 8px 14px;
    min-height: 18px;
    /* Mark first, then the words. On a button sized to its text this changes
       nothing; in a column of equal-width buttons it is what lines the marks
       up instead of scattering them by label length. */
    text-align: left;
}}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton:pressed {{ background: {sunk}; }}
QPushButton:disabled {{
    color: palette(mid); border-color: {edge}; background: transparent;
}}
QPushButton:focus {{ border: 2px solid {ACCENT}; padding: 7px 13px; }}

QPushButton#Primary {{
    background: {ACCENT}; color: white; font-weight: 600;
    padding: 13px 26px; font-size: 16px; border: 1px solid {ACCENT};
    border-radius: 7px;
}}
QPushButton#Primary:hover {{ background: #2560d0; border-color: #2560d0; }}
QPushButton#Primary:pressed {{ background: #1f52b4; border-color: #1f52b4; }}
/* Muted accent rather than grey: a disabled primary should read as "not yet",
   not as a dead control. */
QPushButton#Primary:disabled {{
    background: {muted}; border-color: {muted}; color: {muted_text};
}}
QPushButton#Primary:focus {{ border: 2px solid {focus_ring}; padding: 12px 25px; }}

QPushButton#Danger {{ color: {BAD}; border-color: {edge}; }}
QPushButton#Danger:hover {{
    border-color: {BAD}; color: {BAD}; background: {danger_wash};
}}

/* The footer's own buttons, which sit under the content rather than in it. */
QPushButton#Report {{ padding: 6px 12px; }}

QFrame#Card {{
    border: 1px solid palette(mid); border-radius: 9px; background: palette(base);
}}
QFrame#Banner {{
    border: 1px solid {ACCENT}; border-radius: 7px; background: palette(base);
}}
QFrame#FooterRule {{ border: none; background: palette(mid); max-height: 1px; }}

QListWidget {{ border: 1px solid palette(mid); border-radius: 7px; padding: 4px; }}
QListWidget::item {{ padding: 9px 8px; border-radius: 5px; }}
/* Without these the selected row uses the inactive palette when the list does
   not have focus, and the item the user just picked renders as a blank bar. */
QListWidget::item:selected {{ background: {ACCENT}; color: white; }}
QListWidget::item:selected:!active {{ background: {ACCENT}; color: white; }}

/* -- grouping ----------------------------------------------------------
   A group is named on a hairline that runs the width of the form, with its
   fields inset underneath. Nine rounded cards with a shadow each would make
   every group look equally important, which is the opposite of grouping. */
QLabel#GroupName {{ font-size: 13px; font-weight: 700; color: palette(text); }}
QFrame#GroupRule {{ border: none; background: palette(mid); max-height: 1px; }}
QLabel#FieldLabel {{ color: palette(text); }}
{extra}
"""


STYLESHEET = build_stylesheet(False)
