"""Run every check. No display, no Tkinter, no Elite Dangerous required.

    python tests/run_all.py

This is what has to pass before a release. GUI code cannot be executed in
CI, so the widgets are stubbed and the real logic underneath is driven with
synthetic Status.json and Journal.*.log files.
"""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
# Every check runs with its own %LOCALAPPDATA%, so nothing it does can reach
# the commander's real data folder - BUILD.bat runs this on his own PC. One
# check that forgot to set its own wrote its test settings over his on every
# build (fixed in 1.10034); this is the net under all of them.
os.environ["LOCALAPPDATA"] = os.path.join(
    tempfile.mkdtemp(prefix="edsmt-checks-"), "appdata")
CHECKS = [
    ("survey model and plan view", "test_core.py"),
    ("a full session on Ega 1", "test_app.py"),
    ("every backlog row is really built", "test_backlog.py"),
    ("the in-game overlay", "test_overlay.py"),
    ("nothing shadows a toolkit method", "test_shadowing.py"),
    ("every window actually builds", "test_wiring.py"),
    ("every customtkinter call is valid", "test_ctk_api.py"),
    ("the bundle is fit to ship", "test_packaging.py"),
    ("the surveyed-ground map", "test_coverage.py"),
    ("where to land", "test_land.py"),
    ("updates download, install on a click", "test_update.py"),
    ("rigs down, and too far from them", "test_rigs.py"),
    ("the map opens on the signal, keys and flashes", "test_signal_view.py"),
    ("what is aboard, and where to sell it", "test_hold.py"),
    ("the guide, rig types and the targeted signal", "test_guide.py"),
    ("themes for the app and the overlay", "test_themes.py"),
    ("UK English, everywhere it is read", "test_spelling.py"),
    ("my sites, on every body", "test_sites.py"),
    ("what the testers hit on 1.10029", "test_field.py"),
    ("what 1.10031 adds", "test_110031.py"),
    ("what 1.10032 adds", "test_110032.py"),
    ("what 1.10033 adds", "test_110033.py"),
    ("what 1.10034 adds", "test_110034.py"),
    ("what 1.10035 fixes", "test_110035.py"),
    ("1.10035: the map, the scope and the rig radar", "test_110035_map.py"),
    ("1.10035: hold, session ledger, map picture and Discord", "test_110035_output.py"),
    ("1.10035: Find filters, body search and Powerplay", "test_110035_search.py"),
    ("1.10035: guided survey, pointers, orbit line, rig radar band and planner", "test_110035_survey.py"),
    ("1.10035: one stop for the whole hold, within N jumps, price trends", "test_110035_sell.py"),
    ("1.10035: marking from range, chat commands, joystick buttons and the long press", "test_110035_input.py"),
    ("1.10035: imports, regrowth, My sites bin and stars, map filters, prompts", "test_110035_sites.py"),
    ("1.10036: the community leaderboard", "test_110036_leaderboard.py"),
    ("1.10036: regrowth and rig spacing measured by the community", "test_110036_crowd.py"),
    ("1.10036: the tools as tabs of the main window", "test_110036_tabs.py"),
    ("1.10036: journal-check fixes and the pre-sale line", "test_110036_journal.py"),
    ("1.10036: the rig button from the game's own binds", "test_110036_binds.py"),
    ("1.10036: Find past 500, merits earned on Earnings", "test_110036_find.py"),
    ("1.10036: mining bodies near me, galaxy-wide, with ground odds", "test_110036_galaxy.py"),
    ("the real toolkit, on a real display", "test_gui.py"),
]
# More checks kept on this machine only: EDSMT_EXTRA_CHECKS names one or more
# folders (separated as PATH is) whose test_*.py files run with everything
# else, each told where this project is through EDSMT_REPO.
REPO_DIR = os.path.dirname(HERE)
os.environ["EDSMT_REPO"] = REPO_DIR
for _folder in [f for f in os.environ.get("EDSMT_EXTRA_CHECKS", "").split(os.pathsep) if f]:
    if os.path.isdir(_folder):
        for _name in sorted(os.listdir(_folder)):
            if _name.startswith("test_") and _name.endswith(".py"):
                CHECKS.append(("local: " + _name[5:-3].replace("_", " "),
                               os.path.join(_folder, _name)))

# --quiet (the public build): a check that passes is one line, a failure
# prints in full. The full output is for the machine that builds releases.
QUIET = "--quiet" in sys.argv[1:]
passed, skipped, failed = 0, [], []
for label, script in CHECKS:
    print("=" * 66); print(label); print("=" * 66)
    result = subprocess.run([sys.executable, os.path.join(HERE, script)],
                            capture_output=True, text=True)
    out = result.stdout + result.stderr
    if (label.startswith("local:") or QUIET) and result.returncode == 0:
        # A pass is one line: nothing to read, and a screen that might be
        # shared or streamed has no use for the detail. A failure prints in
        # full.
        print("  %d checks passed" % out.count("  PASS  "))
    else:
        print(out.rstrip())
    print()
    passed += out.count("  PASS  ")
    if "  SKIP  " in out:
        skipped.append(label)
    if result.returncode != 0:
        failed.append(label)

print("=" * 66)
print("%d assertions passed" % passed)
# A skipped suite is not a pass, so it is said out loud.
for label in skipped:
    print("SKIPPED: %s - see the note above it" % label)
if failed:
    print("FAILED: " + ", ".join(failed))
    raise SystemExit(1)
print("Everything passed.")
