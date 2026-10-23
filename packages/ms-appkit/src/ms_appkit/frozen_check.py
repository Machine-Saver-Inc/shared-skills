"""Prove a frozen build carries the modules it loads by name.

    python -m ms_appkit.frozen_check dist/ExampleTool/ExampleTool.exe \
        example_app._client_secret example_app._version

PyInstaller follows ``import`` statements. A module the program loads with
``importlib`` -- the stamped sign-in key is one -- gets in only when the spec
names it under ``hiddenimports``. Every Power Profiler release up to 0.2.5
shipped without its key that way (report 5); the release workflow now runs
this after the build and fails when a named module is missing. Prints what
is missing and exits 1; never prints a module's contents.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def frozen_modules(exe: Path) -> set[str]:
    """Every pure-Python module name inside the build's archive."""
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader

    archive = CArchiveReader(str(exe))
    names: set[str] = set()
    for entry, (_offset, _size, _unpacked, _flag, kind) in archive.toc.items():
        if kind != "z":          # 'z' is the PYZ archive of pure modules
            continue
        with tempfile.TemporaryDirectory() as folder:
            pyz = Path(folder) / "modules.pyz"
            pyz.write_bytes(archive.extract(entry))
            names.update(ZlibArchiveReader(str(pyz)).toc)
    return names


def missing(exe: Path, wanted: list[str]) -> list[str]:
    have = frozen_modules(exe)
    return [name for name in wanted if name not in have]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print(__doc__)
        return 2
    exe, wanted = Path(args[0]), args[1:]
    if not exe.is_file():
        print(f"FAIL: {exe} is not a file")
        return 1
    gone = missing(exe, wanted)
    for name in wanted:
        print(f"{'MISSING' if name in gone else 'present'}: {name}")
    if gone:
        print(f"FAIL: the build at {exe.name} does not carry {', '.join(gone)}; "
              "name each under hiddenimports in the spec (skill section 3)")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
