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

        # `labels` is rebuilt for each file, so it is bound here rather than
        # closed over: the closure happens to be called inside the same
        # iteration today, and would read the wrong file's labels the moment
        # it was not.
        def words(node, labels=labels) -> str:
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


# --- the lint the build runs -----------------------------------------------


def lint_faults(*paths: Path) -> list[str]:
    """Run the same lint the build runs, from the test suite.

    A lint that lives only in CI is a lint you find out about after pushing.
    This one ran `ruff` in the workflow and nowhere else, so an import left in
    the wrong order sailed through a green local `pytest`, went out with a tag
    on it, and turned all six CI jobs red a minute later.

    Returns a complaint per finding. If `ruff` is not installed the caller gets
    one complaint saying so, rather than a silent pass -- a check that quietly
    does nothing is the thing this module exists to prevent.
    """
    import shutil
    import subprocess

    if shutil.which("ruff") is None:
        return ["ruff is not installed, so the lint the build runs was skipped"]
    try:
        done = subprocess.run(
            ["ruff", "check", *[str(p) for p in paths]],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"could not run ruff: {exc}"]
    if done.returncode == 0:
        return []
    return [line for line in done.stdout.splitlines() if line.strip()][:40]


# --- what the program shows about a release --------------------------------


LONG_BODY = (
    "## What's new in 9.9.9\n\n"
    + "\n\n".join(
        f"**Change {n}** \u2014 a paragraph about something that changed, long "
        "enough to wrap onto a second line in a window this wide."
        for n in range(1, 41)
    )
)

BODY_WITH_INSTALL = (
    "## What's new in 9.9.9\n\n"
    "**Something changed** and this is what it means for you.\n\n"
    "---\n\n"
    "## Download\n\n"
    "1. Download `Thing-Setup-9.9.9.exe` from **Assets** below.\n"
    "2. Double-click it.\n"
)


def notes_window_faults() -> list[str]:
    """What the **What's new** window must do with a real release body.

    All four of these were true at once in a shipped build, and the report that
    found them could only describe the symptom: "no way to see information that
    goes off the screen".

    The window held the raw body in a ``QMessageBox``, which sizes itself to
    its text and does not scroll. On one release that was 2042 pixels tall on a
    1080-pixel screen, so the bottom half was unreachable -- including the
    button to close it. The text was Markdown shown as source. And more than
    half of it was install instructions, for a program the reader had already
    installed.
    """
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    from ms_appkit.update.checker import Release
    from ms_appkit.update.ui import NotesWindow

    QApplication.instance() or QApplication([])
    screen = QGuiApplication.primaryScreen()
    available = screen.availableGeometry().height() if screen else 800

    faults = []

    long_one = NotesWindow(Release("9.9.9", "v9.9.9", LONG_BODY, "", {}, None))
    long_one.show()
    if long_one.size().height() > available:
        faults.append(
            f"a long release makes a {long_one.size().height()}px window on a "
            f"{available}px screen; the buttons run off the bottom edge"
        )
    # Both halves matter. A bar with a range that is switched off still
    # reports that range, so asking only about the range passes happily on a
    # view nobody can scroll.
    from PySide6.QtCore import Qt

    if long_one.body.verticalScrollBar().maximum() <= 0:
        faults.append(
            "a release too long for the window does not scroll, so the rest of "
            "it cannot be read"
        )
    if long_one.body.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff:
        faults.append("the notes view has its scrollbar switched off")
    shown = long_one.body.toPlainText()
    if "**" in shown or shown.lstrip().startswith("#"):
        faults.append(
            "the notes are shown as Markdown source rather than rendered"
        )
    long_one.close()

    with_install = NotesWindow(
        Release("9.9.9", "v9.9.9", BODY_WITH_INSTALL, "", {}, None)
    )
    said = with_install.body.toPlainText()
    if "Double-click" in said or "Download" in said:
        faults.append(
            "the install instructions are shown to somebody already running "
            "the program; show only what changed"
        )
    if "Something changed" not in said:
        faults.append("the actual change is missing from the notes window")
    with_install.close()

    return faults


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


# --- public or private (skill section 1a) -------------------------------------


def visibility_faults(declared: str, repo_is_private: bool | None) -> list[str]:
    """The program says what its repository is.

    ``repo_is_private`` comes from the build: GitHub Actions knows it as
    ``github.event.repository.private``. A "private" program in a public
    repository has published its source; a "public" one in a private repository
    cannot be updated by anyone without a GitHub account.
    """
    if repo_is_private is None:
        return ["the build did not say whether the repository is private "
                "(set MS_REPO_PRIVATE from github.event.repository.private)"]
    actual = "private" if repo_is_private else "public"
    if declared != actual:
        return [f"the program says it is {declared} but its repository is {actual}"]
    return []


#: Files that are credentials by name, whatever is in them.
SECRET_FILES = re.compile(
    r"(^|/)(\.env(\..+)?|client_secret[^/]*\.json|_client_secret\.py|credentials\.json|"
    r"[^/]*service[-_]?account[^/]*\.json|[^/]*\.(pem|p12|pfx|key))$",
    re.IGNORECASE,
)
#: Text that is a credential by shape.
SECRET_SHAPES = re.compile(
    r"GOCSPX-[\w\-]{10,}"                       # Google OAuth client secret
    r"|ya29\.[\w.\-]{20,}"                      # Google access token
    r"|1//0[\w\-]{20,}"                         # Google refresh token
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|AKIA[0-9A-Z]{16}"                        # AWS access key
    r"|gh[pousr]_[A-Za-z0-9]{30,}"              # GitHub token
    # A literal value: quoted, or bare to the end of the line. Code that reads
    # a value from somewhere (``secret=config["secret"]``) is not a credential.
    r"|(?i:(password|passwd|api[_-]?key|secret)['\"]?\s*[=:]\s*"
    r"(['\"][^'\"\s]{6,}['\"]|[A-Za-z0-9+/_\-]{12,}\s*$))"
)
#: Where the rule would trip over itself.
SECRET_EXEMPT = ("housekeeping.py", "test_appkit.py", "test_house_rules.py")


def tracked_secret_faults(root: Path, allow: Iterable[str] = ()) -> list[str]:
    """Nothing tracked by git is a credential, by name or by shape.

    The reason section 1a exists: a program that needs a password fetches it
    after sign-in, and a public program needs none. Uses ``git ls-files`` so an
    ignored local ``.env`` is not a fault and a tracked one always is.
    """
    import subprocess

    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True,
        ).stdout.decode("utf-8").split("\0")
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"could not ask git which files are tracked: {exc}"]
    allowed = set(allow)
    faults = []
    for name in filter(None, listed):
        if name in allowed:
            continue
        if SECRET_FILES.search(name):
            faults.append(f"{name}: a credential file is tracked")
            continue
        if Path(name).name in SECRET_EXEMPT:
            continue
        path = root / name
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if SECRET_SHAPES.search(line):
                faults.append(f"{name}:{number}: looks like a credential")
                break
    return faults


def private_config_faults(info) -> list[str]:
    """A private program's sign-in settings are the family's, not improvised."""
    if not info.is_private:
        return [] if info.private is None else ["a public program carries a PrivateConfig"]
    config = info.private
    if config is None:
        return ["a private program has no PrivateConfig"]
    faults = []
    if not config.client_id.endswith(".apps.googleusercontent.com"):
        faults.append("client_id is not a Google OAuth client ID")
    if not config.bucket or not config.project:
        faults.append("the release bucket and the Cloud project must both be named")
    if not config.support_email.endswith("@" + config.domain):
        faults.append(f"support_email must be a {config.domain} address")
    if not 1 <= config.grace_days <= 14:
        faults.append("grace_days is a policy of at most 14 (section 1a); "
                      "change the skill before changing this")
    return faults


# --- the family (kit 1.5.0) ----------------------------------------------------
#
# Everything below was a sentence in the skill before it was a check. The
# first update through the release store (AirVibe Power Profiler, 2026-10-22)
# installed and never reopened: the rule existed in prose and nowhere else.
# Since then a rule exists only if a function here enforces it.

#: The version of the files an application copies from template/. An
#: application whose copies carry an older number is behind the kit; the
#: family sweep refreshes them (template_drift_faults).
TEMPLATE_VERSION = 3
TEMPLATE_MARKER = re.compile(r"ms-appkit template v(\d+)")
TEMPLATE_SLUG = "example-tool"           # the template is allowed its own placeholders
#: The files template/ ships with a marker line, relative to the app root.
TEMPLATE_MARKED = ("tests/test_house_rules.py", ".github/workflows/ci.yml")

#: Words that belong in a commit message, not in what a user reads about a release.
CHANGELOG_JARGON = ("CI", "PR", "pytest", "ruff", ".py", "workflow", "refactor",
                    "merge", "lint")


def _read(path: Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def changelog_summary(version: str, text: str) -> str | None:
    """The prose under ``## [version]`` before its first ``###`` section, or
    None when the version has no entry. The same shape tools/release_notes.py
    reads, so what the release page leads with is what is checked."""
    pattern = re.compile(rf"^## \[{re.escape(version)}\][^\n]*$(.*?)(?=^## \[|\Z)", re.M | re.S)
    found = pattern.search(text)
    if not found:
        return None
    body = found.group(1).strip()
    return re.split(r"^### ", body, maxsplit=1, flags=re.M)[0].strip()


def changelog_faults(root: Path, version: str) -> list[str]:
    """CHANGELOG.md has an entry for this version that a user can read.

    The release page and the What's new window lead with the prose under the
    version heading. An entry that is only bullets, or that talks about pull
    requests and lint, tells the person running the program nothing. A missing
    entry means a release with no words at all.
    """
    text = _read(Path(root) / "CHANGELOG.md")
    if text is None:
        return ["CHANGELOG.md is missing; every release needs a line saying what changed"]
    lead = changelog_summary(version, text)
    if lead is None:
        return [f"CHANGELOG.md has no entry for [{version}]"]
    faults = []
    if not lead:
        return [f"[{version}] has no plain-language summary before its first ### section"]
    if lead.lstrip().startswith(("-", "*")):
        faults.append(f"[{version}]'s summary is a bullet list; write a sentence or two first")
    for word in CHANGELOG_JARGON:
        if re.search(rf"(?<![\w./]){re.escape(word)}(?![\w])", lead):
            faults.append(f"[{version}]'s summary mentions {word!r}; say what changed for the user")
    if re.search(r"#\d+", lead):
        faults.append(f"[{version}]'s summary cites an issue or pull request number")
    return faults


def ci_workflow_faults(root: Path) -> list[str]:
    """The build runs the family's checks the family's way, and runs on a clock.

    Either the application calls the family's reusable workflow at a kit tag,
    or its own ci.yml carries each of the lessons section 6 was written from.
    A monthly scheduled run is required either way: a program nobody has
    touched for a year still has to be found broken by a kit, Python or
    runner change, rather than at its next release.
    """
    text = _read(Path(root) / ".github" / "workflows" / "ci.yml")
    if text is None:
        return [".github/workflows/ci.yml is missing"]
    faults = []
    if "schedule:" not in text:
        faults.append("ci.yml has no schedule: trigger; a monthly run finds an untouched "
                      "program broken by a kit or runner change before its next release")
    if re.search(r"uses:\s*Machine-Saver-Inc/shared-skills/\.github/workflows/desktop-ci\.yml@ms-appkit/v",
                 text):
        return faults
    wanted = {
        "shell: bash": "defaults.run.shell is not bash; the Windows runner defaults to "
                       "PowerShell and every step below is bash",
        "QT_QPA_PLATFORM": "QT_QPA_PLATFORM is not set, so interface tests cannot run on a runner",
        "MS_REPO_PRIVATE": "MS_REPO_PRIVATE is not passed from github.event.repository.private, "
                           "so the visibility rule cannot run (section 1a)",
        "passed": "there is no step proving the interface tests actually ran rather than "
                  "being skipped (grep for '[0-9]+ passed')",
        "ruff": "ruff is not run",
    }
    for needle, complaint in wanted.items():
        if needle not in text:
            faults.append(f"ci.yml: {complaint}")
    return faults


def release_workflow_faults(root: Path, slug: str = "") -> list[str]:
    """A release can only ship what main has, what the tag says, and what was
    verified after publishing (section 6 and 1a)."""
    folder = Path(root) / ".github" / "workflows"
    texts = [t for name in ("release.yml", "release-private.yml")
             if (t := _read(folder / name)) is not None]
    if not texts:
        return [".github/workflows/release.yml is missing"]
    text = "\n".join(texts)
    faults = []
    if "merge-base --is-ancestor" not in text:
        faults.append("release.yml does not refuse a tag that is not on main "
                      "(git merge-base --is-ancestor)")
    if "sha256sum" not in text:
        faults.append("release.yml publishes no SHA256SUMS")
    if "sha256sum -c" not in text and "anonymous" not in text.lower():
        faults.append("release.yml does not verify what it published (sha256sum -c of the "
                      "downloaded files, or the anonymous-download refusal for a private store)")
    if "_version.py" not in text:
        faults.append("release.yml does not stamp _version.py from the tag, so a build can "
                      "disagree with its tag")
    if "_client_secret.py" in text and "frozen_check" not in text:
        faults.append("release.yml stamps the sign-in key but never proves the frozen build "
                      "carries it (python -m ms_appkit.frozen_check after PyInstaller)")
    if slug:
        said = re.findall(r"^\s*SLUG:\s*([\w.-]+)", text, re.M)
        if said and any(s != slug for s in said):
            faults.append(f"release.yml says SLUG: {said[0]} but the program's SLUG is {slug}")
    return faults


REPORT_OWN_NAMES = ("ReportDialog", "issue_url", "mail_url", "report_problem")


def report_path_faults(package_dir: Path) -> list[str]:
    """Reports go the kit's way: the family's form, sent to the intake (section 5).

    A program that draws its own report dialog, builds a GitHub issue address
    or an email for a report, or overrides the window's report_problem has a
    form that will drift from the web's and the mobile apps', cannot carry a
    pasted screenshot, and will not change when the family's form does.
    """
    faults = []
    for path in sources(package_dir):
        text = path.read_text(encoding="utf-8")
        where = path.relative_to(package_dir)
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and (
                    node.name == "ReportDialog"
                    or any(getattr(b, "id", getattr(b, "attr", "")) == "ReportDialog" for b in node.bases)):
                faults.append(f"{where}:{node.lineno} defines its own report dialog; the kit's "
                              "ReportDialog is the family's form")
            if isinstance(node, ast.FunctionDef) and node.name in ("report_problem", "issue_url", "mail_url"):
                faults.append(f"{where}:{node.lineno} defines {node.name}(); the kit's window "
                              "opens the report dialog and the kit sends the report")
            if isinstance(node, ast.ImportFrom) and node.module == "ms_appkit.diagnostics":
                for alias in node.names:
                    if alias.name in ("issue_url", "mail_url"):
                        faults.append(f"{where}:{node.lineno} imports {alias.name}; a report is "
                                      "sent to the intake, not opened in a browser")
        if re.search(r"issues/new|mailto:", text):
            faults.append(f"{where}: builds a GitHub issue or mailto address; the kit's report "
                          "dialog sends to Machine Saver's intake instead")
    return faults


def spec_faults(root: Path, package: str, private: bool = False) -> list[str]:
    """The PyInstaller spec names what the program loads by name (section 3).

    PyInstaller follows ``import`` statements only. The stamped sign-in key
    and the certificate bundle are reached some other way, so a spec that
    does not list them builds a program that opens and then cannot sign in,
    which is what every Power Profiler release up to 0.2.5 was (report 5).
    """
    specs = sorted(Path(root).glob("packaging/*.spec"))
    if not specs:
        return ["packaging/*.spec is missing"]
    text = "\n".join(_read(s) or "" for s in specs)
    found = re.search(r"hiddenimports\s*=\s*\[(.*?)\]", text, re.S)
    if not found:
        return ["the spec has no hiddenimports list"]
    named = set(re.findall(r"[\"']([\w.]+)[\"']", found.group(1)))
    wanted = [package, "certifi"]
    if private:
        wanted.append(f"{package}._client_secret")
    return [f"hiddenimports does not name {name}, so the frozen build may not carry it"
            for name in wanted if name not in named]


KIT_PIN = re.compile(r"ms-appkit(\[[\w,]+\])?\s*@\s*git\+https://github\.com/Machine-Saver-Inc/"
                     r"shared-skills(?:\.git)?(?:@([^#\s\"']+))?#subdirectory=packages/ms-appkit")


def kit_pin(root: Path) -> str | None:
    """The ref the application pins ms-appkit to, '' when it follows a branch
    head with no ref at all, or None when the dependency line is missing."""
    text = _read(Path(root) / "pyproject.toml")
    if text is None:
        return None
    found = KIT_PIN.search(text)
    if not found:
        return None
    return found.group(2) or ""


def manifest_faults(root: Path, info) -> list[str]:
    """ms-app.json says what this program is and what it was built from, and
    agrees with the code and the kit pin.

    Nothing recorded which kit or skill an application came from, so "which
    programs are behind?" could only be answered from commit messages. The
    manifest is that record, the registry and the catalog read it, and the
    pin it names must be a kit tag: a program following a branch head cannot
    be rebuilt the same way twice.
    """
    import json

    path = Path(root) / "ms-app.json"
    text = _read(path)
    if text is None:
        return ["ms-app.json is missing at the repository root (template/ms-app.json)"]
    try:
        data = json.loads(text)
    except ValueError as exc:
        return [f"ms-app.json is not valid JSON: {exc}"]
    faults = []
    for key, expected in (("slug", info.slug), ("name", info.name), ("repo", info.repo),
                          ("visibility", info.visibility)):
        if data.get(key) != expected:
            faults.append(f"ms-app.json {key} is {data.get(key)!r}; the program says {expected!r}")
    if data.get("kind") != "desktop":
        faults.append("ms-app.json kind must be 'desktop' for an ms-appkit program")
    skill = data.get("skill") or {}
    if skill.get("name") != "ms-desktop-app" or not re.fullmatch(r"\d+\.\d+\.\d+", str(skill.get("version", ""))):
        faults.append("ms-app.json skill must name ms-desktop-app and a version like 2.5.0")
    kit = data.get("kit") or {}
    pinned = kit_pin(root)
    if pinned is None:
        faults.append("pyproject.toml has no ms-appkit dependency line")
    elif pinned in ("", "main") or not pinned.startswith("ms-appkit/v"):
        faults.append(f"pyproject.toml pins ms-appkit to {pinned or 'no ref'!r}; pin a kit tag "
                      "such as @ms-appkit/v1.5.0 (section 13)")
    else:
        version = pinned.split("/v", 1)[1]
        if kit.get("name") != "ms-appkit" or kit.get("version") != version:
            faults.append(f"ms-app.json kit is {kit!r}; pyproject.toml pins ms-appkit {version}")
    return faults


def bare_urlopen_faults(package_dir: Path) -> list[str]:
    """No urlopen without the kit's certificate context.

    The most expensive lesson in the family (section 4): Python's own trust
    store is not Windows', and a bare urlopen fails on exactly the machines
    that matter. The kit's ``update.net.open_url`` carries the right context;
    anything else in the program must pass ``context=`` or use it.
    """
    faults = []
    for path in sources(package_dir):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if called != "urlopen":
                continue
            if not any(k.arg == "context" for k in node.keywords):
                faults.append(f"{path.relative_to(package_dir)}:{node.lineno} calls urlopen "
                              "without context=; use ms_appkit.update.net.open_url")
    return faults


def readme_faults(root: Path) -> list[str]:
    """The README carries the family's scope block and shows the program."""
    text = _read(Path(root) / "README.md")
    if text is None:
        return ["README.md is missing"]
    faults = []
    if "machine-saver-scope:start" not in text or "machine-saver-scope:end" not in text:
        faults.append("README.md lacks the machine-saver-scope markers around Scope, Ownership "
                      "boundaries and Development tracking")
    if "**Owner:**" not in text:
        faults.append("README.md's scope block does not say **Owner:**")
    if not re.search(r"!\[[^\]]*\]\([^)]+\.png\)", text):
        faults.append("README.md shows no screenshot (section 12)")
    return faults


def family_support_email_faults(info) -> list[str]:
    """A private program's reports go to the one address the family reads."""
    from ms_appkit.identity import FAMILY_SUPPORT_EMAIL

    if not info.is_private or info.private is None:
        return []
    if info.private.support_email != FAMILY_SUPPORT_EMAIL:
        return [f"support_email is {info.private.support_email}; the family's is "
                f"{FAMILY_SUPPORT_EMAIL} (identity.FAMILY_SUPPORT_EMAIL)"]
    return []


UPDATE_OWN_NAMES = ("apply_update", "windows_update_command", "relaunch", "download_asset",
                    "verify_download")


def update_path_faults(package_dir: Path) -> list[str]:
    """The program updates itself the kit's way and no other.

    Three lessons live in the kit's installer (how the helper is launched, no
    dialog before closing, the mark of the web); a program with its own copy
    of any of it has none of them. The window asks the kit to check, and that
    is the whole of what an application does about updates.
    """
    faults = []
    saw_check = False
    for path in sources(package_dir):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in UPDATE_OWN_NAMES:
                faults.append(f"{path.relative_to(package_dir)}:{node.lineno} defines "
                              f"{node.name}(); the kit's update path is not to be copied")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", "") or ""
                names = [a.name for a in node.names]
                if module.startswith("ms_appkit.update.installer") or (
                    module == "ms_appkit.update" and "installer" in names):
                    faults.append(f"{path.relative_to(package_dir)}:{node.lineno} imports the "
                                  "kit's installer; only the kit's window runs it")
        if "start_update_check(" in text:
            saw_check = True
    if not saw_check:
        faults.append("no module calls start_update_check(); the window must ask the kit to "
                      "check for updates when it opens (section 4)")
    return faults


def template_drift_faults(root: Path) -> list[str]:
    """The files copied from template/ are the kit's current ones.

    They carry a marker line; a copy with an older number has missed the
    lessons added since, and the sweep refreshes it. A copy with no marker
    predates the rule and is refreshed the same way.
    """
    faults = []
    for relative in TEMPLATE_MARKED:
        text = _read(Path(root) / relative)
        if text is None:
            continue                        # its own check says it is missing
        found = TEMPLATE_MARKER.search(text)
        if not found:
            faults.append(f"{relative} carries no 'ms-appkit template vN' marker; copy the "
                          "current one from the kit's template/")
        elif int(found.group(1)) < TEMPLATE_VERSION:
            faults.append(f"{relative} is template v{found.group(1)}; the kit's is "
                          f"v{TEMPLATE_VERSION}. Copy the current one from template/")
    return faults


#: AppIds that must never ship: the template's placeholder and any GUID a
#: shipped program already uses. Two programs with one AppId install over
#: each other.
KNOWN_APP_IDS = {
    "{{REPLACE-WITH-A-NEW-GUID-FROM-uuidgen}}",
    "{{6D1F4C2A-9B7E-4F3A-8C5D-2E1A7B9F0C44}",     # AirVibe Power Profiler
}


def installer_script_faults(root: Path, slug: str = "") -> list[str]:
    """The Inno Setup script is this program's own, installs per user, and
    closes the program before replacing it."""
    folder = Path(root) / "packaging" / "windows"
    scripts = sorted(folder.glob("*.iss")) if folder.is_dir() else []
    if not scripts:
        return ["packaging/windows/*.iss is missing"]
    text = scripts[0].read_text(encoding="utf-8")
    faults = []
    found = re.search(r"^AppId=(\S+)", text, re.M)
    if not found:
        faults.append("the installer script has no AppId")
    elif found.group(1) in KNOWN_APP_IDS and slug not in ("airvibe-power-profiler",
                                                           TEMPLATE_SLUG):
        faults.append(f"AppId {found.group(1)} is the template's or another program's; "
                      "generate a new GUID for this program")
    if not re.search(r"^PrivilegesRequired=lowest", text, re.M):
        faults.append("the installer must install per user (PrivilegesRequired=lowest); "
                      "a work machine is locked down")
    if not re.search(r"^CloseApplications=yes", text, re.M):
        faults.append("the installer must close the running program (CloseApplications=yes) "
                      "or an update cannot replace its files")
    return faults


def _dependency_names(text: str) -> list[str]:
    """The package names in pyproject's dependencies list, lower-cased."""
    block = re.search(r"^dependencies\s*=\s*\[(.*?)^\]", text, re.M | re.S)
    if not block:
        return []
    names = []
    for item in re.findall(r"[\"']([^\"']+)[\"']", block.group(1)):
        name = re.split(r"[\[\s@<>=!~;]", item.strip(), maxsplit=1)[0]
        if name:
            names.append(name.lower().replace("_", "-"))
    return names


def allowed_dependencies() -> set[str]:
    path = Path(__file__).with_name("allowed_dependencies.txt")
    return {line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")}


def dependency_faults(root: Path) -> list[str]:
    """Every dependency is one the family has agreed to, or is justified.

    An unlisted package is declared under ``[tool.ms-appkit]`` as
    ``extra-dependencies = { name = "why" }``; the next kit release moves it
    to the family's list or says why not. The point is that a dependency is
    a decision somebody made on purpose, visible in one place.
    """
    text = _read(Path(root) / "pyproject.toml")
    if text is None:
        return ["pyproject.toml is missing"]
    allowed = allowed_dependencies()
    justified = {}
    table = re.search(r"^\[tool\.ms-appkit\](.*?)(?=^\[|\Z)", text, re.M | re.S)
    if table:
        inline = re.search(r"extra-dependencies\s*=\s*\{(.*?)\}", table.group(1), re.S)
        if inline:
            for name, why in re.findall(r"[\"']?([\w.-]+)[\"']?\s*=\s*[\"']([^\"']*)[\"']", inline.group(1)):
                justified[name.lower().replace("_", "-")] = why.strip()
    faults = []
    for name in _dependency_names(text):
        if name in allowed:
            continue
        if name in justified and justified[name]:
            continue
        if name in justified:
            faults.append(f"{name} is declared under [tool.ms-appkit] without a reason")
        else:
            faults.append(f"{name} is not in the family's allowed dependencies; justify it under "
                          "[tool.ms-appkit] extra-dependencies or propose it for the kit's list")
    return faults
