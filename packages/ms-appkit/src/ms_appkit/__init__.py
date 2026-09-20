"""ms-appkit -- the shell every Machine Saver desktop application is built on.

Not a template to copy. A package to import, so that when the report dialog
gains a field or the update check learns about a new failure, every application
gains it at its next release rather than one of them gaining it and the rest
drifting.

What it provides:

* :mod:`ms_appkit.identity` -- who this program is, stated once at startup.
* :mod:`ms_appkit.style` -- one stylesheet, light and dark.
* :mod:`ms_appkit.icons` -- the Lucide marks, vendored, tinted to the text.
* :mod:`ms_appkit.widgets` -- ``button``, ``action_bar``, the form controls.
* :mod:`ms_appkit.footer` -- report, maker mark, version, check for updates.
* :mod:`ms_appkit.shell` -- the window those three sit in.
* :mod:`ms_appkit.update` -- checking, downloading, verifying, installing.
* :mod:`ms_appkit.diagnostics` and :mod:`ms_appkit.report_dialog` -- the report.
* :mod:`ms_appkit.trail` -- what the operator did, for the report to carry.
* :mod:`ms_appkit.bootstrap` -- ``run()``, which wires all of the above.

The house rules these enforce, and the ones no test can, are in the
``ms-desktop-app`` skill alongside this package.
"""

from ms_appkit._version import __version__
from ms_appkit.identity import AppInfo, app, configure

__all__ = ["__version__", "AppInfo", "app", "configure"]
