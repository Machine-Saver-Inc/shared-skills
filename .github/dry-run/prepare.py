"""Dry run only: a stand-in icon, and the template's own installer and
verification steps written out as scripts, unchanged."""

import struct
import sys
from pathlib import Path

import yaml

template, temp = Path(sys.argv[1]), Path(sys.argv[2])

# A 16x16 32-bit icon: header, one directory entry, a BMP with an AND mask.
pixels = b"\x30\x60\xc0\xff" * 256
mask = b"\x00" * 64
bmp = struct.pack("<IiiHHIIiiII", 40, 16, 32, 1, 32, 0, len(pixels) + len(mask), 0, 0, 0, 0)
image = bmp + pixels + mask
icon = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 16, 16, 0, 0, 1, 32, len(image), 22)
(template / "packaging" / "windows" / "icon.ico").write_bytes(icon + image)

# The template names an entry script and a resources folder it does not ship.
package = template / "example_app"
(package / "__main__.py").write_text(
    "import sys\n\nfrom example_app.app import main\n\nsys.exit(main())\n", encoding="utf-8")
(package / "resources").mkdir(exist_ok=True)
(package / "resources" / "placeholder.txt").write_text("dry run\n", encoding="utf-8")

steps = yaml.safe_load((template / ".github" / "workflows" / "release-private.yml")
                       .read_text(encoding="utf-8"))["jobs"]["build"]["steps"]
named = {s.get("name"): s for s in steps}
for name, out in (("Build the Windows installer, signed with its uninstaller", "installer-step.ps1"),
                  ("Windows says every program is signed by Machine Saver", "verify-step.ps1")):
    (temp / out).write_text("$ErrorActionPreference = 'Stop'\n" + named[name]["run"], encoding="utf-8")
    print(f"--- {out}\n{named[name]['run']}")
