# Example Tool

<!-- machine-saver-scope:start -->
## Scope

One paragraph: what the program does, for whom, on which bench or site.

**Owner:** Machine-Saver-Inc. **Development area:** Manufacturing / Quality.

## Ownership boundaries

Shared desktop shell behaviour belongs in shared-skills (`ms-appkit`). Say
here which other repositories hold the firmware, hardware or services this
program talks to, and that this program does not change them.

## Development tracking

Track work in this repository's issues and pull requests. Cross-repository work
is coordinated through the [Machine Saver development Projects](https://github.com/orgs/Machine-Saver-Inc/projects).
The [company development hub](https://github.com/Machine-Saver-Inc/Organizational)
records repository ownership and dependencies.
<!-- machine-saver-scope:end -->

One or two sentences for the person who will use it, in their words.

## Download and install

1. Download `ExampleTool-Setup-<version>.exe` from the newest release and
   double-click it.
2. Windows will say **"Windows protected your PC"**. Click **More info**, then
   **Run anyway**: the installer is not code-signed yet.
3. Click through the installer. No administrator rights are needed.

Once installed, the program offers each new version itself: **Check for
updates** is in the footer of every screen.

## What it looks like

| Home |
| --- |
| ![Home](docs/images/home.png) |

Regenerate the pictures with `python tools/screenshots.py` before every release.

## Where things are

| What | Where |
| --- | --- |
| Settings | `~\.example-tool\settings.json` |
| Log | `~\.example-tool\example-tool.log` |

## Reporting a problem

**Report a problem** in the footer gathers the version, the screen, and the
last things pressed, and sends it to Machine Saver.

## Running from source

```sh
python -m venv .venv
.venv/Scripts/activate            # Windows;  source .venv/bin/activate on Linux
pip install -e ".[dev]"
example-tool
```

## Tests

```sh
ruff check .
pytest
```

`tests/test_house_rules.py` is the family's shared checks; the rules live in
`ms_appkit.housekeeping`.

## Releasing

Push `main`, wait for CI to pass, then tag `vX.Y.Z`. The release workflow
builds the Windows installer, publishes it with `SHA256SUMS`, and verifies
what it published.
