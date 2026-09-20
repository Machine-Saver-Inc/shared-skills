"""Entry point. Six lines of its own; the rest is the kit."""

from __future__ import annotations

from pathlib import Path

from example_app import APP_NAME, GITHUB_REPO, SLUG, __version__
from ms_appkit.bootstrap import run


def main() -> int:
    from example_app.ui.main_window import MainWindow

    return run(
        name=APP_NAME,
        repo=GITHUB_REPO,
        version=__version__,
        slug=SLUG,
        window=MainWindow,
        icon=Path(__file__).resolve().parent / "resources" / "icon.png",
        single_instance=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
