"""Starting a Machine Saver program: the six lines every one of them needs.

    from ms_appkit.bootstrap import run

    def main() -> int:
        return run(
            name="Gateway Provisioning",
            repo="Machine-Saver-Inc/gateway-provisioning",
            version=__version__,
            slug="gateway-provisioning",
            window=lambda: MainWindow(),
            icon=Path(__file__).parent / "resources" / "icon.png",
            single_instance=True,
        )

Logging to a file the report button can read, the shared stylesheet chosen for
the machine's own theme, ``--version`` answerable from a command line, and an
optional single-instance lock. A program that wants none of this can still
build its own ``QApplication``; it just has to call
:func:`ms_appkit.configure` first.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path

from ms_appkit.identity import app, configure


def start_logging(level: int = logging.INFO) -> Path:
    """A log file beside the settings, plus stderr. Returns where it went."""
    path = app().log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(path, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    return path


def run(name: str, repo: str, version: str, window: Callable[[], object],
        slug: str = "", icon: Path | None = None, extra_style: str = "",
        single_instance: bool = False, argv: list[str] | None = None) -> int:
    """Configure, build the application, show the window, run the loop."""
    argv = sys.argv if argv is None else argv
    configure(name=name, repo=repo, version=version, slug=slug)

    # Answerable from a command line, which matters when someone is on the
    # phone with a machine that has never seen the internet.
    if any(arg in ("--version", "-V") for arg in argv[1:]):
        print(f"{name} {version}")
        return 0

    start_logging()

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ms_appkit.style import build_stylesheet, is_dark

    application = QApplication(argv)
    application.setApplicationName(name)
    application.setApplicationVersion(version)
    application.setOrganizationName(app().organisation)
    # The window surface stays whatever the machine is set to; only the colours
    # that have to stay legible against it are chosen here.
    application.setStyleSheet(build_stylesheet(is_dark(application), extra_style))

    if icon and Path(icon).exists():
        application.setWindowIcon(QIcon(str(icon)))

    if single_instance:
        from ms_appkit.single_instance import acquire_lock

        if not acquire_lock():
            QMessageBox.warning(
                None, name,
                f"{name} is already running. Only one copy can use the "
                "hardware at a time.",
            )
            return 1

    made = window()
    made.show()
    return application.exec()
