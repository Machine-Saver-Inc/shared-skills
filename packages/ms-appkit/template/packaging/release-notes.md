## Download

This is a private Machine Saver program: the installer is in Machine Saver's
release store, readable with a machinesaver.net Google account.

| Your computer | File to download |
| --- | --- |
| **Windows 10 / 11** | `ExampleTool-Setup-<version>.exe` |

Open the folder for this version in the Cloud console:
https://console.cloud.google.com/storage/browser/machinesaver-desktop-releases/example-tool/v<version>
and download the installer. Nothing else is needed; Python, Qt and every
dependency are bundled.

### Installing on Windows

1. Download `ExampleTool-Setup-<version>.exe`.
2. Double-click it.
3. The installer is signed by **Machine Saver Inc**. If Windows shows a blue
   **"Windows protected your PC"** notice (it can, for a new release, until
   enough people have installed it), click **More info** and check that
   *Publisher* says **Machine Saver Inc**, then **Run anyway**. If it says
   *Unknown publisher*, do not run it; use **Report a problem** instead.
4. Click through the installer. It needs **no administrator rights**. Leave
   *Create a desktop shortcut* ticked.
5. Launch **Example Tool** from the desktop icon and sign in with
   your machinesaver.net Google account when it asks.

### First run

Plug the Nordic Power Profiler Kit II in, fit the D-cell adapter in place of
the AirVibe's battery, open the program and press **Start a test**. Enter the
serial from the AirVibe's label and work through the steps; each one says what
to do on the bench and which numbers to copy from the Power Profiler. The
results are in `Documents\Example Tool` and in Machine Saver's cloud.

Full instructions: [README](https://github.com/Machine-Saver-Inc/example-tool#readme)

### Verifying your download

`SHA256SUMS` sits beside the installer and is what the in-app updater checks
against.

```sh
sha256sum -c SHA256SUMS --ignore-missing
```
