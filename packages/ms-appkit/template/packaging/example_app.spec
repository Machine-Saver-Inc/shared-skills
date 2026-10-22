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
        "example_app", "certifi", "ms_appkit.signin", "ms_appkit.auth",
        "ms_appkit.secrets", "keyring", "keyring.backends.Windows",
        "keyring.backends.SecretService",
        # The Kit's driver is imported only when a Kit is opened (devices/ppk2.py).
        "ppk2_api", "ppk2_api.ppk2_api", "serial", "serial.tools", "serial.tools.list_ports",
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
