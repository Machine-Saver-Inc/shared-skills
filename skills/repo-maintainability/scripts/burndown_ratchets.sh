#!/usr/bin/env bash
# Run every ratcheted finding tool on the checkout and fail on any finding not
# in its baseline (ADR 0019). The burn-down runs it twice: on the untouched
# tree, so a main that already fails is never blamed on a target, and on the
# changed tree (ADR 0022).
#
#   burndown_ratchets.sh OUT_DIR
#
# Leaves ruff.txt, vulture.txt and jscpd.txt in OUT_DIR for `burndown_pick.py
# verify`. No pipefail: the tools exit non-zero when they find anything, and
# the ratchet after the pipe is the verdict.
set -eu

out=$1
mkdir -p "$out"
here=$(dirname "$0")

ruff check --config .maintainability/ruff.toml --output-format concise . 2>/dev/null \
  | grep -E '^[^ ]+:[0-9]+:[0-9]+: ' > "$out/ruff.txt" || [ $? -eq 1 ]
python3 "$here/ratchet.py" check --baseline .maintainability/ruff.baseline < "$out/ruff.txt"

vulture --min-confidence 80 scripts cloud mcp eval > "$out/vulture.txt" 2>/dev/null || [ $? -eq 3 ]
python3 "$here/ratchet.py" check --baseline .maintainability/vulture.baseline < "$out/vulture.txt"

git ls-files -z '*.sh' | xargs -0 shellcheck -f gcc -S warning 2>/dev/null \
  | python3 "$here/ratchet.py" check --baseline .maintainability/shellcheck.baseline

rm -rf "$out/jscpd"
jscpd --silent --reporters json --output "$out/jscpd" \
      --format python,bash,powershell,yaml --min-lines 12 --min-tokens 70 \
      scripts cloud edge >/dev/null 2>&1 || true
# No report means jscpd did not run, not that every duplicate is gone.
test -s "$out/jscpd/jscpd-report.json"
python3 "$here/jscpd_findings.py" "$out/jscpd/jscpd-report.json" > "$out/jscpd.txt"
python3 "$here/ratchet.py" check --baseline .maintainability/jscpd.baseline < "$out/jscpd.txt"
