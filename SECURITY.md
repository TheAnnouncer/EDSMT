# Security

## Reporting a vulnerability

Please do not open a public issue for a vulnerability.

Use GitHub's private reporting: the **Security** tab of this repository, then
**Report a vulnerability**. The report goes to the maintainer only.

If that is unavailable, use the COMMS page on
[radioraxxla.com](https://www.radioraxxla.com/) and say only that you have a
security report; leave the detail for the reply.

You can expect an acknowledgement within a few days. A fix ships as a normal
numbered release, with the cause described in `CHANGELOG.md`.

Only the latest version is supported. EDSMT tells you on launch when a newer
build exists, and updating keeps your finds.

---

## Code signing

EDSMT is not code signed, which has two visible effects.

### SmartScreen warns on first run

Windows shows *"Windows protected your PC"* for any unsigned program it has not
seen downloaded often. It is a reputation check, not a detection.
**More info, then Run anyway.** The warning fades as more people install the
build and returns with each new release, because reputation attaches to the
file.

### VirusTotal

At the last check, 4 of 71 engines flagged the installer. All four were
machine-learning or heuristic detections; none of the signature-based engines
flagged it. That pattern is typical of PyInstaller builds, which unpack a
Python runtime to a temporary folder when they start.

If you would rather not run a binary, the project is GPL-3.0:
`EDSMT-source.zip` is published with every release, `RUN.bat` runs the app
directly from source, and the GitHub Actions workflow builds the same source on
a GitHub-hosted Windows runner with a public log.

---

## What the app does on your machine

- **It reads the game's files and writes nothing to them.** `Status.json`,
  `Journal.*.log`, `Market.json` and `Cargo.json` in your Saved Games folder
  are opened read-only.
- **Its own data is stored in `%LOCALAPPDATA%\RadioRaxxla\EDSMT`**, not in the
  program folder.
- **It opens no listening socket.** There is no local server, port or remote
  control. Every connection is an outbound HTTPS request that the app starts.
- **Updates are downloaded automatically and installed only when you choose.**
  The update check reads a static `version.json` on radioraxxla.com. A newer
  build is downloaded in the background under these rules, each covered by
  `tests/test_update.py`:
  - it must come from radioraxxla.com over HTTPS; a `version.json` naming any
    other host is refused, as is a redirect to one;
  - it is kept only if its size and SHA-256 match `version.json`, otherwise it
    is deleted and nothing is installed;
  - it is checked again at the moment it runs, so a file altered on disk after
    download is refused;
  - it runs only when you press INSTALL UPDATE, never in the middle of a
    session.

  The checksum shows you received the file that was published; it cannot show
  that the website itself was untampered. Code signing would close that gap.
  Settings has a switch to download new versions only on request.
- **Global hotkeys.** By default Left Alt with the number row, and the same
  numbers with AltGr (Ctrl+Alt); all can be rebound. They are registered with
  Windows so they work while the game is in front, and they capture those key
  combinations only, not what you type.
- **Credentials.** Any credential you enter, such as your Inara API key or a
  Discord webhook address, is stored in `settings.json` in your own
  `%LOCALAPPDATA%` and sent only to the service it belongs to. Settings shows
  them as dots until you press **Show**, and hides them again after 20 seconds.

## What leaves your machine

- **Your finds.** The position, commodity, density, rig count and body facts of
  each deposit you record, with a timestamp, and the prices at markets you
  open. This is what the community map is made of, so sharing it is not a
  switch. There is no account and no sign-up. Your commander name is optional:
  it is asked on first run and can be changed in Settings.
- **The wing link (beta) is off unless you switch it on and enter a code.**
  When on, your system, body, surface position, heading, SRV state and rig
  positions are sent every few seconds, with your commander name only if name
  sharing is on. Nothing is stored; you are dropped two minutes after your last
  update.
- **Inara reporting is off unless you enter your own Inara API key.** The key
  is sent to inara.cz and nowhere else.

`settings.json` holds credentials and should not be attached to a bug report.
The issue template asks for the status line instead.

---

## The community service

`api.radioraxxla.com` is operated by Radio Raxxla and is the only community
service EDSMT connects to. Report a problem with it the same way as any other
vulnerability.
