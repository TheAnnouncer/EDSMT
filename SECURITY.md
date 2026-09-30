# Security

## Reporting something

**Do not open a public issue for a vulnerability.**

Use GitHub's private reporting: the **Security** tab on this repository →
**Report a vulnerability**. It goes to the maintainer and nobody else, and it
keeps the discussion attached to the fix.

If that is unavailable to you, reach CMDR TheAnnouncer through the COMMS page
on [radioraxxla.com](https://www.radioraxxla.com/) and say only that you have
a security report — no detail in the first message.

Expect an acknowledgement within a few days. This is one person who also runs
a repair shop; it is not a 24-hour desk. A fix ships as a normal numbered
release with the cause written up in `CHANGELOG.md`, because a fix nobody can
see the reason for is a fix nobody trusts.

Only the latest version is supported. There is no back-porting: the app tells
you on launch when a newer build exists, and updating keeps your finds.

---

## The unsigned build, stated plainly

**EDSMT is not code signed.** A Windows code-signing certificate costs several
hundred pounds a year and this tool is free, so there is no certificate behind
it.

Two things follow, and both look alarming if nobody has told you in advance.

### SmartScreen will warn on first run

You will get *"Windows protected your PC"*. That is Microsoft's reputation
check on an unsigned binary nobody has downloaded many times yet, not a
detection of anything. **More info → Run anyway.**

It fades as more people install it and comes straight back on the next
release, because reputation attaches to the file, not the project.

### VirusTotal: 4 of 71 engines

Submitted and checked. **Four engines flag it. All four are machine-learning
or heuristic detections. All 67 signature-based engines are clean.**

That pattern is what a PyInstaller build looks like to a heuristic scanner:
a self-extracting executable that unpacks a Python runtime to a temporary
folder and runs it. It is indistinguishable, from the outside, from a
technique that malware also uses. Every unsigned PyInstaller tool in this
community gets the same handful of hits.

This is stated rather than hidden because you are going to check, and finding
it yourself after being told nothing is worse than being told.

The remedies are the only two there are, and neither is a promise:
submitting false positives to the vendors, and signing the binary. Signing is
the real answer and is a money question, not a technical one.

**What you can do instead:** it is GPL-3.0. `EDSMT-source.zip` ships with
every release, `RUN.bat` runs the app straight from that source without
building anything, and the GitHub Actions workflow builds the exact same
binaries on a GitHub-hosted Windows runner where you can read the log. If you
do not want to trust a binary, do not — run the source.

---

## What the app actually does on your machine

Worth knowing before you decide whether any of the above matters.

- **It reads. It does not write to the game.** `Status.json`,
  `Journal.*.log`, `Market.json` and `Cargo.json` in your Saved Games folder,
  opened read-only. Nothing is ever written into that folder.
- **Its own data lives in `%LOCALAPPDATA%\RadioRaxxla\EDSMT`**, not the
  program folder.
- **It opens no listening socket.** There is no local server, no port and no
  remote-control surface. Every connection is outbound HTTPS that the app
  starts.
- **Updates: downloaded for you, run only when you say.** The update check
  reads a static `version.json` on radioraxxla.com. When it names a newer
  build, EDSMT downloads it in the background under these rules, each held by
  a test in `tests/test_update.py`:
  - **from radioraxxla.com over HTTPS only** — a `version.json` that names any
    other host is refused, and so is a redirect to one;
  - **kept only if it is exactly the file described** — the byte count and
    the SHA-256 published in `version.json` must both match, or it is
    deleted and nothing is installed;
  - **checked again at the moment it is run**, so a file changed on disk
    after it was downloaded is refused;
  - **run only when you press INSTALL UPDATE.** Nothing installs by itself,
    and nothing runs in the middle of a session.

  The checksum proves you got the file that was published; it cannot prove
  the website itself was not tampered with. Code signing is what closes that
  gap, and the build is not yet signed — see above. If you would rather
  fetch every build by hand, switch *Download new versions by myself* off in
  Settings and the button just downloads on request.
- **Global hotkeys.** Left Alt and the number row, and the same numbers with
  AltGr (Ctrl+Alt), by default - every one rebindable.
  They are registered with Windows so they work with the game in front. They
  capture those key combinations only, not what you type.
- **Your Inara key and staff token** are kept in `settings.json` in your own
  `%LOCALAPPDATA%` and sent only to Inara and the community server
  respectively. Settings shows both as dots until you press **Show**, and
  hides them again after 20 seconds, so Settings can be opened on stream.

## What leaves your machine

- **Nothing, until you switch sharing on.** You are asked once on first run
  and no is taken for an answer. The switch is in Settings either way.
- With it on: the position, commodity, density, rig count and body facts of
  what you record, plus the timestamp. **Your CMDR name is optional.**
- A deposit is a position, a commodity and a date. No personal data is
  collected, there is no account and there is no sign-up.
- **The wing link (beta) is off unless you switch it on and type a code.**
  With it on, every few seconds: your system, body, position on the surface,
  heading, whether you are in the SRV and where your rigs are - and your CMDR
  name only if name sharing is on. It goes to the community server, which
  hands it to whoever else has typed the same code and keeps it in memory
  only: nothing is written to disk, and you are forgotten two minutes after
  your last beat.
- **Inara reporting is off unless you paste your own Inara API key.** That key
  is yours, is stored in `settings.json` on your machine, and is sent to
  inara.cz and nowhere else.

`settings.json` therefore holds a credential. It is in `.gitignore`, and it
should not be in a bug report — see the issue template, which asks for the
status line rather than the file.

---

## The community API

`api.radioraxxla.com` is the server half, and its source is in `server/` under
the same licence. If you find something there, report it the same way.

Notes for anyone hosting their own copy — `server/DEPLOY.md` has the detail:

- It binds to localhost and is published by a reverse proxy. It is never
  exposed directly.
- `RR_STAFF` in the `.env` is the key that grants a site the *verified* badge.
  Treat it as a secret; `.env` is gitignored. Verification cannot be
  self-awarded by the app — the server grants it to a named holder and records
  who, because an unaccountable badge is worth less than no badge.
- Submissions are rate limited and validated, and a commander cannot
  corroborate their own report.
