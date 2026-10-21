# Contributing to EDSMT

Bug reports and patches are welcome. This guide covers how to run the project,
the rules a change has to follow, and what will not be merged.

## Run from source

    RUN.bat

On Windows this finds Python, creates `.venv`, installs `requirements.txt` and
starts the app. The only runtime dependency is `customtkinter`; the plan view
is drawn on a plain canvas.

## Run the tests

    python tests/run_all.py

One command runs every check. It needs no display, no Tkinter and no Elite
Dangerous: the widgets are stubbed and the logic underneath is driven with
synthetic `Status.json` and `Journal.*.log` files. A suite whose dependency is
missing is reported as skipped, not passed; read the summary at the end of the
output. `BUILD.bat` runs the same command and will not build if it fails.

## Rules for a change

- **Patch, do not rewrite.** Change the working code in place and explain
  exactly what changed and why. Comments in the source record the reason for
  the code beside them; keep them accurate.
- **Every fix comes with a test that fails without it.** Write the test, see
  it fail against the unfixed code, then fix the code.
- **Test headlessly.** Import the module with the toolkit stubbed
  (`tests/stubs/`) and exercise the logic. Anything that cannot be tested that
  way belongs behind a plain function that can.
- **Validate customtkinter calls statically.** `tests/test_ctk_api.py` checks
  every `ctk.CTk*` call against the installed library's signatures.
  `bind_all` is forbidden; customtkinter rejects it.
- **Do not shadow toolkit methods.** Assigning an attribute that replaces a
  tkinter or customtkinter method (`self.state = None`, for example) breaks
  the library. `tests/test_shadowing.py` checks for it.
- **Bump the version for every change.** Run `python build/bump.py`. It
  updates every version field together, and `tests/test_packaging.py` fails if
  they disagree.
- **No silent failures.** Errors must reach the status line or `crash.log`.
  Do not add a bare `except: pass`.
- **Batch files keep CRLF line endings.** `BUILD.bat` and `RUN.bat` break
  otherwise; the tests check it.
- Add a `CHANGELOG.md` entry that says what was wrong, not only what is new.

## Building

    BUILD.bat

Move the version on first with `python build/bump.py`. `BUILD.bat` runs the
tests, fetches Inno Setup if it is missing, and writes to `upload/`:

    EDSMT-Setup.exe    installer
    EDSMT.exe          portable build
    EDSMT-source.zip   source for the release

Pushing a version tag runs `.github/workflows/build.yml`, which builds the same
three files on a Windows runner and attaches them to a GitHub release.

## What will not be merged

- **Anything that weakens update integrity.** Updates come from
  radioraxxla.com over HTTPS only, must match the size and SHA-256 published in
  `version.json`, are checked again at install, and run only when the user
  presses INSTALL UPDATE. `tests/test_update.py` covers each of these.
- **Uploading anything beyond finds and prices.** Nothing else on a user's PC
  leaves it, and the commander name stays optional.
- **A dependency that brings in another GUI or plotting toolkit.**

## Reporting bugs and vulnerabilities

Use the issue templates; they ask for the version shown in the title bar.
Report vulnerabilities privately, as described in `SECURITY.md`.

## Source tree

    edsmt.py       the main window
    survey.py      locations, deposits and geometry
    planview.py    plan view maths
    overlay.py     in-game overlay boxes
    journal.py     Status.json and journal reading
    edonline.py    Inara, the community client and ranking
    rigplan.py     rig planner
    coverage.py    survey coverage per body
    bodybook.py    bodies per system (Where to land)
    build/         PyInstaller and Inno Setup configuration
    tests/         headless test suite
    site/          download page
    sounds/        rig warning sounds
    .github/       build workflow and issue templates

## Licence

EDSMT is GPL-3.0-only. By contributing you agree that your work is released
under the same licence.
