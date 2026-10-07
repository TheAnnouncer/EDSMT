# Contributing to EDSMT

Patches are welcome. So are bug reports, and so is a copy of
`journal-mining-events.log` — that one is worth more than most code.

This document is short on etiquette and long on the four or five rules that
have each cost this project a release. They are not style preferences.

---

## Run it from source

    RUN.bat

That is the whole thing on Windows. It finds Python, makes `.venv`, installs
`requirements.txt` into it and starts the app. First run takes a minute; after
that it is instant. If Python is missing it offers to install it.

The only dependency is `customtkinter`. There is no plotting library — the
plan view is drawn on a plain canvas, which is why the app opens in about a
second and the download is a few MB rather than fifty.

The community map at `api.radioraxxla.com` is run by Radio Raxxla and is not
part of this repository. You do not need it to work on the app: the tests
stand in for it.

---

## Run the tests

    python tests/run_all.py

Every check, in one command. It needs **no display, no Tkinter and no Elite
Dangerous** — the widgets are stubbed and the real logic underneath is driven
with synthetic `Status.json` and `Journal.*.log` files.

Green means every suite passed. Read the last few lines rather than the exit
code alone: a suite whose dependency is missing is **skipped**, not passed,
and the runner says which. The customtkinter checks skip when customtkinter
is not installed. A skipped suite is not evidence of anything.

`BUILD.bat` runs the same command and refuses to build if it fails.

---

## The rules that matter here

### Never rewrite a file from scratch

A ground-up rewrite replaced a working 1,200-line file once, and broke it.
Patch the working file surgically and say exactly what you changed.

This is not sentiment about old code. The comments in these files are the
project's memory: nearly every one of them is a bug that got out, written
down at the line that caused it. A rewrite throws that away and the same bugs
come back.

### Prove the fix by reintroducing the bug

A test that passes before your change is not a test of your change. Write the
test, watch it fail against the unfixed code, then fix it.

Two tests in this repo passed for months while the feature under them was
broken. One asserted against a fixture that accepted anything. Another ran
`EXPLAIN QUERY PLAN` on a copy of the SQL typed into the test file, so it
would have kept passing after the endpoint stopped using the index. Both had
to be replaced with tests that fail on the bug.

### Test headlessly

CI has no display and no Tkinter, so GUI code cannot be run there to check
it.

So: import the module with the toolkit stubbed, and drive the real logic
underneath. `tests/stubs/` has what you need. Anything that cannot be tested
that way belongs behind a plain function that can be.

### Validate customtkinter calls statically

`tests/test_ctk_api.py` parses the installed customtkinter source for every
class signature and checks every `ctk.CTk*` call in the app against it. That
is the only way to know a widget call is valid when the app cannot be started.

**`bind_all` is forbidden.** customtkinter raises on it by design. It shipped
once and the app died on launch with a traceback naming the library rather
than the line that called it. The test refuses it by name.

The neighbouring check, `test_shadowing.py`, catches the other half of the
same problem: assigning an attribute over a toolkit method. `self.state = None`
in the main window replaced tkinter's own `state()`, which customtkinter calls
during startup, so the app died before drawing a pixel.

### Move the version on, every time

    python build/bump.py

The version lives in seven fields across three files. Every release that
edited six of them shipped a build reporting the wrong number somewhere, so
this does all seven at once and `test_packaging.py` fails if they ever
disagree.

Run it for every change, however small. A build you cannot name is a bug
report you cannot place.

### Nothing fails silently

Tk prints an exception raised inside a callback to a console and carries on.
In an installed build there is no console, so a broken button was simply a
dead button and the commander was told nothing. Every silent failure this app
has shipped went out through that hole.

`report_callback_exception` is installed on the main window now, and writes a
stamped traceback to `crash.log`. Do not add a bare `except: pass` that puts
the hole back.

---

## What a good change looks like

- One thing, patched in place, with the reason in a comment at the line.
- A test that fails without it.
- `python build/bump.py` run.
- `python tests/run_all.py` green, with no suite skipped that was not skipped
  before.
- A `CHANGELOG.md` entry that says what was wrong, not just what is new.

Line endings matter on the batch files: `BUILD.bat` and `RUN.bat` are CRLF
throughout, because `goto` stops working in a LF file. The test checks it.

## What is off the table

- **Loosening the update rules.** The app downloads a new build by itself,
  and that is only acceptable because of the fence round it: radioraxxla.com
  over HTTPS only, the exact size and SHA-256 from `version.json`, checked
  again at install, and nothing run until the commander presses INSTALL
  UPDATE. `tests/test_update.py` holds every one of those. A change that
  weakens any of them - another host, a skipped check, an install without
  the click - will not be merged.
- **Uploading anything beyond the finds and prices.** Every deposit goes on
  the community map - that is the point of it - but nothing else on a
  commander's PC does, and the CMDR name stays optional.
- **A dependency that pulls in a toolkit.** See `requirements.txt` for why
  the upper bounds are there.

---

## Licence

EDSMT is GPL-3.0. By contributing you agree your work ships under it.

---

## Running and building

    RUN.bat     run it from source, no build needed
    BUILD.bat   compile it

Before building, move the version on with `python build/bump.py`.

`BUILD.bat` finds or fetches Inno Setup, runs the test suite and refuses to
build if anything fails, then compiles twice and leaves the `upload` folder
holding everything the website needs:

    EDSMT-Setup.exe    the download link
    EDSMT.exe          the same program, portable
    EDSMT-source.zip   GPL-3.0 obliges us to offer the source

Two compiles because they are different jobs. The installer packages a folder
build, so it starts instantly. The portable exe is one file that unpacks
itself to temp each launch — the right trade when there is no installer to
put a folder anywhere.

There is also `.github/workflows/build.yml`: push a tag and GitHub builds all
three on a real Windows machine and attaches them to a release, so an
installer exists without anyone having to build one.

`test_packaging.py` checks the bundle rather than the code: line endings on
the batch files, characters `cmd` would read as redirection, version drift
across the installer and the app, unused imports, functions written and never
wired up, and files the docs name that do not exist.

---

## Help document the schema

`docs/SURFACE-MINING-JOURNAL.md` is the running specification: every
surface-mining journal event, field and quirk this project has established,
with each claim labelled by how it was established and how confident it is.
Written to be handed to EDCD, who maintain the community journal
documentation.

The headline of it is worth repeating here, because it is easy to assume
otherwise: **no surface-mining-specific journal event has been observed at
all.** What exists is the in-game structure, the fields on existing events
that already carry surface-mining data, and a way of capturing new events
without knowing their names first.

`journal-mining-events.log`, in `%LOCALAPPDATA%\RadioRaxxla\EDSMT`, collects
the first example of every surface-mining event the game does write. **One
real captured event is worth more to that document than anything else anybody
can send.** Open an issue with it attached, or post it to the forums — either
way the schema gets written down for every tool that follows, which is a
bigger win for the community than this app is.

---

## Reporting bugs

Bugs and requests go through the issue templates, which ask for the version
off the title bar first. That is what the number is there for.

`SECURITY.md` is the one to read before anything else: a vulnerability
goes through private reporting rather than a public issue, and it explains
the unsigned build, the SmartScreen warning and the VirusTotal result in
full rather than leaving you to find them yourself.

---

## The source tree

    edsmt.py           the window
    survey.py          the model - locations, deposits, geometry
    planview.py        the plan view maths
    overlay.py         the in-game HUD boxes
    journal.py         reading Status.json and Journal.*.log
    edonline.py        Inara, the community map client, ranking
    rigplan.py         the rig planner
    build/             PyInstaller and Inno Setup configuration
    tests/             the headless test suite, including one check per
                       numbered requirement
    site/              the download page on radioraxxla.com
    sounds/            the rig warnings
    .github/           the Windows build, and the issue templates
    docs/              the surface-mining journal specification
    JOURNAL-NOTES.md   everything learned about the journal
    CONTRIBUTING.md    running from source, and the rules that matter here
    SECURITY.md        reporting a vulnerability, and the unsigned build
