"""The window. Screens and what this program does; nothing else.

The footer, the update banner, the report dialog and the trail arrive with
:class:`ms_appkit.shell.AppWindow` and are not rebuilt here.
"""

from __future__ import annotations

from ms_appkit.shell import AppWindow

from example_app.ui.pages import HomePage, SettingsPage

DEFAULTS = {"port": None}


class MainWindow(AppWindow):
    def __init__(self) -> None:
        super().__init__(DEFAULTS)

        self.home = HomePage()
        self.home.start_requested.connect(self._start)
        self.home.settings_requested.connect(lambda: self.show_screen(self.SETTINGS))
        self.HOME = self.add_screen(self.home, "Home")

        self.settings_page = SettingsPage(self.settings)
        self.settings_page.back.connect(lambda: self.show_screen(self.HOME))
        self.settings_page.saved.connect(self._save_settings)
        self.SETTINGS = self.add_screen(self.settings_page, "Settings")

        self.show_screen(self.HOME)
        self.start_update_check()

    # -- what the kit asks of every program ---------------------------------
    def report_context(self) -> dict[str, str]:
        """Whatever would otherwise be the first question back."""
        return {"Port": self.settings.get("port") or "none chosen"}

    def busy(self) -> str | None:
        """Completes "Updates are not offered while ...", or None."""
        return None

    # -- this program's own work --------------------------------------------
    def _start(self) -> None:
        ...

    def _save_settings(self, values: dict) -> None:
        self.settings.update(values)
        from ms_appkit import settings as settings_mod

        settings_mod.save(self.settings)
        self.show_screen(self.HOME)
