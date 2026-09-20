"""The house rules, as checks a program's own test suite can run.

Every rule here replaces something a person had to remember, and every one is
here because it was missed at least once in a shipped build. They are written
against the *shape* of the code rather than its behaviour, which is unusual for
tests -- but a rule nobody can forget is worth more than a rule written down
well.

They live in the kit rather than being copied into each application, so that a
lesson learned in one program is a gate in all of them at their next release.
Each function returns a list of complaints; an empty list is a pass, and each
complaint says what to do rather than only what is wrong.

    # tests/test_house_rules.py, in the application
    from pathlib import Path
    from ms_appkit import housekeeping as house

    UI = Path(__file__).resolve().parents[1] / "gateway_app" / "ui"

    def test_buttons_come_from_the_helper():
        assert not house.hand_built_buttons(UI)
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

BUTTON_HELPERS = ("button", "primary")


def sources(folder: Path) -> list[Path]:
    return sorted(p for p in Path(folder).rglob("*.py") if "__pycache__" not in p.parts)


# --- buttons ---------------------------------------------------------------


def hand_built_buttons(ui: Path, allow: Iterable[tuple[str, str]] = ()) -> list[str]:
    """Buttons built with QPushButton instead of ``widgets.button``.

    Secondary buttons rendered as bare words for weeks in the first of these
    programs. Two things caused it: a stylesheet that set some box properties
    and not others, and buttons built by hand in eight different files, so no
    single change could fix them all.

    One helper is also the only place a press can be recorded for the problem
    report without asking every screen to remember to do it.
    """
    allowed = set(allow)
    offenders = []
    for path in sources(ui):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if called != "QPushButton":
                continue
            label = ""
            if node.args and isinstance(node.args[0], ast.Constant):
                label = str(node.args[0].value).strip()
            if (path.name, label) in allowed:
                continue
            offenders.append(
                f"{path.name}:{node.lineno} builds QPushButton({label!r}) by hand; "
                "use ms_appkit.widgets.button()"
            )
    return offenders


def buttons_declared_in(ui: Path) -> list[tuple[str, str, str]]:
    """Every button the interface builds, as (file, label, mark)."""
    found = []
    for path in sources(ui):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if called not in BUTTON_HELPERS:
                continue
            args = [a.value if isinstance(a, ast.Constant) else None for a in node.args]
            label = args[0] if args else None
            if label is None:
                continue
            glyph = args[1] if len(args) > 1 and args[1] else ""
            found.append((path.name, str(label), str(glyph)))
    return found


def unknown_marks(ui: Path) -> list[str]:
    """Buttons asking for a mark the library does not hold.

    A name the set does not have renders nothing and only writes a log line, so
    the button looks deliberately plain. One shipped that way: ``speed``, for an
    icon vendored as ``gauge``.
    """
    from ms_appkit.icons import names

    available = set(names())
    if not available:
        return ["no icons are vendored with ms_appkit"]
    return [
        f"{where}: {label!r} asks for {glyph!r}, which the library does not "
        "hold. Pick an existing name, or vendor one from lucide.dev, record it "
        "in resources/icons/SOURCE.md, and add a row to the button register in "
        "the ms-desktop-app skill."
        for where, label, glyph in buttons_declared_in(ui)
        if not glyph or glyph not in available
    ]


def inconsistent_marks(ui: Path) -> dict[str, set[str]]:
    """Labels that appear with more than one mark.

    The same words must mean the same mark, or the vocabulary stops being a
    vocabulary and becomes a list of pictures.
    """
    seen: dict[str, set[str]] = {}
    for _, label, glyph in buttons_declared_in(ui):
        seen.setdefault(label, set()).add(glyph)
    return {label: marks for label, marks in seen.items() if len(marks) > 1}


# --- the stylesheet --------------------------------------------------------


def stylesheet_rules(text: str) -> dict[str, str]:
    """Selector -> declarations, for every rule in a Qt stylesheet."""
    without_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return {
        match.group(1).strip().splitlines()[-1].strip(): match.group(2)
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", without_comments)
    }


def partial_restyles(stylesheet: str) -> list[str]:
    """Rules that take a control's native look away without replacing it.

    Establishing a corner radius makes Qt hand the whole appearance of the
    control over to the stylesheet. A rule that then states neither a border
    nor a background leaves a control with no edge and no fill -- which is how
    every secondary button in one program came to render as bare text.
    """
    complaints = []
    for selector, body in stylesheet_rules(stylesheet).items():
        if "QPushButton" not in selector:
            continue
        if ":" in selector.split("QPushButton")[-1]:
            continue                     # states inherit the base rule
        if "border-radius" not in body:
            continue                     # only nudging padding; box inherited
        if "border:" not in body and "border-color" not in body:
            complaints.append(
                f"{selector} sets a box property but no border, so Qt drops the "
                "native border and the control stops looking clickable"
            )
        if "background" not in body:
            complaints.append(
                f"{selector} sets a box property but no background, so Qt drops "
                "the native fill"
            )
    return complaints


def roles_missing_states(stylesheet: str,
                         roles: Iterable[str] = ("QPushButton", "QPushButton#Primary"),
                         states: Iterable[str] = (":hover", ":pressed", ":disabled"),
                         ) -> list[str]:
    """A role styled only at rest has no pressed or disabled appearance."""
    rules = stylesheet_rules(stylesheet)
    return [
        f"{role} has no {state} appearance"
        for role in roles
        for state in states
        # Exactly this role in this state. "QPushButton" must not be
        # satisfied by "QPushButton#Primary:pressed", which is how the base
        # role went a release with no pressed appearance at all.
        if f"{role}{state}" not in rules
    ]


# --- the icon library ------------------------------------------------------


def library_faults() -> list[str]:
    """That the vendored set is the real thing and can still be tinted."""
    from ms_appkit.icons import ICON_DIR, LIBRARY

    faults = []
    if LIBRARY != "Lucide":
        faults.append(f"the library is named {LIBRARY!r}; it should be Lucide")
    if not (ICON_DIR / "LICENSE").is_file():
        faults.append("the library's licence must ship beside its icons")
    source = ICON_DIR / "SOURCE.md"
    if not source.is_file() or "lucide.dev" not in source.read_text(encoding="utf-8"):
        faults.append("SOURCE.md must record where each mark came from")
    sample = ICON_DIR / "back.svg"
    if not sample.is_file():
        faults.append("back.svg is missing from the set")
        return faults
    text = sample.read_text(encoding="utf-8")
    if "lucide-static" not in text:
        faults.append("icons must be the upstream files, not redrawn by hand")
    if "currentColor" not in text:
        faults.append("an icon that cannot be tinted is invisible on a dark machine")
    return faults


def illegible_icons(floor: float = 0.55) -> list[str]:
    """Marks too small in their box to read beside a label.

    A glyph using a small share of its box looks like a speck, which is
    indistinguishable from a missing icon. Two hand-drawn ones shipped that way
    before the set was replaced with a maintained library.
    """
    from PySide6.QtWidgets import QApplication

    from ms_appkit.icons import SIZE, icon, names

    QApplication.instance() or QApplication([])
    if not names():
        return ["the icon set is empty"]

    complaints = []
    for name in names():
        image = icon(name, "#000000", SIZE).pixmap(SIZE, SIZE).toImage()
        inked = [
            (x, y)
            for x in range(SIZE)
            for y in range(SIZE)
            if image.pixelColor(x, y).alpha() > 40
        ]
        if not inked:
            complaints.append(f"the {name!r} icon drew nothing")
            continue
        width = max(x for x, _ in inked) - min(x for x, _ in inked) + 1
        height = max(y for _, y in inked) - min(y for _, y in inked) + 1
        if max(width, height) < SIZE * floor:
            complaints.append(f"{name} is {width}x{height} of {SIZE}px and reads as a speck")
    return complaints


def untintable_icons() -> list[str]:
    """Every mark must render in both a light and a dark ink."""
    from PySide6.QtWidgets import QApplication

    from ms_appkit.icons import icon, names

    QApplication.instance() or QApplication([])
    return [
        f"{name} is null in {colour}"
        for name in names()
        for colour in ("#1a1a1a", "#e6e9ee")
        if icon(name, colour).isNull()
    ]


# --- navigation ------------------------------------------------------------


def navigation_faults() -> list[str]:
    """Back on the left, the action that moves forward on the right.

    It was the other way round in the first of these programs, which is not
    what any other application on the machine does. Checked on the helper,
    because the helper is the only place it is decided.
    """
    from PySide6.QtWidgets import QApplication

    from ms_appkit.widgets import action_bar, button

    QApplication.instance() or QApplication([])
    back = button("Back", "back")
    forward = button("Continue", "forward")
    extra = button("Something else", "edit")
    row = action_bar(back=back, forward=forward, extras=[extra])
    # Spacers count. They are what holds the two sides apart, and a check that
    # ignored them passed happily on a row built back-to-front.
    order = [row.itemAt(i).widget() for i in range(row.count())]
    gaps = [i for i, item in enumerate(order) if item is None]

    faults = []
    if not gaps:
        return ["the action row has no gap, so both sides sit together"]
    gap = gaps[0]
    if order.index(back) > gap:
        faults.append("Back belongs on the left of the gap")
    if order.index(forward) < gap:
        faults.append("the action that moves forward belongs on the right of the gap")
    if order[-1] is not forward:
        faults.append("the forward action is the rightmost control")
    if order.index(extra) > order.index(forward):
        faults.append("a secondary action belongs left of the forward action")
    return faults


def misplaced_back_buttons(ui: Path) -> list[str]:
    """Screens that hand the wrong button to the wrong side of the row.

    :func:`navigation_faults` proves the helper puts its arguments in the right
    places. It cannot prove a screen passed the right arguments, and passing
    them the wrong way round is the whole of the complaint that started this:
    the row was built correctly and filled backwards.

    The rule is narrow on purpose -- a button whose words are "Back" belongs in
    the ``back`` slot and nowhere else. What sits opposite it is the screen's
    business.
    """
    complaints = []
    for path in sources(ui):
        tree = ast.parse(path.read_text(encoding="utf-8"))

        # name -> the words on the button it was assigned, within this module
        labels: dict[str, str] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            called = getattr(node.value.func, "id", None) or getattr(
                node.value.func, "attr", None
            )
            if called not in BUTTON_HELPERS:
                continue
            if not node.value.args or not isinstance(node.value.args[0], ast.Constant):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    labels[target.id] = str(node.value.args[0].value)

        def words(node) -> str:
            if isinstance(node, ast.Name):
                return labels.get(node.id, "")
            if isinstance(node, ast.Call) and node.args and isinstance(
                node.args[0], ast.Constant
            ):
                called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if called in BUTTON_HELPERS:
                    return str(node.args[0].value)
            return ""

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if called != "action_bar":
                continue
            for keyword in node.keywords:
                if keyword.arg == "back":
                    continue
                said = []
                if keyword.arg == "extras" and isinstance(
                    keyword.value, (ast.List, ast.Tuple)
                ):
                    said = [words(item) for item in keyword.value.elts]
                elif keyword.arg == "forward":
                    said = [words(keyword.value)]
                if any(text.strip().lower() == "back" for text in said):
                    complaints.append(
                        f"{path.name}:{node.lineno} passes 'Back' as "
                        f"{keyword.arg}=, which puts it on the right. Back goes "
                        "in the back slot, on the left."
                    )
    return complaints


# --- the footer ------------------------------------------------------------


def footer_faults(window) -> list[str]:
    """The three things every Machine Saver program shows on every screen.

    Pass a built main window. The version line is checked for the version the
    program actually reports, because a footer showing a hard-coded number is
    worse than no footer at all.
    """
    from PySide6.QtWidgets import QLabel

    from ms_appkit.identity import app

    footer = getattr(window, "footer", None)
    if footer is None:
        return ["the window has no ms_appkit footer"]

    faults = []
    if footer.report_button.text() != "Report a problem":
        faults.append("the report button must say 'Report a problem'")
    if footer.report_button.icon().isNull():
        faults.append("the report button has lost its mark")
    if app().version not in footer.version_label.text():
        faults.append(
            f"the footer says {footer.version_label.text()!r}, which does not "
            f"carry version {app().version}"
        )
    if footer.check_now.text() != "Check for updates":
        faults.append("the update button must say 'Check for updates'")

    said = [w.text() for w in window.findChildren(QLabel) if w.text()]
    if not any(t == f"Created by {app().organisation}" for t in said):
        faults.append("the footer must say who made it")
    marks = [w for w in footer.findChildren(QLabel) if not w.pixmap().isNull()]
    if not marks:
        faults.append("the Machine Saver mark is missing from the footer")
    return faults
