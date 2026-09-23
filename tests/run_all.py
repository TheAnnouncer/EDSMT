"""Run every check. No display, no Tkinter, no Elite Dangerous required.

    python tests/run_all.py

This is what has to pass before a release. GUI code cannot be executed in
CI, so the widgets are stubbed and the real logic underneath is driven with
synthetic Status.json and Journal.*.log files.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = [
    ("survey model and plan view", "test_core.py"),
    ("a full session on Ega 1", "test_app.py"),
    ("every backlog row is really built", "test_backlog.py"),
    ("the community API", "test_server.py"),
    ("the in-game overlay", "test_overlay.py"),
    ("nothing shadows a toolkit method", "test_shadowing.py"),
    ("every window actually builds", "test_wiring.py"),
    ("every customtkinter call is valid", "test_ctk_api.py"),
    ("the bundle is fit to ship", "test_packaging.py"),
    ("the surveyed-ground map", "test_coverage.py"),
    ("where to land", "test_land.py"),
    ("updates download, install on a click", "test_update.py"),
    ("rigs down, and too far from them", "test_rigs.py"),
    ("the real toolkit, on a real display", "test_gui.py"),
]
# The checks on the documents that describe the live server live beside
# those documents, in the private folder, and never ship. That folder is
# EDSMT-Private, next to this project's folder - or, in the older layout,
# internal/ inside it. Where either exists - the machine that builds
# releases - they run with everything else. On GitHub neither does.
REPO_DIR = os.path.dirname(HERE)
PRIVATE = next((p for p in (os.path.join(REPO_DIR, "internal"),
                            os.path.join(os.path.dirname(REPO_DIR), "EDSMT-Private"))
                if os.path.isdir(p)), "")
INTERNAL_TESTS = os.path.join(PRIVATE, "tests") if PRIVATE else ""
os.environ["EDSMT_REPO"] = REPO_DIR
if INTERNAL_TESTS and os.path.isdir(INTERNAL_TESTS):
    for _name in sorted(os.listdir(INTERNAL_TESTS)):
        if _name.startswith("test_") and _name.endswith(".py"):
            CHECKS.append(("internal: " + _name[5:-3].replace("_", " "),
                           os.path.join(INTERNAL_TESTS, _name)))

passed, skipped, failed = 0, [], []
for label, script in CHECKS:
    print("=" * 66); print(label); print("=" * 66)
    result = subprocess.run([sys.executable, os.path.join(HERE, script)],
                            capture_output=True, text=True)
    out = result.stdout + result.stderr
    if label.startswith("internal:") and result.returncode == 0:
        # The internal checks describe the live server line by line. On a
        # pass there is nothing to read, and nothing about the server
        # belongs on a screen that might be shared or streamed - so a pass
        # is one line. A failure still prints in full.
        print("  %d internal checks passed" % out.count("  PASS  "))
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
# A skipped suite is not a pass. Saying so out loud is the difference
# between "the API is fine" and "nobody checked the API on this machine".
for label in skipped:
    print("SKIPPED: %s - see the note above it" % label)
if failed:
    print("FAILED: " + ", ".join(failed))
    raise SystemExit(1)
print("Everything passed.")
