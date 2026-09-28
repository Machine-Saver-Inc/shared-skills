"""Prove a private program's Google setup works, end to end, before shipping.

    python -m ms_appkit.private_check --client-json client.json \\
        --project <cloud project> --bucket <release bucket> \\
        --slug <folder in the bucket> --secret <a test secret>

Runs the kit's own code -- not a copy of it -- against the real Google:

1. signs in through a browser (the address is printed and written to
   ``--url-file``; open it, sign in, and if the browser cannot reach this
   machine's ``127.0.0.1`` -- Cloud Shell, a remote session -- request the
   address it lands on from this machine with ``curl``);
2. asks Google whether the sign-in stands, as a restart would;
3. reads ``<slug>/latest.json`` from the bucket, downloads the first file it
   names and checks it against ``SHA256SUMS``;
4. fetches the secret from Secret Manager (prints its length, never its value);
5. signs out, then proves the old sign-in is now refused rather than
   quietly accepted.

It prints PASS or FAIL for each step and never prints a token. The sign-in is
held in memory only; nothing is written to the credential store.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import ms_appkit
from ms_appkit import auth, secrets
from ms_appkit.identity import PrivateConfig
from ms_appkit.update import channel
from ms_appkit.update.checker import fetch_latest_release_detailed
from ms_appkit.update.installer import UpdateError, download_asset, verify_download


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--client-json", required=True, type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--secret", required=True)
    parser.add_argument("--domain", default="machinesaver.net")
    parser.add_argument("--support-email", default="")
    parser.add_argument("--url-file", type=Path, default=Path("sign-in-url.txt"))
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args(argv)

    installed = json.loads(args.client_json.read_text())["installed"]
    config = PrivateConfig(
        client_id=installed["client_id"],
        client_secret=installed["client_secret"],
        project=args.project,
        bucket=args.bucket,
        support_email=args.support_email or f"software-support@{args.domain}",
        domain=args.domain,
    )
    ms_appkit.configure(name="Private check", repo="", version="0.0.0",
                        slug=args.slug, visibility="private", private=config)
    failures = 0

    def step(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name}{'  - ' + detail if detail else ''}",
              flush=True)

    def show(url: str) -> bool:
        args.url_file.write_text(url)
        print(f"\nOpen this address and sign in:\n{url}\n", flush=True)
        return True

    session = auth.Auth(config, store=auth.MemoryStore(), browser=show)
    auth.use(session)

    try:
        status = session.sign_in(timeout=args.timeout)
        step("sign in", status.kind == "signed_in", status.email)
    except auth.SignInError as exc:
        step("sign in", False, str(exc))
        return 1

    status = session.status()
    step("sign-in still stands on restart", status.kind == "signed_in", status.footer_text())

    release, error = fetch_latest_release_detailed()
    step("read the release feed", error is None and release is not None,
         error or f"version {release.version}, files {sorted(release.assets)}")
    if release is not None:
        first = next((n for n in sorted(release.assets) if n != "SHA256SUMS"), None)
        try:
            with tempfile.TemporaryDirectory() as folder:
                release = release.__class__(**{**release.__dict__, "assets": {
                    first: release.assets[first],
                    "SHA256SUMS": release.assets.get("SHA256SUMS", "")}})
                from ms_appkit.update import checker

                checker.asset_pattern_for_this_platform = lambda: (first,)
                path = download_asset(release, destination=Path(folder))
                verify_download(path, release)
                step("download and verify a release file", True, first)
        except (UpdateError, TypeError, KeyError) as exc:
            step("download and verify a release file", False, str(exc))

    try:
        value = secrets.get(args.secret)
        step("fetch a secret", bool(value), f"{len(value)} characters")
    except secrets.SecretUnavailable as exc:
        step("fetch a secret", False, str(exc))

    kept = session.store.get()
    session.sign_out()
    step("sign out", session.store.get() is None)

    stale = auth.MemoryStore()
    stale.set(kept or "")
    after = auth.Auth(config, store=stale).status()
    step("the signed-out sign-in is refused, not accepted", after.kind == "revoked",
         after.kind)
    stolen = channel.GoogleCloudStorage(bucket=args.bucket, slug=args.slug,
                                        token=lambda: "not-a-real-token")
    _, error = fetch_latest_release_detailed(channel=stolen)
    step("the bucket refuses a request without a real sign-in", error is not None)

    print(f"\n{'All checks passed.' if not failures else f'{failures} check(s) failed.'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
