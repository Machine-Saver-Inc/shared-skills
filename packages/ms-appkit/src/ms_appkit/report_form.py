"""The family's Report a problem form: what it asks, and how a report is sent.

Qt-free, so the dialog's rules can be asserted in tests. The form itself is
``resources/report_form.json``, a copy of ``registry/report-form.json`` in
shared-skills: the same file draws the dialog in every desktop program, the
mobile kit's sheet and the form on apps.machinesaver.com, so a change to the
form is one change. ``tools/check_report_form.py`` keeps the copies identical.

A report goes to the report intake (``intake_url`` in the form) as JSON with
the attachments base64-encoded; the intake files the GitHub issue and stores
the files. Set ``MS_REPORT_INTAKE=off`` to keep tests and bench runs from
sending anything, or to another address to send there.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from ms_appkit.diagnostics import Report
from ms_appkit.identity import app

log = logging.getLogger(__name__)

INTAKE_ENV = "MS_REPORT_INTAKE"
TIMEOUT_S = 30.0
_CONTENT_TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif",
    "webp": "image/webp", "pdf": "application/pdf", "txt": "text/plain", "log": "text/plain",
    "json": "application/json", "csv": "text/csv", "zip": "application/zip",
}


def form() -> dict:
    """The form definition the kit was built with."""
    text = resources.files("ms_appkit").joinpath("resources/report_form.json").read_text("utf-8")
    return json.loads(text)


def intake_url() -> str:
    """Where reports go: the form's address, or what MS_REPORT_INTAKE says.

    Empty when sending is switched off.
    """
    override = os.environ.get(INTAKE_ENV, "").strip()
    if override.lower() == "off":
        return ""
    return override or form()["intake_url"]


@dataclass
class Attachment:
    """One file going with the report, already read into memory."""

    name: str
    data: bytes

    @property
    def extension(self) -> str:
        return self.name.rsplit(".", 1)[-1].lower() if "." in self.name else ""

    @property
    def content_type(self) -> str:
        return _CONTENT_TYPES.get(self.extension, "application/octet-stream")

    @classmethod
    def from_path(cls, path: Path) -> Attachment:
        return cls(Path(path).name, Path(path).read_bytes())


def refusal(existing: list[Attachment], new: Attachment, limits: dict | None = None) -> str:
    """Why ``new`` cannot join ``existing``: a plain sentence, or '' when it can.

    The same limits the intake enforces, checked here so the person hears it
    before anything is sent rather than as a refused upload afterwards.
    """
    limits = limits or form()["attachments"]
    prefix = form()["wording"]["refused_prefix"]
    mb = 1024 * 1024
    if len(existing) >= limits["max_files"]:
        return f"{prefix}up to {limits['max_files']} files can go with one report."
    if new.extension not in limits["extensions"]:
        return f"{prefix}{new.name} is not a kind of file a report can carry ({limits['hint']})"
    if len(new.data) > limits["max_file_mb"] * mb:
        return f"{prefix}{new.name} is larger than {limits['max_file_mb']} MB."
    if sum(len(a.data) for a in existing) + len(new.data) > limits["max_total_mb"] * mb:
        return f"{prefix}the files together would be more than {limits['max_total_mb']} MB."
    if any(a.name == new.name for a in existing):
        return f"{prefix}a file called {new.name} is already attached."
    return ""


def next_paste_name(existing: list[Attachment]) -> str:
    """paste-1.png, paste-2.png ... the same names the web form gives."""
    taken = {a.name for a in existing}
    number = 1
    while f"paste-{number}.png" in taken:
        number += 1
    return f"paste-{number}.png"


@dataclass
class Sent:
    number: int | None
    url: str


@dataclass
class Submission:
    """Everything the intake receives for one report."""

    report: Report
    email: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    edited_text: str | None = None     # the preview as the person left it, if touched

    def payload(self) -> dict:
        info = app()
        if self.edited_text is not None:
            title, _, body = self.edited_text.partition("\n\n")
        else:
            title, body = self.report.title, self.report.body()
        data = {
            "slug": info.slug,
            "app_version": info.version,
            "kind": self.report.kind,
            "title": title.strip()[: form()["fields"]["title"]["max_length"]],
            "body_markdown": body,
        }
        if self.email.strip():
            data["email"] = self.email.strip()
        if self.attachments:
            data["attachments"] = [
                {"name": a.name, "content_type": a.content_type,
                 "data_base64": base64.b64encode(a.data).decode("ascii")}
                for a in self.attachments
            ]
        return data


class IntakeError(Exception):
    """The intake could not be reached or refused the report; nothing was sent."""


def send(submission: Submission, url: str | None = None, opener=None) -> Sent:
    """Post the report; return the issue number (and link, for a public repository).

    Raises :class:`IntakeError` with a sentence a person can act on. The
    caller keeps the text on the clipboard either way, so nothing is lost.
    """
    from ms_appkit.update.net import open_url

    target = intake_url() if url is None else url
    if not target:
        raise IntakeError("sending is switched off on this computer (MS_REPORT_INTAKE=off)")
    body = json.dumps(submission.payload()).encode("utf-8")
    request = urllib.request.Request(
        target.rstrip("/") + "/v1/reports", data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": f"{app().slug}/{app().version} ms-appkit"},
    )
    open_it = opener or open_url
    try:
        with open_it(request, timeout=TIMEOUT_S) as response:
            answer = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8"))
        except (ValueError, OSError):
            detail = {}
        if error.code == 400 and detail.get("rule"):
            raise IntakeError(f"{form()['wording']['refused_prefix']}{detail['rule']}") from error
        raise IntakeError(f"Machine Saver answered {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        raise IntakeError(str(error)) from error
    return Sent(number=answer.get("number"), url=answer.get("url") or "")


def received_wording(sent: Sent) -> str:
    """The sentence to show once the intake has the report."""
    words = form()["wording"]
    key = "received_public" if sent.url and not app().is_private else "received_private"
    return words[key].replace("{number}", str(sent.number or "?"))
