"""The house rules, run against this application.

Copy this file into a new Machine Saver application unchanged except for the
two names at the top. The checks themselves live in :mod:`ms_appkit.housekeeping`
so that a lesson learned in one program becomes a gate in all of them at their
next release, rather than being copied once and then drifting.

Add a test here only for a rule that is specific to this application. A rule
that would hold for any Machine Saver tool belongs in the kit.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ms_appkit
from ms_appkit import housekeeping as house

# --- the two lines to change in a new application --------------------------
ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "example_app" / "ui"
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def identity():
    from example_app import APP_NAME, GITHUB_REPO, PRIVATE, SLUG, VISIBILITY, __version__

    return ms_appkit.configure(
        name=APP_NAME, repo=GITHUB_REPO, version=__version__, slug=SLUG,
        visibility=VISIBILITY, private=PRIVATE,
    )


@pytest.fixture(scope="session")
def qt():
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from ms_appkit.style import STYLESHEET

    application = QApplication.instance() or QApplication([])
    application.setStyleSheet(STYLESHEET)
    return application


def test_every_button_comes_from_the_shared_helper():
    assert not house.hand_built_buttons(UI)


def test_every_button_asks_for_a_mark_the_library_has(qt):
    assert not house.unknown_marks(UI)


def test_the_same_words_always_mean_the_same_mark():
    assert not house.inconsistent_marks(UI)


def test_back_is_on_the_left_and_the_forward_action_on_the_right(qt):
    assert not house.navigation_faults()


def test_no_screen_fills_the_action_row_backwards():
    """The helper puts its arguments in the right places; this checks the
    screens handed it the right arguments."""
    assert not house.misplaced_back_buttons(UI)


def test_the_footer_is_on_every_screen(qt):
    from example_app.ui.main_window import MainWindow

    window = MainWindow()
    assert not house.footer_faults(window)
    window.close()


def test_every_screen_has_a_name_a_report_can_use(qt):
    """A report that says "opened ?" costs a round trip to find out where."""
    from example_app.ui.main_window import MainWindow

    window = MainWindow()
    for index in range(window.stack.count()):
        window.show_screen(index)
        assert window.current_screen() != "?"
    window.close()


def test_this_version_has_a_changelog_entry():
    """No release goes out without a line saying what changed."""
    from example_app import __version__

    changelog = (ROOT / "CHANGELOG.md")
    if not changelog.is_file():          # the template ships without one
        pytest.skip("no CHANGELOG.md in the template")
    assert f"[{__version__}]" in changelog.read_text(encoding="utf-8")


# --- public or private (skill section 1a) -------------------------------------


def test_the_repository_is_what_the_program_says_it_is(identity):
    """Only the build knows the repository's real visibility. CI passes it as
    MS_REPO_PRIVATE: ${{ github.event.repository.private }}."""
    told = os.environ.get("MS_REPO_PRIVATE")
    if told is None and not os.environ.get("CI"):
        pytest.skip("only the build knows whether the repository is private")
    private = None if told is None else told.strip().lower() == "true"
    assert not house.visibility_faults(identity.visibility, private)


def test_no_credential_is_tracked_by_git():
    assert not house.tracked_secret_faults(ROOT)


def test_a_private_program_signs_in_the_family_s_way(identity):
    assert not house.private_config_faults(identity)
