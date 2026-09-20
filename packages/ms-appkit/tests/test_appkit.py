"""The kit's own tests. A new application does not copy these.

The application copies ``template/test_house_rules.py``, which runs the same
checks against its own source.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ms_appkit
from ms_appkit import housekeeping as house
from ms_appkit.identity import app


@pytest.fixture(scope="session", autouse=True)
def identity():
    return ms_appkit.configure(
        name="Kit Under Test",
        repo="Machine-Saver-Inc/kit-under-test",
        version="3.4.5",
        slug="kit-under-test",
    )


@pytest.fixture(scope="session")
def qt():
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from ms_appkit.style import STYLESHEET

    application = QApplication.instance() or QApplication([])
    application.setStyleSheet(STYLESHEET)
    return application


# --- identity --------------------------------------------------------------


def test_the_kit_knows_which_program_it_is_in():
    this = app()
    assert this.name == "Kit Under Test"
    assert this.releases_page.endswith("/Machine-Saver-Inc/kit-under-test/releases")
    assert this.new_issue_url.endswith("/issues/new")
    assert this.user_agent == "kit-under-test/3.4.5"
    assert this.log_path.name == "kit-under-test.log"


def test_an_unconfigured_program_says_so_instead_of_crashing(caplog):
    """A missing configure() must not stop a machine from working."""
    from ms_appkit import identity

    saved = identity._app
    try:
        identity._app = identity.AppInfo()
        with caplog.at_level("WARNING"):
            assert identity.app().repo == ""
        assert "configure" in caplog.text
    finally:
        identity._app = saved


# --- the shared look -------------------------------------------------------


@pytest.mark.parametrize("dark", [False, True])
def test_no_control_is_half_restyled(dark):
    from ms_appkit.style import build_stylesheet

    assert not house.partial_restyles(build_stylesheet(dark))


@pytest.mark.parametrize("dark", [False, True])
def test_every_button_role_describes_its_states(dark):
    from ms_appkit.style import build_stylesheet

    assert not house.roles_missing_states(build_stylesheet(dark))


def test_a_program_adds_its_own_rules_rather_than_forking_the_sheet():
    from ms_appkit.style import build_stylesheet

    sheet = build_stylesheet(False, extra="QLabel#Reading { font-size: 70px; }")
    assert "QLabel#Reading" in sheet
    assert "QPushButton#Primary" in sheet


# --- the library -----------------------------------------------------------


def test_the_icons_are_the_real_lucide_files():
    assert not house.library_faults()


def test_every_mark_is_legible_at_the_size_it_ships_at(qt):
    assert not house.illegible_icons()


def test_every_mark_survives_a_dark_machine(qt):
    assert not house.untintable_icons()


def test_a_missing_mark_is_survivable(qt, caplog):
    """A button with no icon is a blemish; a crash is a stopped line."""
    from ms_appkit.icons import icon

    with caplog.at_level("WARNING"):
        assert icon("no-such-mark").isNull()
    assert "no-such-mark" in caplog.text


# --- navigation and the footer ---------------------------------------------


def test_back_is_on_the_left(qt):
    assert not house.navigation_faults()


def test_the_footer_carries_the_version_the_maker_and_the_report_button(qt):
    from PySide6.QtWidgets import QLabel

    from ms_appkit.shell import AppWindow

    window = AppWindow()
    window.add_screen(QLabel("a screen"), "Home")
    assert not house.footer_faults(window)
    window.close()


def test_the_footer_says_what_a_check_established(qt):
    from ms_appkit.footer import Footer

    footer = Footer()
    footer.set_version_line(None)
    assert "not checked yet" in footer.version_label.text()
    footer.set_version_line("18 Sep 2026 14:02")
    assert "last checked 18 Sep 2026 14:02" in footer.version_label.text()
    # Failing to reach GitHub must never read as "you are up to date".
    footer.set_version_line("18 Sep 2026 14:02", failed=True)
    assert "could not reach GitHub" in footer.version_label.text()
    assert footer.version_label.objectName() == "StatusWarn"


# --- the shell -------------------------------------------------------------


def test_a_screen_is_named_before_it_becomes_current(qt):
    """Adding the first screen makes it current, which writes the trail. A
    name recorded after the add arrived too late and every report opened with
    "opened ?"."""
    from PySide6.QtWidgets import QLabel

    from ms_appkit.shell import AppWindow
    from ms_appkit.trail import TRAIL

    TRAIL.clear()
    window = AppWindow()
    window.add_screen(QLabel("one"), "Home")
    window.add_screen(QLabel("two"), "Settings")
    window.show_screen(1)
    assert TRAIL.lines()[0].endswith("opened Home")
    assert window.current_screen() == "Settings"
    window.close()


def test_a_program_says_when_it_is_a_bad_moment(qt):
    from PySide6.QtWidgets import QLabel

    from ms_appkit.shell import AppWindow

    class Busy(AppWindow):
        def busy(self):
            return "a label is printing"

    window = Busy()
    window.add_screen(QLabel("x"), "Home")
    assert window.busy() == "a label is printing"
    window.close()


# --- the report ------------------------------------------------------------


def test_a_report_carries_the_version_the_screen_and_the_trail():
    from ms_appkit.diagnostics import Report

    body = Report(
        kind="bug",
        summary="It stopped",
        description="mid-print",
        context={"Screen": "Home", "Printer": "ZT411"},
        trail=["10:00:00  pressed Print"],
    ).body()
    assert "3.4.5" in body
    assert "| Screen | Home |" in body
    assert "pressed Print" in body
    assert "| | |\n| --- | --- |" in body, "a blank line here stops GitHub rendering the table"


def test_a_report_does_not_carry_the_home_folder(tmp_path, monkeypatch):
    """Reports go to a public repository, and a Windows home path carries the
    account name."""
    from pathlib import Path

    from ms_appkit import diagnostics

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    said = diagnostics.redact(f"could not open {tmp_path}/settings.json")
    assert str(tmp_path) not in said
    assert "~" in said


def test_the_issue_url_points_at_this_programs_repository():
    from ms_appkit.diagnostics import Report, issue_url

    url, trimmed = issue_url(Report(summary="It stopped"))
    assert url.startswith("https://github.com/Machine-Saver-Inc/kit-under-test/issues/new")
    assert not trimmed


def test_a_long_report_is_trimmed_rather_than_truncated_by_the_browser():
    from ms_appkit.diagnostics import MAX_URL_CHARS, Report, issue_url

    url, trimmed = issue_url(
        Report(summary="It stopped", log_tail=["x" * 200] * 60)
    )
    assert trimmed, "the log should have been dropped to fit"
    assert len(url) <= MAX_URL_CHARS


# --- the trail -------------------------------------------------------------


def test_the_trail_collapses_a_button_pressed_five_times():
    from ms_appkit.trail import Trail

    trail = Trail()
    for _ in range(5):
        trail.pressed("Continue")
    assert len(trail) == 1
    assert trail.lines()[0].endswith("pressed Continue ×5")


def test_the_trail_forgets_the_oldest_rather_than_growing():
    from ms_appkit.trail import KEPT, Trail

    trail = Trail()
    for n in range(KEPT + 10):
        trail.happened(f"step {n}")
    assert len(trail) == KEPT


# --- updates ---------------------------------------------------------------


def test_a_newer_release_is_compared_numerically():
    from ms_appkit.update.checker import Release, is_newer

    def release(version):
        return Release(version, f"v{version}", "", "", {}, None)

    assert is_newer(release("3.10.0"), "3.9.0"), "1.10 must beat 1.9"
    assert not is_newer(release("3.4.5"), "3.4.5")
    assert not is_newer(release("3.4.4"))       # against the configured version


def test_not_reaching_github_is_not_the_same_as_being_up_to_date():
    from ms_appkit.update.checker import CheckOutcome, Release, outcome_kind

    reached = Release("9.0.0", "v9.0.0", "", "", {}, None)
    assert outcome_kind(CheckOutcome(release=reached, latest=reached)) == "update"
    assert outcome_kind(CheckOutcome(latest=None)) == "current"
    assert outcome_kind(CheckOutcome(error="no route to host")) == "unknown"


def test_a_build_with_no_repository_says_so():
    from ms_appkit import identity
    from ms_appkit.update.checker import fetch_latest_release_detailed

    saved = identity._app
    try:
        identity._app = identity.AppInfo(configured=True)
        release, error = fetch_latest_release_detailed()
        assert release is None and "repository" in error
    finally:
        identity._app = saved


def test_the_failure_is_explained_in_words_someone_can_act_on():
    from ms_appkit.update.checker import describe_failure

    assert "proxy" in describe_failure(Exception("certificate verify failed"))
    assert "internet" in describe_failure(Exception("getaddrinfo failed"))


def test_one_trust_store_carries_both_sets_of_roots():
    """A fallback that only ran after a failure cost every connection a doomed
    attempt first, and skipped entirely when the failure was not an SSLError."""
    import certifi

    from ms_appkit.update.net import trust

    import ssl

    context = trust()
    assert trust() is context, "the context is built once and reused"

    machine = ssl.create_default_context()
    bundled = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    bundled.load_verify_locations(cafile=certifi.where())

    def roots(ctx):
        return {c["serialNumber"] for c in ctx.get_ca_certs()}

    assert roots(machine) <= roots(context), (
        "a company proxy's CA lives in the machine store and must keep working"
    )
    assert roots(bundled) <= roots(context), (
        "a root this machine has never fetched must come from the bundle"
    )


def test_an_unsigned_download_is_refused():
    from ms_appkit.update.checker import verify_against_checksums

    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "setup.exe"
        path.write_bytes(b"not the real installer")
        assert not verify_against_checksums(path, "deadbeef  setup.exe")


# --- the lint -------------------------------------------------------------


def test_the_kit_passes_the_lint_the_build_runs():
    """So `pytest` alone is enough to know a push will not turn CI red."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert not house.lint_faults(root / "src", root / "tests", root / "template")


# --- what's new ------------------------------------------------------------


def test_the_whats_new_window_can_be_read(qt):
    """Issue #9: it scrolled off the screen with no scrollbar, showed Markdown
    as source, and was mostly install instructions."""
    assert not house.notes_window_faults()


def test_only_the_changes_are_shown_not_the_download():
    from ms_appkit.update.notes import what_changed

    said = what_changed(house.BODY_WITH_INSTALL)
    assert "Something changed" in said
    assert "Download" not in said and "Double-click" not in said
    assert not said.lstrip().startswith("#"), (
        "the window title already says which version this is"
    )


@pytest.mark.parametrize("rule", ["---", "***", "___", "- - -", "  ---  "])
def test_every_shape_of_horizontal_rule_separates_the_two_halves(rule):
    from ms_appkit.update.notes import what_changed

    body = f"It got faster.\n\n{rule}\n\n## Download\n\nGet the installer."
    assert what_changed(body) == "It got faster."


def test_a_release_written_by_hand_still_shows():
    """No horizontal rule means no install section to cut. Showing too much
    beats showing nothing."""
    from ms_appkit.update.notes import what_changed

    assert what_changed("Just a sentence about the fix.") == \
        "Just a sentence about the fix."
    assert what_changed("") == ""
    assert what_changed("   \n\n  ") == ""


def test_a_dash_inside_the_notes_is_not_mistaken_for_the_rule(qt):
    """A line of dashes under a Markdown table, or an em-dash in a sentence,
    must not truncate the notes."""
    from ms_appkit.update.notes import what_changed

    body = (
        "We changed the table \u2014 it now reads:\n\n"
        "| Setting | Value |\n| --- | --- |\n| Speed | Fast |\n\n"
        "And that is all.\n\n---\n\n## Download\n"
    )
    said = what_changed(body)
    assert "And that is all." in said
    assert "Download" not in said


def test_the_release_page_is_always_one_click_away(qt):
    """A machine the updater cannot serve still has somebody who can fetch the
    file by hand \u2014 and the leaving action keeps the left-hand place."""
    from PySide6.QtWidgets import QPushButton

    from ms_appkit.update.checker import Release
    from ms_appkit.update.ui import NotesWindow

    window = NotesWindow(
        Release("9.9.9", "v9.9.9", "It got faster.", "https://example.invalid/r",
                {}, None)
    )
    buttons = window.findChildren(QPushButton)
    said = [b.text() for b in buttons]
    assert said == ["Close", "Open the release page"], said
    assert all(not b.icon().isNull() for b in buttons), "both carry their mark"
    window.close()


# --- settings --------------------------------------------------------------


def test_unreadable_settings_do_not_stop_the_program(tmp_path, monkeypatch):
    from pathlib import Path

    from ms_appkit import settings

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    folder = tmp_path / f".{app().slug}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "settings.json").write_text("{ this is not json")
    data = settings.load({"port": None})
    assert data["check_for_updates"] is True
    assert data["port"] is None


def test_a_setting_added_in_a_later_release_appears_with_its_default(tmp_path, monkeypatch):
    from pathlib import Path

    from ms_appkit import settings

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    settings.save({"device": {"port": "COM4"}})
    data = settings.load({"device": {"port": None, "baud": 19200}})
    assert data["device"] == {"port": "COM4", "baud": 19200}
