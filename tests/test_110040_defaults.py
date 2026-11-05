"""1.10040 (#313): the settings a new install starts with.

Taken from a well-used settings file through the app's own loader: only
plain preferences that differed from the shipped defaults - never a key,
token, webhook, path, commander, window position, device binding or a record
of what the app has already shown. A first-time commander still gets the
step-by-step guide on the overlay and the notes on every control.

    python tests/test_110040_defaults.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-defaults-")
# Never the commander's own settings: the app's data folder moves first.
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import edsmt as A           # noqa: E402
import supportbundle as SB  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


OWNER = {"chat_tags": True, "long_press_rig": True, "map_trail": False, "overlay_enabled": True,
         "overlay_show_deposit": True, "overlay_show_guide": True, "show_tips": True}
D = A.DEFAULT_SETTINGS
for key, value in sorted(OWNER.items()):
    check("a new install starts with %s = %r" % (key, value), D.get(key) == value, D.get(key))

print("== what never comes from anyone's own file ==")
check("no key, token or webhook has a value", all(not D[k] for k in D if SB.is_secret_key(k)),
      [k for k in D if SB.is_secret_key(k) and D[k]])
for key in ("journal_dir", "cmdr_name", "welcome_seen_version", "tour_done", "asked_to_share", "find_unlocked"):
    if key in D:
        check("%s is still the plain default" % key, not D[key], D[key])
check("the overlay still follows the app theme on a new install, in Imperial gold",
      D.get("overlay_follows_app", True) is True and D.get("app_theme") == "gold" and D.get("overlay_theme") == "gold")

print("== and a brand-new install really gets them ==")
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
fresh = A.load_settings()
check("load_settings with no file gives those choices",
      all(fresh.get(k) == v for k, v in OWNER.items()), {k: fresh.get(k) for k in OWNER})

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
