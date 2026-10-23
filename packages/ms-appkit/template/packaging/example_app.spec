# PyInstaller spec. One-folder, not one-file: a one-file build unpacks ~150 MB
# to a temp directory on every launch, which reads as a program that takes
# fifteen seconds to open.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent

# Qt is large. Excluding what we never touch is the difference between a
# download people tolerate and one they do not.
EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.Qt3DCore",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtNfc",
    "PySide6.QtPositioning", "PySide6.QtWebSockets", "PySide6.QtWebChannel",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtTest", "PySide6.QtSql", "matplotlib", "scipy", "pandas", "tkinter",
    "IPython", "PIL",
]

a = Analysis(
    [str(ROOT / "example_app" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "example_app" / "resources"), "example_app/resources")]
    + collect_data_files("ms_appkit"),          # the Machine Saver mark and the icons
    # Every function-level import, named here so the frozen build cannot end
    # up without it (skill sections 3 and 1a).
    hiddenimports=[
        # The sign-in key is stamped into _client_secret.py at release time and
        # loaded by name, so the packager ships it only when told to. Every
        # Power Profiler release up to 0.2.5 went out without it (report 5).
        "example_app", "example_app._client_secret", "certifi",
        "ms_appkit.signin", "ms_appkit.auth", "ms_appkit.secrets",
        "keyring", "keyring.backends.Windows", "keyring.backends.SecretService",
    ],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="ExampleTool",
    console=False,
    icon=str(ROOT / "packaging" / "windows" / "icon.ico") if sys.platform == "win32" else None,
)
COLLECT(exe, a.binaries, a.datas, name="ExampleTool")
