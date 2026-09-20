"""A cross-platform single-instance lock.

For any program that owns a piece of hardware -- a serial port, a printer, a
programming header. Two copies would fight over it and the loser would report
the device as dead.

If the lock file itself cannot be opened the program is allowed to start: a
broken lock must never be the reason someone cannot do their job.
"""

from __future__ import annotations

import atexit
import os
from pathlib import Path

from ms_appkit.identity import app

_handle = None


def lock_path() -> Path:
    folder = app().home
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "instance.lock"


def acquire_lock() -> bool:
    global _handle
    path = lock_path()
    try:
        _handle = path.open("w")
    except OSError:
        return True  # cannot lock; do not block the user over it

    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        _handle.close()
        _handle = None
        return False

    atexit.register(release_lock)
    return True


def release_lock() -> None:
    global _handle
    if _handle is not None:
        try:
            _handle.close()
        except OSError:
            pass
        _handle = None
