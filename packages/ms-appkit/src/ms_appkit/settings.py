"""A settings file, per program, in the program's own folder.

Deliberately a plain dictionary in a JSON file rather than QSettings: the file
can be read over someone's shoulder on a machine with no internet, copied to
another machine, and pasted into a problem report.

Settings are a convenience, never load-bearing. Every failure here is swallowed
and logged; a program must start with its defaults when the file is missing,
unreadable or corrupt, because a lab PC that will not open is worse than one
that has forgotten which port it used.
"""

from __future__ import annotations

import json
import logging

from ms_appkit.identity import app

log = logging.getLogger(__name__)

# Kept by the kit itself, so the footer's version line survives a restart.
SHARED_DEFAULTS = {
    "check_for_updates": True,
    "last_update_check": None,
    "last_update_check_failed": False,
}


def settings_path():
    return app().home / "settings.json"


def load(defaults: dict | None = None) -> dict:
    """The stored settings, with anything missing filled in from the defaults."""
    data = {**SHARED_DEFAULTS, **(defaults or {})}
    try:
        stored = json.loads(settings_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return data
    except (OSError, ValueError) as exc:
        log.warning("could not read %s (%s); using defaults", settings_path(), exc)
        return data
    for key, value in stored.items():
        # A nested group is merged rather than replaced, so a setting added in
        # a later release appears with its default instead of vanishing.
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    return data


def save(data: dict) -> None:
    """Write via a temporary file, so a crash mid-write cannot empty it."""
    path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        log.warning("could not save settings to %s: %s", path, exc)
