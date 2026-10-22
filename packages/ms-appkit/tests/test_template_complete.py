"""The template passes every house rule it ships, so what a new program is
copied from can never be behind the rules it is checked against."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import ms_appkit
from ms_appkit import housekeeping as house

KIT = Path(__file__).resolve().parents[1]
TEMPLATE = KIT / "template"


@pytest.fixture(scope="module")
def template_info():
    sys.path.insert(0, str(TEMPLATE))
    import example_app as pkg

    yield ms_appkit.configure(name=pkg.APP_NAME, repo=pkg.GITHUB_REPO, version=pkg.__version__,
                              slug=pkg.SLUG, visibility=pkg.VISIBILITY, private=pkg.PRIVATE)
    sys.path.remove(str(TEMPLATE))


def test_the_template_ships_every_file_a_program_needs():
    for relative in ("pyproject.toml", "ms-app.json", "README.md", "CHANGELOG.md", ".gitignore",
                     ".github/workflows/ci.yml", ".github/workflows/release.yml",
                     ".github/workflows/release-private.yml", "packaging/example_app.spec",
                     "packaging/windows/example_app.iss", "packaging/release-notes.md",
                     "tools/release_notes.py", "tests/test_house_rules.py",
                     "docs/images/home.png", "example_app/__init__.py", "example_app/_version.py",
                     "example_app/app.py", "example_app/ui/main_window.py"):
        assert (TEMPLATE / relative).is_file(), f"template lacks {relative}"


def test_the_marked_template_files_carry_the_current_marker():
    for relative in house.TEMPLATE_MARKED:
        text = (TEMPLATE / relative).read_text(encoding="utf-8")
        found = house.TEMPLATE_MARKER.search(text)
        assert found and int(found.group(1)) == house.TEMPLATE_VERSION, relative


def test_the_template_passes_the_family_s_checks(template_info):
    info = template_info
    package = TEMPLATE / "example_app"
    assert not house.changelog_faults(TEMPLATE, info.version)
    assert not house.ci_workflow_faults(TEMPLATE)
    assert not house.release_workflow_faults(TEMPLATE, info.slug)
    assert not house.manifest_faults(TEMPLATE, info)
    assert not house.installer_script_faults(TEMPLATE, info.slug)
    assert not house.bare_urlopen_faults(package)
    assert not house.update_path_faults(package)
    assert not house.readme_faults(TEMPLATE)
    assert not house.template_drift_faults(TEMPLATE)
    assert not house.dependency_faults(TEMPLATE)
    assert not house.family_support_email_faults(info)


def test_the_template_s_manifest_names_the_kit_s_own_version(template_info):
    import json

    from ms_appkit import __version__

    data = json.loads((TEMPLATE / "ms-app.json").read_text(encoding="utf-8"))
    assert data["kit"]["version"] == __version__, "bump template/ms-app.json and pyproject with the kit"
    assert f"@ms-appkit/v{__version__}#" in (TEMPLATE / "pyproject.toml").read_text(encoding="utf-8")
