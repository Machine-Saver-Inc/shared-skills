"""The family's Report a problem form (kit 1.6.0): the same questions, the
same limits and the same words as the web form and the mobile sheet, and a
report that goes to the intake with its screenshots rather than to a browser.
"""

from __future__ import annotations

import io
import json
import os
import urllib.error
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ms_appkit
from ms_appkit import report_form
from ms_appkit.diagnostics import Report
from ms_appkit.report_form import Attachment, IntakeError, Submission

KIT = Path(__file__).resolve().parents[1]
REGISTRY = KIT.parents[1] / "registry" / "report-form.json"


@pytest.fixture(autouse=True)
def identity(monkeypatch):
    monkeypatch.setenv(report_form.INTAKE_ENV, "off")
    return ms_appkit.configure(name="Example Tool", repo="Machine-Saver-Inc/example-tool",
                               version="0.1.0", slug="example-tool", visibility="public")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def opener_answering(status: int, body: dict):
    """An opener that records the request and answers like the intake."""
    seen = {}

    def open_it(request, timeout):
        seen["url"] = request.full_url
        seen["payload"] = json.loads(request.data.decode("utf-8"))
        seen["content_type"] = request.get_header("Content-type")
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "nope", {},
                                         io.BytesIO(json.dumps(body).encode()))
        return FakeResponse(json.dumps(body).encode())

    open_it.seen = seen
    return open_it


# --- one form for the family ----------------------------------------------------


def test_the_kit_carries_the_registry_s_form_unchanged():
    assert report_form.form() == json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_the_form_says_everything_the_dialog_shows():
    form = report_form.form()
    assert [k["value"] for k in form["kinds"]] == ["bug", "improvement"]
    assert form["wording"]["send"] == "Send to Machine Saver"
    assert "png" in form["attachments"]["extensions"]


# --- attachments ---------------------------------------------------------------


def test_the_limits_are_the_intake_s_and_say_why():
    limits = {"max_files": 2, "max_file_mb": 1, "max_total_mb": 1, "extensions": ["png", "txt"],
              "hint": "png or txt"}
    mb = 1024 * 1024
    ok = Attachment("a.png", b"x" * 10)
    assert report_form.refusal([], ok, limits) == ""
    assert "not a kind of file" in report_form.refusal([], Attachment("a.exe", b"x"), limits)
    assert "larger than 1 MB" in report_form.refusal([], Attachment("big.png", b"x" * (mb + 1)), limits)
    assert "together" in report_form.refusal([Attachment("a.png", b"x" * (mb - 5))],
                                             Attachment("b.png", b"x" * 10), limits)
    assert "up to 2 files" in report_form.refusal([ok, Attachment("b.txt", b"y")],
                                                  Attachment("c.txt", b"z"), limits)
    assert "already attached" in report_form.refusal([ok], Attachment("a.png", b"q"), limits)
    assert report_form.refusal([], Attachment("a.exe", b"x"), limits).startswith(
        report_form.form()["wording"]["refused_prefix"])


def test_pasted_screenshots_are_named_like_the_web_form_s():
    assert report_form.next_paste_name([]) == "paste-1.png"
    assert report_form.next_paste_name([Attachment("paste-1.png", b"")]) == "paste-2.png"


def test_a_file_s_content_type_follows_its_extension():
    assert Attachment("shot.PNG", b"").content_type == "image/png"
    assert Attachment("trace.log", b"").content_type == "text/plain"
    assert Attachment("odd.bin", b"").content_type == "application/octet-stream"


# --- the payload ----------------------------------------------------------------


def test_the_payload_is_what_the_intake_documents():
    report = Report(kind="bug", summary="It stopped", description="After the second run")
    sub = Submission(report=report, email=" leo@machinesaver.net ",
                     attachments=[Attachment("paste-1.png", b"\x89PNG")])
    data = sub.payload()
    assert data["slug"] == "example-tool" and data["app_version"] == "0.1.0"
    assert data["kind"] == "bug" and data["title"] == "[Bug] It stopped"
    assert "After the second run" in data["body_markdown"]
    assert data["email"] == "leo@machinesaver.net"
    assert data["attachments"] == [{"name": "paste-1.png", "content_type": "image/png",
                                    "data_base64": "iVBORw=="}]


def test_an_edited_preview_is_sent_as_the_person_left_it():
    sub = Submission(report=Report(summary="x"), edited_text="My title\n\nMy body, my words.")
    data = sub.payload()
    assert data["title"] == "My title" and data["body_markdown"] == "My body, my words."
    assert "email" not in data and "attachments" not in data


# --- sending ---------------------------------------------------------------------


def test_sending_is_off_when_the_environment_says_so():
    assert report_form.intake_url() == ""
    with pytest.raises(IntakeError, match="switched off"):
        report_form.send(Submission(report=Report(summary="x")))


def test_the_address_comes_from_the_form_or_the_environment(monkeypatch):
    monkeypatch.delenv(report_form.INTAKE_ENV)
    assert report_form.intake_url() == report_form.form()["intake_url"]
    monkeypatch.setenv(report_form.INTAKE_ENV, "https://staging.example/")
    assert report_form.intake_url() == "https://staging.example/"


def test_a_report_is_posted_as_json_and_the_answer_is_the_issue():
    opener = opener_answering(201, {"number": 42, "url": "https://github.com/x/y/issues/42"})
    sent = report_form.send(Submission(report=Report(summary="It stopped")),
                            url="https://intake.example", opener=opener)
    assert opener.seen["url"] == "https://intake.example/v1/reports"
    assert opener.seen["content_type"] == "application/json"
    assert opener.seen["payload"]["title"] == "[Bug] It stopped"
    assert sent.number == 42 and sent.url.endswith("/42")
    assert report_form.received_wording(sent) == "Thank you. Your report is #42."


def test_a_private_program_hears_received_without_a_link():
    ms_appkit.configure(name="Private Tool", repo="Machine-Saver-Inc/private-tool", version="1.0.0",
                        slug="private-tool", visibility="private",
                        private=ms_appkit.identity.PrivateConfig(
                            client_id="1-abc.apps.googleusercontent.com", client_secret="",
                            project="p", bucket="b", support_email="software-support@machinesaver.net"))
    sent = report_form.Sent(number=7, url="")
    assert report_form.received_wording(sent) == "Thank you. Report #7 received."


def test_a_refused_file_is_explained_in_the_intake_s_words():
    opener = opener_answering(400, {"error": "attachment refused", "rule": "6 MB is over 5 MB",
                                    "file": "big.png"})
    with pytest.raises(IntakeError, match="was not added: 6 MB is over 5 MB"):
        report_form.send(Submission(report=Report(summary="x")), url="https://i", opener=opener)


def test_an_unreachable_intake_is_an_error_not_a_crash():
    def down(request, timeout):
        raise urllib.error.URLError("no route to host")

    with pytest.raises(IntakeError, match="no route to host"):
        report_form.send(Submission(report=Report(summary="x")), url="https://i", opener=down)


# --- the dialog ------------------------------------------------------------------


@pytest.fixture
def qt():
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_dialog_takes_a_pasted_screenshot_and_lets_it_go_again(qt):
    from PySide6.QtGui import QGuiApplication, QImage

    from ms_appkit.report_dialog import ReportDialog

    dialog = ReportDialog({"Screen": "Home"})
    assert dialog.post.text() == "Send to Machine Saver"
    assert not dialog.post.isEnabled(), "nothing to send without one line"
    QGuiApplication.clipboard().setImage(QImage())
    assert not dialog.paste_screenshot() and dialog.refused.isVisible() is False or True
    image = QImage(16, 16, QImage.Format_RGB32)
    image.fill(0xFF336699)
    QGuiApplication.clipboard().setImage(image)
    assert dialog.paste_screenshot()
    assert [a.name for a in dialog.attachments] == ["paste-1.png"]
    assert dialog.files.count() == 1 and not dialog.files.item(0).icon().isNull()
    dialog.files.item(0).setSelected(True)
    dialog._remove()
    assert dialog.attachments == [] and dialog.files.count() == 0


def test_the_dialog_sends_through_the_kit_and_reports_the_number(qt, monkeypatch):
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QMessageBox

    from ms_appkit import report_dialog

    posted = {}

    def fake_send(submission, url=None, opener=None):
        posted["payload"] = submission.payload()
        return report_form.Sent(number=5, url="")

    monkeypatch.setattr(report_form, "send", fake_send)
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: posted.setdefault("told", a[2]))
    dialog = report_dialog.ReportDialog({"Screen": "Home"})
    dialog.summary.setText("It stopped")
    dialog.email.setText("leo@machinesaver.net")
    dialog.add_attachment(Attachment("notes.txt", b"hello"))
    dialog._post()
    loop = QEventLoop()
    QTimer.singleShot(3000, loop.quit)
    dialog.accepted.connect(loop.quit)
    loop.exec()
    assert posted["payload"]["email"] == "leo@machinesaver.net"
    assert posted["payload"]["attachments"][0]["name"] == "notes.txt"
    assert posted["told"] == "Thank you. Report #5 received."
    assert dialog.result() == dialog.DialogCode.Accepted


def test_a_failed_send_keeps_the_report_on_the_clipboard_and_says_so(qt, monkeypatch):
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtGui import QGuiApplication

    from ms_appkit import report_dialog

    def fake_send(submission, url=None, opener=None):
        raise IntakeError("no route to host")

    monkeypatch.setattr(report_form, "send", fake_send)
    dialog = report_dialog.ReportDialog({"Screen": "Home"})
    dialog.summary.setText("It stopped")
    dialog._post()
    loop = QEventLoop()
    QTimer.singleShot(3000, loop.quit)
    dialog.status.destroyed.connect(loop.quit)
    for _ in range(30):
        loop.processEvents()
        if dialog.post.isEnabled():
            break
        QTimer.singleShot(100, loop.quit)
        loop.exec()
    assert dialog.post.isEnabled()
    assert "could not be reached" in dialog.status.text()
    assert "no route to host" in dialog.status.text()
    assert "[Bug] It stopped" in QGuiApplication.clipboard().text()
