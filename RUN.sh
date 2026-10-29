#!/usr/bin/env bash
# EDSMT - Surface Mining Survey, on Linux. The same job as RUN.bat does on
# Windows: find a Python, make the .venv once, install what requirements.txt
# lists, start EDSMT. Run it from a terminal the first time, so you can read
# anything it says:
#
#     bash RUN.sh
#
# Elite Dangerous itself runs through Proton (Steam), Lutris, Heroic or
# Bottles; EDSMT finds the game's Saved Games folder inside whichever Wine
# prefix is being played in. docs/GUIDE.md has the Linux section.
set -u
cd "$(dirname "$0")" || exit 1

say() { printf '  %s\n' "$*"; }

echo
say "=========================================================="
say "   EDSMT - Surface Mining Survey"
say "=========================================================="
echo
say "Starting. First run takes a minute while it sets itself up."
echo

if [ ! -f edsmt.py ]; then
    say "PROBLEM: edsmt.py is not in this folder. This file must sit next"
    say "to it. This folder is: $PWD"
    exit 1
fi

# Python 3.10 or newer, with tkinter. Linux distributions ship tkinter as
# a separate package, so a Python that is new enough can still lack it.
PY=""
for candidate in python3 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
        && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done
if [ -z "$PY" ]; then
    say "Python 3.10 or newer is needed. Install it with your package manager,"
    say "for example:  sudo apt install python3 python3-venv python3-tk"
    say "         or:  sudo dnf install python3 python3-tkinter"
    say "then run this file again."
    exit 1
fi
if ! "$PY" -c 'import tkinter' >/dev/null 2>&1; then
    say "Python is there but tkinter is not. Install it, for example:"
    say "    sudo apt install python3-tk        (Debian, Ubuntu, Mint)"
    say "    sudo dnf install python3-tkinter   (Fedora)"
    say "    sudo pacman -S tk                  (Arch)"
    say "then run this file again."
    exit 1
fi

if [ ! -x .venv/bin/python ]; then
    say "Setting up..."
    if ! "$PY" -m venv .venv; then
        say "Could not make the .venv. On Debian and Ubuntu that needs:"
        say "    sudo apt install python3-venv"
        exit 1
    fi
    .venv/bin/python -m pip install --upgrade pip --quiet --disable-pip-version-check
    if ! .venv/bin/python -m pip install -r requirements.txt --quiet --disable-pip-version-check; then
        say "Setup failed. The error is above."
        exit 1
    fi
fi

say "Running."
echo
exec .venv/bin/python edsmt.py
