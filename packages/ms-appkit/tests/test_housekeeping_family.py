"""The family checks (kit 1.5.0): each one proved red on a broken copy of the
template and green on the template itself.

The rule for this file is the rule for the kit: a check that cannot be made
to fail has not been shown to check anything.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

import ms_appkit
from ms_appkit import housekeeping as house
from ms_appkit.identity import FAMILY_SUPPORT_EMAIL, PrivateConfig

KIT = Path(__file__).resolve().parents[1]
TEMPLATE = KIT / "template"


@pytest.fixture
def app(tmp_path) -> Path:
    """A copy of the template an individual test may break."""
    root = tmp_path / "example-tool"
    shutil.copytree(TEMPLATE, root)
    return root


@pytest.fixture
def info():
    return ms_appkit.configure(name="Example Tool", repo="Machine-Saver-Inc/example-tool",
                               version="0.1.0", slug="example-tool", visibility="public",
                               private=None)


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# --- the changelog -------------------------------------------------------------


def test_the_changelog_check_wants_an_entry_with_a_readable_summary(app):
    assert not house.changelog_faults(app, "0.1.0")
    assert house.changelog_faults(app, "0.2.0") == ["CHANGELOG.md has no entry for [0.2.0]"]
    edit(app / "CHANGELOG.md", "The first version.", "- The first version.")
    assert any("bullet" in f for f in house.changelog_faults(app, "0.1.0"))
    (app / "CHANGELOG.md").write_text("# Changelog\n\n## [0.1.0]\n\nA PR merged after CI "
                                      "passed; see #12.\n\n### Added\n- x\n", encoding="utf-8")
    said = " ".join(house.changelog_faults(app, "0.1.0"))
    assert "'PR'" in said and "'CI'" in said and "pull request number" in said
    (app / "CHANGELOG.md").unlink()
    assert house.changelog_faults(app, "0.1.0")[0].startswith("CHANGELOG.md is missing")


def test_the_summary_is_what_the_release_page_leads_with():
    text = "# C\n\n## [1.2.0] - x\n\nPlain words.\n\n### Fixed\n- a\n\n## [1.1.0]\n\nOlder.\n"
    assert house.changelog_summary("1.2.0", text) == "Plain words."
    assert house.changelog_summary("1.1.0", text) == "Older."
    assert house.changelog_summary("9.9.9", text) is None


# --- the build -------------------------------------------------------------------


LEGACY_CI = """name: CI
on:
  push:
  pull_request:
  schedule:
    - cron: "17 6 1 * *"
jobs:
  test:
    defaults:
      run:
        shell: bash
    steps:
      - run: ruff check .
      - env:
          QT_QPA_PLATFORM: offscreen
          MS_REPO_PRIVATE: ${{ github.event.repository.private }}
        run: python -m pytest -q
      - run: grep -qE "[0-9]+ passed" result.txt
"""


def test_the_ci_check_wants_the_family_s_steps_and_a_schedule(app):
    ci = app / ".github" / "workflows" / "ci.yml"
    assert not house.ci_workflow_faults(app), "the template calls the reusable workflow at a tag"
    edit(ci, "  schedule:\n    - cron: \"17 6 1 * *\"\n", "")
    assert any("schedule" in f for f in house.ci_workflow_faults(app))
    edit(ci, "@ms-appkit/v1.5.0", "@main")
    assert any("bash" in f for f in house.ci_workflow_faults(app)), \
        "a call at a branch head is not the family's workflow; the own-steps rules apply"
    # A program with its own steps passes when it carries every lesson.
    ci.write_text(LEGACY_CI, encoding="utf-8")
    assert not house.ci_workflow_faults(app)
    edit(ci, "shell: bash", "shell: pwsh")
    assert any("bash" in f for f in house.ci_workflow_faults(app))
    ci.write_text(LEGACY_CI.replace("MS_REPO_PRIVATE", "X"), encoding="utf-8")
    assert any("MS_REPO_PRIVATE" in f for f in house.ci_workflow_faults(app))
    ci.unlink()
    assert house.ci_workflow_faults(app) == [".github/workflows/ci.yml is missing"]


def test_the_release_check_wants_main_the_tag_and_a_verified_upload(app):
    assert not house.release_workflow_faults(app, "example-tool")
    assert any("SLUG" in f for f in house.release_workflow_faults(app, "other-tool"))
    workflows = app / ".github" / "workflows"
    (workflows / "release-private.yml").unlink()
    release = workflows / "release.yml"
    edit(release, "git merge-base --is-ancestor", "echo skipped")
    assert any("merge-base" in f for f in house.release_workflow_faults(app))
    edit(release, "sha256sum -c SHA256SUMS", "echo trusting")
    assert any("verify" in f for f in house.release_workflow_faults(app))
    edit(release, "example_app/_version.py", "example_app/version.txt")
    assert any("_version.py" in f for f in house.release_workflow_faults(app))
    release.unlink()
    assert house.release_workflow_faults(app) == [".github/workflows/release.yml is missing"]


def test_the_private_release_workflow_passes_too(app):
    (app / ".github" / "workflows" / "release.yml").unlink()
    assert not house.release_workflow_faults(app, "example-tool")


def test_the_installer_check_wants_its_own_appid_per_user_and_close(app):
    assert not house.installer_script_faults(app, "example-tool"), "the template may hold its placeholder"
    assert any("GUID" in f for f in house.installer_script_faults(app, "a-real-tool"))
    iss = app / "packaging" / "windows" / "example_app.iss"
    edit(iss, "AppId={{REPLACE-WITH-A-NEW-GUID-FROM-uuidgen}}", "AppId={{11111111-2222-3333-4444-555555555555}")
    assert not house.installer_script_faults(app, "a-real-tool")
    edit(iss, "PrivilegesRequired=lowest", "PrivilegesRequired=admin")
    assert any("per user" in f for f in house.installer_script_faults(app, "a-real-tool"))
    edit(iss, "CloseApplications=yes", "CloseApplications=no")
    assert any("CloseApplications" in f for f in house.installer_script_faults(app, "a-real-tool"))


# --- the manifest and the pin ---------------------------------------------------


def test_the_manifest_check_wants_agreement_and_a_kit_tag(app, info):
    assert not house.manifest_faults(app, info)
    manifest = app / "ms-app.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["slug"] = "something-else"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert any("slug" in f for f in house.manifest_faults(app, info))
    data["slug"] = "example-tool"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    edit(app / "pyproject.toml", "@ms-appkit/v1.5.0#", "@main#")
    assert any("pin a kit tag" in f for f in house.manifest_faults(app, info))
    edit(app / "pyproject.toml", "@main#", "#")
    assert any("no ref" in f for f in house.manifest_faults(app, info))
    edit(app / "pyproject.toml", "shared-skills.git#", "shared-skills.git@ms-appkit/v1.6.0#")
    assert any("pins ms-appkit 1.6.0" in f for f in house.manifest_faults(app, info))
    manifest.unlink()
    assert house.manifest_faults(app, info)[0].startswith("ms-app.json is missing")


def test_the_kit_pin_is_read_from_the_dependency_line(app):
    assert house.kit_pin(app) == "ms-appkit/v1.5.0"
    edit(app / "pyproject.toml", "ms-appkit @ git", "ms-appkit[private] @ git")
    assert house.kit_pin(app) == "ms-appkit/v1.5.0", "the private extra is still the kit"
    (app / "pyproject.toml").write_text("[project]\ndependencies = []\n", encoding="utf-8")
    assert house.kit_pin(app) is None


def test_the_template_drift_check_reads_the_marker(app):
    assert not house.template_drift_faults(app)
    edit(app / "tests" / "test_house_rules.py", "# ms-appkit template v1", "# ms-appkit template v0")
    assert any("is template v0" in f for f in house.template_drift_faults(app))
    edit(app / ".github" / "workflows" / "ci.yml", "# ms-appkit template v1\n", "")
    assert any("no 'ms-appkit template vN' marker" in f for f in house.template_drift_faults(app))


# --- dependencies -------------------------------------------------------------------


def test_the_dependency_check_knows_the_family_s_list_and_wants_a_reason_otherwise(app):
    assert not house.dependency_faults(app)
    assert {"ms-appkit", "pyserial", "certifi"} <= house.allowed_dependencies()
    pyproject = app / "pyproject.toml"
    edit(pyproject, "#subdirectory=packages/ms-appkit\",\n", "#subdirectory=packages/ms-appkit\",\n    \"left-pad>=1\",\n")
    assert any("left-pad is not in the family's allowed" in f for f in house.dependency_faults(app))
    edit(pyproject, "extra-dependencies = { }", 'extra-dependencies = { left-pad = "" }')
    assert any("without a reason" in f for f in house.dependency_faults(app))
    edit(pyproject, 'left-pad = ""', 'left-pad = "pads the left side of the bench label"')
    assert not house.dependency_faults(app)


# --- the network and the update path ------------------------------------------------


def test_the_urlopen_check_wants_a_certificate_context(app):
    package = app / "example_app"
    assert not house.bare_urlopen_faults(package)
    (package / "fetch.py").write_text(
        "import urllib.request\n\ndef go(u):\n    return urllib.request.urlopen(u)\n", encoding="utf-8")
    assert house.bare_urlopen_faults(package) == ["fetch.py:4 calls urlopen without context=; use "
                                                   "ms_appkit.update.net.open_url"]
    (package / "fetch.py").write_text(
        "import urllib.request\n\ndef go(u, ctx):\n    return urllib.request.urlopen(u, context=ctx)\n",
        encoding="utf-8")
    assert not house.bare_urlopen_faults(package)


def test_the_update_path_check_refuses_a_copy_of_the_installer(app):
    package = app / "example_app"
    assert not house.update_path_faults(package)
    (package / "updater.py").write_text(
        "from ms_appkit.update.installer import apply_update as _a\n\n"
        "def apply_update(p):\n    return _a(p)\n", encoding="utf-8")
    said = house.update_path_faults(package)
    assert any("defines apply_update()" in f for f in said)
    assert any("imports the kit's installer" in f for f in said)
    (package / "updater.py").unlink()
    main_window = package / "ui" / "main_window.py"
    edit(main_window, "start_update_check(", "start_nothing(")
    assert any("start_update_check" in f for f in house.update_path_faults(package))


# --- the README and the support address ------------------------------------------------


def test_the_readme_check_wants_the_scope_block_and_a_picture(app):
    assert not house.readme_faults(app)
    readme = app / "README.md"
    edit(readme, "![Home](docs/images/home.png)", "(no picture yet)")
    assert any("screenshot" in f for f in house.readme_faults(app))
    edit(readme, "<!-- machine-saver-scope:start -->", "")
    assert any("markers" in f for f in house.readme_faults(app))
    readme.unlink()
    assert house.readme_faults(app) == ["README.md is missing"]


def test_a_private_program_s_support_address_is_the_family_s():
    def private(email):
        return ms_appkit.configure(
            name="X", repo="Machine-Saver-Inc/x", version="0.1.0", slug="x", visibility="private",
            private=PrivateConfig(client_id="1-a.apps.googleusercontent.com", client_secret="",
                                  project="ms-desktop-apps", bucket="b", support_email=email))

    assert not house.family_support_email_faults(private(FAMILY_SUPPORT_EMAIL))
    said = house.family_support_email_faults(private("support@machinesaver.net"))
    assert said and FAMILY_SUPPORT_EMAIL in said[0]
    public = ms_appkit.configure(name="X", repo="Machine-Saver-Inc/x", version="0.1.0",
                                 slug="x", visibility="public", private=None)
    assert not house.family_support_email_faults(public)


def test_the_jargon_list_is_words_a_user_would_not_say():
    assert "CI" in house.CHANGELOG_JARGON and "refactor" in house.CHANGELOG_JARGON
    assert all(re.fullmatch(r"[\w.]+", w) for w in house.CHANGELOG_JARGON)
