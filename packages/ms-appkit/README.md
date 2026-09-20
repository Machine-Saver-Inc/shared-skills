# ms-appkit

The shell every Machine Saver desktop application is built on.

Not a template to copy — a package to import, so that when the report dialog
gains a field or the update check learns about a new failure, every application
gains it at its next release rather than one of them gaining it and the rest
drifting.

## Install

```toml
dependencies = [
  "ms-appkit @ git+https://github.com/Machine-Saver-Inc/shared-skills.git#subdirectory=packages/ms-appkit",
]
```

## A whole application

```python
# gateway_app/app.py
from ms_appkit.bootstrap import run

def main() -> int:
    from gateway_app.ui.main_window import MainWindow
    return run(name="Gateway Provisioning",
               repo="Machine-Saver-Inc/gateway-provisioning",
               version=__version__, slug="gateway-provisioning",
               window=MainWindow, single_instance=True)
```

```python
# gateway_app/ui/main_window.py
from ms_appkit.shell import AppWindow

class MainWindow(AppWindow):
    def __init__(self) -> None:
        super().__init__({"gateway": None})
        self.home = HomePage()
        self.HOME = self.add_screen(self.home, "Home")
        self.show_screen(self.HOME)
        self.start_update_check()

    def report_context(self) -> dict[str, str]:
        return {"Gateway": self.settings.get("gateway") or "none chosen"}

    def busy(self) -> str | None:
        return "a gateway is being provisioned" if self.working else None
```

That is the footer, the update banner and check, the problem report with the
action trail behind it, the version line, the Lucide icon set and the shared
stylesheet. A runnable version of the above is in [`template/`](template/).

## What is in it

| Module | What it gives you |
| --- | --- |
| `identity` | who this program is — name, repo, version, slug — stated once |
| `bootstrap` | `run()`: logging, stylesheet, `--version`, single-instance lock |
| `shell` | `AppWindow`: banner, screens, footer, report, updates, trail |
| `footer` | report · maker mark · version · check for updates |
| `widgets` | `button`, `primary`, `action_bar`, `FieldGroup`, form controls |
| `icons` | 59 vendored Lucide marks, tinted to the text beside them |
| `style` | one stylesheet, light and dark, extended rather than forked |
| `update` | check, download, verify, install; one trust context |
| `diagnostics` | the problem report, Qt-free, home paths redacted |
| `report_dialog` | the dialog, with an editable preview |
| `trail` | screens opened and buttons pressed, for the report to carry |
| `settings` | a JSON settings file that never stops the program starting |
| `housekeeping` | the house rules, as checks your test suite calls |

## The house rules

Copy [`template/tests/test_house_rules.py`](template/tests/test_house_rules.py)
into a new application and change the two names at the top. It calls
`ms_appkit.housekeeping`, so the checks improve without the file being touched
again.

They hold that every button comes from the helper and asks for a mark the
library actually has, that the same words always carry the same mark, that Back
is on the left *and* that no screen filled the row backwards, that the footer
carries the version and the maker, that no control is half-restyled, that every
mark is legible at 16px in both tints, and that every screen has a name a report
can use.

## Tests

```sh
pip install -e ".[dev]"
python -m pytest tests
cd template && PYTHONPATH=. python -m pytest tests
```

Adding a check means proving it fails when its rule is broken. Break the rule,
watch it go red, put it back — and clear `__pycache__` before trusting the
result, because a restored file can keep a stale `.pyc`.

## Licence

MIT. The vendored Lucide set is ISC and carries its own `LICENSE` beside the
files, with `SOURCE.md` recording which upstream file each one is.
