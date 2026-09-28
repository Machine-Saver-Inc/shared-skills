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
    import ssl

    import certifi

    from ms_appkit.update.net import trust

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
    import tempfile
    from pathlib import Path

    from ms_appkit.update.checker import verify_against_checksums

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



# --- where releases come from -----------------------------------------------
#
# A private program will be released somewhere other than GitHub. These hold
# the seam that makes that possible: the update code asks the channel, and a
# public program's channel behaves exactly as the code it replaced.


class _Answer:
    """Enough of an HTTP response for the checker and the downloader."""

    def __init__(self, body: bytes):
        self._body = body
        self.headers = {"Content-Length": str(len(body))}

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk, self._body = self._body, b""
        else:
            chunk, self._body = self._body[:size], self._body[size:]
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _a_channel(**changes):
    from ms_appkit.update.channel import GitHubReleases

    class Elsewhere(GitHubReleases):
        """A host that is not GitHub and wants its own header on every request."""

        def feed_headers(self):
            return {**super().feed_headers(), "X-Channel": "feed"}

        def download_headers(self):
            return {**super().download_headers(), "X-Channel": "download"}

    return Elsewhere(repo="Machine-Saver-Inc/kit-under-test",
                     host="the Machine Saver release store",
                     domain="releases.example.invalid", refused_hint="", **changes)


def test_a_public_program_is_released_through_github_exactly_as_before():
    from ms_appkit.update import channel
    from ms_appkit.update.channel import GitHubReleases

    source = channel.current()
    assert isinstance(source, GitHubReleases)
    assert source.latest_url == app().latest_release_api
    assert source.releases_page == app().releases_page
    headers = source.feed_headers()
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["User-Agent"] == app().user_agent


def test_the_feed_is_read_by_the_channel_not_by_the_checker():
    import json

    from ms_appkit.update.checker import fetch_latest_release_detailed

    seen = []
    feed = {"tag_name": "v9.1.0", "body": "Faster.", "html_url": "https://x.invalid/r",
            "assets": [{"name": "SHA256SUMS", "browser_download_url": "https://x.invalid/s"}]}

    def opener(request, timeout):
        seen.append(request)
        return _Answer(json.dumps(feed).encode())

    release, error = fetch_latest_release_detailed(opener=opener, channel=_a_channel())
    assert error is None
    assert release.version == "9.1.0" and release.checksums_url == "https://x.invalid/s"
    assert seen[0].get_header("X-channel") == "feed"


def test_every_download_carries_the_channel_s_headers(tmp_path, monkeypatch):
    """A private host will put its token here; a request that skips the
    channel would arrive without one and be refused."""
    from ms_appkit.update import checker
    from ms_appkit.update.checker import Release
    from ms_appkit.update.installer import download_asset, fetch_checksums

    monkeypatch.setattr(checker, "asset_pattern_for_this_platform", lambda: (".bin",))
    release = Release("9.1.0", "v9.1.0", "", "", {"app.bin": "https://x.invalid/a"},
                      "https://x.invalid/s")
    seen = []

    def opener(request, timeout):
        seen.append(request)
        return _Answer(b"payload")

    source = _a_channel()
    download_asset(release, destination=tmp_path, opener=opener, channel=source)
    fetch_checksums(release, opener=opener, channel=source)
    assert [r.get_header("X-channel") for r in seen] == ["download", "download"]


def test_an_error_names_the_host_it_was_talking_to():
    from ms_appkit.update.checker import describe_failure

    source = _a_channel()
    lookup = describe_failure(Exception("getaddrinfo failed"), source)
    assert "releases.example.invalid" in lookup and "github" not in lookup.lower()
    slow = describe_failure(TimeoutError("timed out"), source)
    assert slow.startswith("the Machine Saver release store did not answer")
    refused = describe_failure(Exception("HTTP Error 403: Forbidden"), source)
    assert "hourly limit" not in refused, "a GitHub excuse on a host that is not GitHub"


def test_no_update_code_names_github_outside_the_channel():
    """Anything that names the host outside channel.py is a place the private
    channel would silently not reach. Comments and docstrings may say GitHub;
    strings the program uses may not."""
    import ast
    from pathlib import Path

    import ms_appkit

    root = Path(ms_appkit.__file__).parent
    files = [*sorted((root / "update").glob("*.py")), root / "footer.py", root / "shell.py"]
    offenders = []
    for path in files:
        if path.name == "channel.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef))
            and node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings and "github" in node.value.lower()):
                offenders.append(f"{path.name}:{node.lineno}: {node.value[:40]!r}")
    assert not offenders, offenders

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


# --- private programs (skill section 1a) -------------------------------------
#
# Google is never reached from these tests. FakeGoogle answers the four
# endpoints the kit uses the way Google does, and can be told to be offline,
# to refuse the sign-in, or to hand back an account from another domain.

import base64 as _b64  # noqa: E402
import io as _io  # noqa: E402
import json as _json  # noqa: E402
import urllib.error as _urlerror  # noqa: E402
import urllib.parse as _parse  # noqa: E402

DAY = 86_400
T0 = 1_790_000_000.0


def _private_config(**changes):
    from ms_appkit.identity import PrivateConfig

    values = dict(
        client_id="123-abc.apps.googleusercontent.com",
        client_secret="not-really-secret",
        project="example-project",
        bucket="example-releases",
        support_email="software-support@machinesaver.net",
    )
    values.update(changes)
    return PrivateConfig(**values)


def _id_token(email="leo@machinesaver.net", hd="machinesaver.net", aud=None,
              verified=True, exp=None):
    # Valid for an hour from whichever is later, the fixed test time or now, so
    # tests on either clock see a live token.
    exp = exp if exp is not None else max(T0, __import__("time").time()) + 3600
    def part(data):
        return _b64.urlsafe_b64encode(_json.dumps(data).encode()).rstrip(b"=").decode()

    claims = {"iss": "https://accounts.google.com", "aud": aud or _private_config().client_id,
              "email": email, "email_verified": verified, "exp": exp}
    if hd:
        claims["hd"] = hd
    return f"{part({'alg': 'RS256'})}.{part(claims)}.signature"


class FakeGoogle:
    """The token, revoke, Cloud Storage and Secret Manager endpoints."""

    def __init__(self, mode="ok", email="leo@machinesaver.net", hd="machinesaver.net"):
        self.mode, self.email, self.hd = mode, email, hd
        self.seen = []
        self.challenge = None
        self.objects = {}
        self.secrets = {}

    def _error(self, url, code, body):
        return _urlerror.HTTPError(url, code, "error", {}, _io.BytesIO(_json.dumps(body).encode()))

    def __call__(self, request, timeout):
        self.seen.append(request)
        url = request.full_url
        if self.mode == "offline":
            raise _urlerror.URLError("getaddrinfo failed")
        if url.startswith("https://oauth2.googleapis.com/token"):
            form = dict(_parse.parse_qsl(request.data.decode()))
            if self.mode == "revoked":
                raise self._error(url, 400, {"error": "invalid_grant"})
            if form["grant_type"] == "authorization_code":
                import hashlib

                digest = hashlib.sha256(form["code_verifier"].encode()).digest()
                made = _b64.urlsafe_b64encode(digest).rstrip(b"=").decode()
                assert made == self.challenge, "PKCE verifier does not match its challenge"
                assert form["code"] == "the-code"
            answer = {"access_token": "ya29.fresh-access-token-value", "expires_in": 3599,
                      "id_token": _id_token(self.email, self.hd)}
            if form["grant_type"] == "authorization_code":
                answer["refresh_token"] = "1//0refresh-token-value-for-tests"
            return _Answer(_json.dumps(answer).encode())
        if url.startswith("https://oauth2.googleapis.com/revoke"):
            return _Answer(b"{}")
        auth = request.get_header("Authorization") or ""
        if not auth.startswith("Bearer "):
            raise self._error(url, 401, {"error": "no token"})
        if url.startswith("https://storage.googleapis.com/"):
            path = _parse.unquote(url.split("/o/")[1].split("?")[0])
            if path not in self.objects:
                raise self._error(url, 404, {})
            return _Answer(self.objects[path])
        if url.startswith("https://secretmanager.googleapis.com/"):
            name = url.split("/secrets/")[1].split("/")[0]
            if name not in self.secrets:
                raise self._error(url, 403 if name == "forbidden" else 404, {})
            data = _b64.b64encode(self.secrets[name].encode()).decode()
            return _Answer(_json.dumps({"payload": {"data": data}}).encode())
        raise AssertionError(f"unexpected request to {url}")


def _session(google, saved=True, confirmed=T0, now=T0, **config):
    from ms_appkit.auth import Auth, MemoryStore

    store = MemoryStore()
    if saved:
        store.set(_json.dumps({"refresh_token": "1//0stored", "email": "leo@machinesaver.net",
                               "confirmed_at": confirmed}))
    clock = {"now": now}
    session = Auth(_private_config(**config), store=store, opener=google,
                   clock=lambda: clock["now"], browser=lambda url: True)
    return session, store, clock


@pytest.fixture
def private_program():
    """Configure a private program for one test, then put the public one back."""
    from ms_appkit import auth
    from ms_appkit.update import channel

    before = app()
    ms_appkit.configure(name="Private Tool", repo="Machine-Saver-Inc/private-tool",
                        version="1.0.0", slug="private-tool", visibility="private",
                        private=_private_config())
    yield
    auth.use(None)
    channel.use(None)
    ms_appkit.configure(name=before.name, repo=before.repo, version=before.version,
                        slug=before.slug)


def test_a_private_program_must_say_how_it_signs_in():
    with pytest.raises(ValueError):
        ms_appkit.configure(name="X", repo="r", version="1", visibility="private")
    with pytest.raises(ValueError):
        ms_appkit.configure(name="X", repo="r", version="1", private=_private_config())
    with pytest.raises(ValueError):
        ms_appkit.configure(name="X", repo="r", version="1", visibility="secret")
    assert app().name == "Kit Under Test", "a refused configure changes nothing"


def test_nobody_signed_in_means_the_window_is_not_built():
    session, _, _ = _session(FakeGoogle(), saved=False)
    status = session.status()
    assert status.kind == "signed_out" and not status.may_open


def test_a_confirmed_sign_in_opens_and_restarts_the_grace_period():
    session, store, clock = _session(FakeGoogle(), confirmed=T0 - 5 * DAY)
    status = session.status()
    assert status.kind == "signed_in" and status.may_open
    assert status.footer_text() == "Signed in as leo@machinesaver.net"
    assert _json.loads(store.get())["confirmed_at"] == T0


def test_offline_inside_the_grace_period_opens_and_counts_down():
    session, _, _ = _session(FakeGoogle("offline"), confirmed=T0 - 3 * DAY)
    status = session.status()
    assert status.kind == "offline" and status.may_open and status.days_left == 11
    assert "working offline, 11 days left" in status.footer_text()


def test_offline_past_the_grace_period_does_not_open():
    session, _, _ = _session(FakeGoogle("offline"), confirmed=T0 - 14 * DAY)
    status = session.status()
    assert status.kind == "expired" and not status.may_open
    assert "14 days" in status.message


def test_a_clock_set_back_does_not_buy_more_grace():
    session, _, _ = _session(FakeGoogle("offline"), confirmed=T0 + 2 * DAY)
    assert session.status().kind == "expired"


def test_a_revoked_account_is_locked_out_at_once_even_inside_the_grace_period():
    session, store, _ = _session(FakeGoogle("revoked"), confirmed=T0 - 1 * DAY)
    status = session.status()
    assert status.kind == "revoked" and not status.may_open
    assert store.get() is None, "the stored sign-in must be forgotten"


def test_an_account_from_another_domain_is_refused_and_forgotten():
    session, store, _ = _session(FakeGoogle(email="someone@gmail.com", hd=None))
    status = session.status()
    assert status.kind == "revoked" and "machinesaver.net" in status.message
    assert store.get() is None


def _browser_that_signs_in(google, state_override=None, error=None):
    """Plays the person's browser: checks what the kit asked Google for, then
    sends Google's answer back to the kit's loopback address."""
    import threading
    import urllib.request

    def browser(url):
        query = dict(_parse.parse_qsl(_parse.urlparse(url).query))
        assert query["code_challenge_method"] == "S256"
        assert query["hd"] == "machinesaver.net"
        assert query["access_type"] == "offline"
        assert query["redirect_uri"].startswith("http://127.0.0.1:")
        google.challenge = query["code_challenge"]
        back = {"state": state_override or query["state"]}
        back.update({"error": error} if error else {"code": "the-code"})
        target = query["redirect_uri"] + "/?" + _parse.urlencode(back)
        threading.Thread(target=lambda: urllib.request.urlopen(target, timeout=5).read(),
                         daemon=True).start()
        return True

    return browser


def test_signing_in_through_the_browser_keeps_the_sign_in_in_the_credential_store(
        tmp_path, monkeypatch):
    from pathlib import Path

    from ms_appkit import settings

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    google = FakeGoogle()
    session, store, _ = _session(google, saved=False)
    session.clock = __import__("time").time
    session.browser = _browser_that_signs_in(google)
    status = session.sign_in(timeout=10)
    assert status.kind == "signed_in" and status.email == "leo@machinesaver.net"
    assert _json.loads(store.get())["refresh_token"] == "1//0refresh-token-value-for-tests"
    settings.save(settings.load())
    assert "refresh" not in settings.settings_path().read_text(), \
        "a token must never reach settings.json"


def test_a_sign_in_that_did_not_come_from_this_program_is_refused():
    from ms_appkit.auth import SignInError

    google = FakeGoogle()
    session, store, _ = _session(google, saved=False)
    session.clock = __import__("time").time
    session.browser = _browser_that_signs_in(google, state_override="forged")
    with pytest.raises(SignInError, match="did not come from this program"):
        session.sign_in(timeout=10)
    assert store.get() is None


def test_cancelling_at_google_says_so():
    from ms_appkit.auth import SignInError

    google = FakeGoogle()
    session, _, _ = _session(google, saved=False)
    session.clock = __import__("time").time
    session.browser = _browser_that_signs_in(google, error="access_denied")
    with pytest.raises(SignInError, match="cancelled"):
        session.sign_in(timeout=10)


def test_signing_in_with_a_personal_account_stores_nothing():
    from ms_appkit.auth import WrongAccount

    google = FakeGoogle(email="leo@gmail.com", hd=None)
    session, store, _ = _session(google, saved=False)
    session.clock = __import__("time").time
    session.browser = _browser_that_signs_in(google)
    with pytest.raises(WrongAccount):
        session.sign_in(timeout=10)
    assert store.get() is None


def test_signing_out_forgets_here_and_tells_google():
    google = FakeGoogle()
    session, store, _ = _session(google)
    session.sign_out()
    assert store.get() is None
    assert any("revoke" in r.full_url for r in google.seen)


def test_a_private_program_is_updated_from_its_bucket_with_the_person_s_token(private_program):
    from ms_appkit import auth
    from ms_appkit.update import channel
    from ms_appkit.update.checker import fetch_latest_release_detailed, is_newer

    google = FakeGoogle()
    session, _, _ = _session(google)
    session.clock = __import__("time").time
    auth.use(session)
    source = channel.current()
    assert isinstance(source, channel.GoogleCloudStorage)
    assert "github" not in source.latest_url.lower()

    payload = b"installer bytes"
    import hashlib

    google.objects = {
        "private-tool/latest.json": channel.feed(
            "1.1.0", "Faster labels.", ["private-tool-1.1.0.AppImage", "SHA256SUMS"]).encode(),
        "private-tool/v1.1.0/private-tool-1.1.0.AppImage": payload,
        "private-tool/v1.1.0/SHA256SUMS":
            f"{hashlib.sha256(payload).hexdigest()}  private-tool-1.1.0.AppImage\n".encode(),
    }
    release, error = fetch_latest_release_detailed(opener=google)
    assert error is None and is_newer(release) and release.notes == "Faster labels."
    assert release.checksums_url.endswith("SHA256SUMS?alt=media")
    assert all(r.get_header("Authorization") == "Bearer ya29.fresh-access-token-value"
               for r in google.seen if "storage" in r.full_url)


def test_a_private_release_downloads_and_verifies(private_program, tmp_path, monkeypatch):
    import hashlib

    from ms_appkit import auth
    from ms_appkit.update import channel, checker
    from ms_appkit.update.installer import download_asset, verify_download

    monkeypatch.setattr(checker, "asset_pattern_for_this_platform", lambda: (".bin",))
    google = FakeGoogle()
    session, _, _ = _session(google)
    session.clock = __import__("time").time
    auth.use(session)
    payload = b"the new version"
    google.objects = {
        "private-tool/v2.0.0/tool.bin": payload,
        "private-tool/v2.0.0/SHA256SUMS":
            f"{hashlib.sha256(payload).hexdigest()}  tool.bin\n".encode(),
    }
    release = channel.current().release_from(
        _json.loads(channel.feed("2.0.0", "", ["tool.bin", "SHA256SUMS"])))
    path = download_asset(release, destination=tmp_path, opener=google)
    verify_download(path, release, opener=google)
    assert path.read_bytes() == payload


def test_not_being_signed_in_is_a_failed_check_not_a_crash(private_program, tmp_path):
    from ms_appkit import auth
    from ms_appkit.update.checker import Release, check_for_update_detailed
    from ms_appkit.update.installer import UpdateError, download_asset

    session, _, _ = _session(FakeGoogle(), saved=False)
    auth.use(session)
    outcome = check_for_update_detailed()
    assert not outcome.reached and "signed in" in outcome.error
    with pytest.raises(UpdateError):
        download_asset(Release("2", "v2", "", "", {"x.AppImage": "https://s/x",
                                                   "x.exe": "https://s/x"}, None),
                       destination=tmp_path)


def test_a_release_feed_without_checksums_is_refused():
    from ms_appkit.update import channel

    with pytest.raises(ValueError):
        channel.feed("1.0.0", "", ["tool.exe"])


def test_credentials_come_from_secret_manager_and_are_never_guessed(private_program):
    from ms_appkit import secrets

    google = FakeGoogle()
    google.secrets = {"wipom-password": "hunter2-but-longer"}
    secrets.forget()
    token = lambda: "ya29.test"  # noqa: E731
    assert secrets.get("wipom-password", opener=google, token=token) == "hunter2-but-longer"
    with pytest.raises(secrets.SecretUnavailable, match="not allowed"):
        secrets.get("forbidden", opener=google, token=token)
    with pytest.raises(secrets.SecretUnavailable, match="no secret called"):
        secrets.get("missing", opener=google, token=token)
    with pytest.raises(secrets.SecretUnavailable, match="offline"):
        secrets.get("other", opener=FakeGoogle("offline"), token=token)
    secrets.forget()


def test_a_public_program_holds_no_secrets():
    from ms_appkit import secrets

    with pytest.raises(RuntimeError):
        secrets.get("anything")


def test_a_report_never_carries_a_credential():
    from ms_appkit.diagnostics import redact

    for token in ("ya29.a0AfB_byC-abc.def", "1//0gAbCdEfGhIjKlMnOp", _id_token(),
                  "GOCSPX-abcdefghijk", "Authorization: Bearer abcdefghijklmnopqrstu"):
        cleaned = redact(f"request failed with {token} attached")
        assert "credential removed" in cleaned and token.split()[-1] not in cleaned, token


def test_a_private_report_is_an_email_to_support():
    from ms_appkit.diagnostics import Report, mail_url

    report = Report(context={"Printer": "Zebra"}, trail=["opened Home"], log_tail=[])
    report.summary = "Label printed off-centre"
    url, trimmed = mail_url(report, "software-support@machinesaver.net")
    assert url.startswith("mailto:software-support@machinesaver.net?subject=")
    assert "Label%20printed%20off-centre" in url and not trimmed
    long_one = "x" * 5000
    url, trimmed = mail_url(report, "s@machinesaver.net", edited=f"Title\n\n{long_one}")
    assert trimmed and long_one not in url, "a person's text is never cut from the middle"


def test_the_window_is_not_built_until_the_gate_says_so():
    from ms_appkit.bootstrap import open_window

    built = []
    assert open_window(lambda: built.append(1), gate=lambda: False) is None
    assert not built


def test_the_gate_opens_without_asking_when_the_sign_in_stands(qt):
    from ms_appkit.signin import gate

    asked = []

    class Dialog:
        def __init__(self, session, reason=""):
            asked.append(reason)
            self.status = None

        def exec(self):
            return 0

    session, _, _ = _session(FakeGoogle())
    assert gate(session, dialog=Dialog) and not asked
    session, _, _ = _session(FakeGoogle(), saved=False)
    assert not gate(session, dialog=Dialog) and asked, "signed out: ask, and stay shut"
    session, _, _ = _session(FakeGoogle("revoked"))
    asked.clear()
    assert not gate(session, dialog=Dialog) and "no longer valid" in asked[0]


def test_run_builds_no_window_for_a_private_program_nobody_has_signed_into(
        qt, tmp_path, monkeypatch):
    """The whole startup, not a helper: a private program with no sign-in and
    the sign-in declined must return without constructing its window."""
    from pathlib import Path

    from ms_appkit import auth, bootstrap, signin

    before = app()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(signin, "gate", lambda: False)
    built = []
    try:
        code = bootstrap.run(name="Private Tool", repo="Machine-Saver-Inc/private-tool",
                             version="1.0.0", slug="private-tool",
                             window=lambda: built.append(1), visibility="private",
                             private=_private_config(), argv=["private-tool"])
    finally:
        auth.use(None)
        ms_appkit.configure(name=before.name, repo=before.repo, version=before.version,
                            slug=before.slug)
    assert code == 1 and not built


def test_the_sign_in_screen_uses_the_family_s_buttons(qt):
    from ms_appkit.signin import SignInDialog

    session, _, _ = _session(FakeGoogle(), saved=False)
    dialog = SignInDialog(session)
    assert dialog.sign_in.text().strip() == "Sign in with Google"
    assert dialog.cancel.text().strip() == "Cancel"
    assert not dialog.sign_in.icon().isNull() and not dialog.cancel.icon().isNull()
    dialog.close()


def test_a_private_report_button_says_where_it_goes(qt, private_program):
    from ms_appkit.report_dialog import ReportDialog

    dialog = ReportDialog({})
    assert dialog.post.text().strip() == "Email it to support"
    assert "software-support@machinesaver.net" in dialog.note.text()
    dialog.close()


def test_the_footer_says_whose_sign_in_it_is(qt):
    from ms_appkit.footer import Footer

    footer = Footer()
    assert footer.account_label.isHidden(), "public programs show nothing"
    footer.set_account("Signed in as leo@machinesaver.net")
    assert not footer.account_label.isHidden()
    footer.close()


# --- the house rules for public and private ----------------------------------


def test_the_declared_visibility_must_match_the_repository():
    assert not house.visibility_faults("public", False)
    assert not house.visibility_faults("private", True)
    assert house.visibility_faults("private", False)
    assert house.visibility_faults("public", True)
    assert house.visibility_faults("public", None), "not knowing is not passing"


def _repo(tmp_path, files):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


def test_a_tracked_env_file_fails_the_build(tmp_path):
    repo = _repo(tmp_path, {"app/main.py": "print('hi')\n", "web/.env": "PRINTER_IP=1\n"})
    assert house.tracked_secret_faults(repo) == ["web/.env: a credential file is tracked"]


def test_a_credential_pasted_into_source_fails_the_build(tmp_path):
    repo = _repo(tmp_path, {"app/config.py": 'CLIENT_SECRET = "GOCSPX-abcdefghijklmnop"\n'})
    assert house.tracked_secret_faults(repo)
    repo2 = tmp_path / "second"
    repo2.mkdir()
    _repo(repo2, {"app/services.py": 'WIPOM_PASSWORD = "correct-horse-battery"\n'})
    assert house.tracked_secret_faults(repo2)


def test_an_ignored_env_file_is_not_a_fault(tmp_path):
    repo = _repo(tmp_path, {".gitignore": ".env\n", "main.py": "x = 1\n"})
    (repo / ".env").write_text("SECRET=abcdefgh\n")
    assert not house.tracked_secret_faults(repo)


def test_this_repository_tracks_no_credentials():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    assert not house.tracked_secret_faults(root)


def test_a_private_program_s_sign_in_settings_are_the_family_s():
    from ms_appkit.identity import AppInfo

    good = AppInfo(visibility="private", private=_private_config())
    assert not house.private_config_faults(good)
    assert house.private_config_faults(AppInfo(visibility="private",
                                               private=_private_config(grace_days=30)))
    assert house.private_config_faults(AppInfo(visibility="private",
                                               private=_private_config(client_id="abc")))
    assert house.private_config_faults(AppInfo(
        visibility="private", private=_private_config(support_email="me@gmail.com")))


def test_the_sign_in_is_kept_in_the_operating_system_s_credential_store(monkeypatch):
    import sys
    import types

    from ms_appkit.auth import KeyringStore

    vault = {}
    fake = types.SimpleNamespace(
        get_password=lambda service, user: vault.get((service, user)),
        set_password=lambda service, user, value: vault.__setitem__((service, user), value),
        delete_password=lambda service, user: vault.pop((service, user)),
    )
    monkeypatch.setitem(sys.modules, "keyring", fake)
    store = KeyringStore("ms-appkit:private-tool")
    store.set("{}")
    assert vault == {("ms-appkit:private-tool", "google-sign-in"): "{}"}
    assert store.get() == "{}"
    store.delete()
    store.delete()      # already gone is not an error
    assert store.get() is None
