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
# The same net on Linux (1.10039), where the data folder follows
# $XDG_DATA_HOME.
os.environ["XDG_DATA_HOME"] = os.path.join(os.environ["LOCALAPPDATA"], "xdg")
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
    ("1.10037: the results box no longer loops itself to death", "test_110037_scroll.py"),
    ("1.10038: Find one search at a time, and any tool tab pops out", "test_110038_find.py"),
    ("1.10038: Earnings in four pages, and short Why cells", "test_110038_earnings.py"),
    ("1.10038: the leaderboard's three views, far from Sol, your standing", "test_110038_board.py"),
    ("1.10038: the mining location you are in, without targeting it", "test_110038_zone.py"),
    ("1.10039: the overlay boxes change shape - a keystone and a bend", "test_110039_warp.py"),
    ("1.10039: Powerplay themes, match my in-game HUD colours, the Theme tab", "test_110039_theme.py"),
    ("1.10039: Linux - the journal in a Wine prefix, joystick, hotkeys, overlay, packaging", "test_110039_linux.py"),
    ("1.10040: one build per version, on the website and on GitHub alike", "test_110040_release_pipeline.py"),
    ("1.10040: the EDSMT page looks like the rest of radioraxxla.com, with the weekly update", "test_110040_site.py"),
    ("1.10040: the welcome window, the EDSMT logo and Help", "test_110040_welcome.py"),
    ("1.10040: the overlay uses the app theme", "test_110040_overlay_theme.py"),
    ("1.10040: status strip, chevron tabs, shortcut bar, spacing and theme arrows", "test_110040_chrome.py"),
    ("1.10040: a launcher can see EDSMT is running", "test_110040_hub.py"),
    ("1.10040: several Discord webhooks of your own, every address a secret", "test_110040_webhooks.py"),
    ("1.10040: streamer mode - names hidden for a delay, posts held, bigger text", "test_110040_streamer.py"),
    ("1.10040: the session on a stream - the OBS page, the viewer card, the session card, the text shadow", "test_110040_stream.py"),
    ("1.10040: the EDSMT logo is the icon in both builds, the installer and the favicon", "test_110040_logo_build.py"),
    ("1.10040: the settings a new install starts with", "test_110040_defaults.py"),
    ("1.10040: EDSMT's own address, with the first one as a fallback", "test_110040_address.py"),
    ("1.10040: a dark backdrop behind the overlay on bright ground", "test_110040_backdrop.py"),
    ("1.10040: pairing with the member page on radioraxxla.com", "test_110040_pairing.py"),
    ("1.10040: one tick chain, however often tick is called", "test_110040_tick.py"),
    ("1.10040: a site card from Find and Where to land", "test_110040_sitecard.py"),
    ("1.10040: the ship minimap - the scope up by itself low over a body with finds", "test_110040_shipview.py"),
    ("1.10040: signed updates - version.json signed on the build machine, checked by the app", "test_110040_signed.py"),
    ("1.10040: the scope comes back once every pin has a rig on it", "test_110040_plan_done.py"),
    ("1.10040: a site takes twelve rigs - two Rhinos' worth - the Rhino itself still six", "test_110040_rigs.py"),
    ("1.10040: Share my week - your week on the surface as a card from the community map", "test_110040_weekcard.py"),
    ("1.10040: the squadron share - carriers, orders, Powerplay and hauling to your squadron's site, off by default", "test_110040_squadron.py"),
    ("1.10040: mining locations to EDDN - live FSS events only, cross-checked, one schema", "test_110040_eddn.py"),
    ("1.10040: best to mine, the Value sort, by ground, the location line worth most first", "test_110040_bestmine.py"),
    ("1.10040: good and bad marks on a shared site, kept until they can be sent", "test_110040_marks.py"),
    ("1.10040: you on the map and the scope in a colour of your own", "test_110040_srv_colour.py"),
    ("1.10040: the wing - linked from the in-game wing, one shared survey, pins split", "test_110040_wing.py"),
    ("1.10040: the wing on the map, the scope and in Settings", "test_110040_wing_gui.py"),
    ("1.10040: choose which materials the commodity lists offer", "test_110040_materials.py"),
    ("1.10040: Find's Powerplay search, mine-to-sell rows for a goal", "test_110040_powerplay.py"),
    ("1.10040: Voice Mode, spoken directions, the proximity sonar and a VoiceAttack profile", "test_110040_voice.py"),
    ("1.10040: the big tables on the tree view, 2,000 rows drawn and scrolled in a budget", "test_110040_tables.py"),
    ("1.10040: the journal read in chunks off the window's thread, timed", "test_110040_speed.py"),
    ("1.10040: the journal's own checks on a session - transfers, Statistics, ejected tonnes, trace, prices", "test_110040_journal_rows.py"),
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
