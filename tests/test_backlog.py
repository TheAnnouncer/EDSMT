"""Every backlog claim, checked against the code.

This file exists because #7 sat at BUILT for three releases while the
commander who first mapped a site was invisible on the search people
actually use. A status column is a thing somebody types; this is a thing
that fails.

Each row here is one numbered requirement from BACKLOG.md and a test that
would fail if it were quietly removed. It is deliberately coarse - it proves
the feature is REACHABLE, not that it is correct; correctness is the rest of
the suite. The failure it is built to catch is "written, never wired up",
which is how four functions shipped unreferenced this month.
"""
import ast, io, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def src(f): return io.open(f, encoding="utf-8").read()
APP, OV, PV, SV, EDO, SRV, JN = (src("edsmt.py"), src("overlay.py"),
    src("planview.py"), src("survey.py"), src("edonline.py"),
    src("server/main.py"), src("journal.py"))
tree = ast.parse(APP)
DEFS = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
CALLED = {getattr(n.func, "attr", getattr(n.func, "id", ""))
          for n in ast.walk(tree) if isinstance(n, ast.Call)}
# A Tk command= is a REFERENCE, not a call: `command=self.check_updates`
# never appears as ast.Call, and a check that only looks for calls declares
# every button handler in the app unbuilt. Both forms count as wired.
REFERENCED = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
REFERENCED |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}

def wired(name):
    """Defined AND reachable. A function nobody ever names is not built."""
    return name in DEFS and (name in CALLED or name in REFERENCED)

CHECKS = [
 # (#, claim, test)
 (1,  "Find window opens at all",            lambda: "_rewrap" in DEFS),
 (2,  "click-then-press hotkey binding",     lambda: wired("binding_from_event")),
 (3,  "says when a hotkey is taken",         lambda: "already taken" in APP),
 (4,  "copy buttons on system name",         lambda: "COPY_COLUMN = 0" in APP and APP.count("column=COPY_COLUMN") >= 2),
 (5,  "Find filters reach the server",       lambda: '"name"' in APP and "verified_only" in EDO),
 (6,  "sortable columns",                    lambda: wired("sort_by") and "def _sorted" in APP),
 (7,  "commander shown on EVERY table",      lambda: APP.count("self._found_by(row)") >= 3),
 (8,  "dynamic layout, scrollable rail",     lambda: "RAIL_WIDTH = 384" in APP),
 (9,  "beta tester credits",                 lambda: "BETA_TESTERS" in APP and "MJH430" in APP),
 (10, "Within N Ly reaches the server",      lambda: "star_position" in APP and APP.count("def here(") == 1),
 (11, "radar scope overlay",                 lambda: "def draw_radar" in OV),
 (12, "centre on the signal",                lambda: "site_centre" in PV),
 (13, "centre on SRV as alternative",        lambda: "overlay_centre" in APP),
 (14, "range rings + stated radius",         lambda: "MAP RADIUS" in OV),
 (15, "dots by commodity, sized by rigs",    lambda: "marker_radius" in PV),
 (16, "off-screen chevrons with range",      lambda: "arrow_points" in PV),
 (17, "2km scanner ring round the SRV",      lambda: "SCANNER_RANGE_M" in PV and "_scanner" in OV),
 (18, "auto-zoom capped",                    lambda: "MAX_MAP_RADIUS_M" in PV),
 (19, "amber Radio Raxxla HUD",              lambda: "#ff7a18" in OV),
 (20, "compass strip kept as a mode",        lambda: "def draw_strip" in OV),
 (21, "next target + best patch",            lambda: "next_target" in PV and "best_patch" in PV),
 (22, "outlier rejection on site centre",    lambda: "OUTLIER_FACTOR" in PV),
 (23, "one range format everywhere",         lambda: "def format_range" in OV),
 ("23a","scope AND tape at once",            lambda: "overlay_show_strip" in APP and "overlay_show_radar" in APP),
 ("23b","drag then lock",                    lambda: wired("toggle_overlay_lock") and "_grab" in OV),
 ("23c","layout as screen fractions",        lambda: "panel_fractions" in OV and "panel_pixels" in OV),
 ("23d","TARGETS box",                       lambda: "def draw_targets" in OV),
 ("23e","STATUS box",                        lambda: "def draw_status" in OV),
 ("23f","reset box positions",               lambda: wired("reset_overlay_layout") or "reset_boxes" in APP),
 (24, "auto-fill re-runs on the Scan",       lambda: "_autofill" in APP and "_known_world" in APP),
 (25, "session earnings wired + UI",         lambda: "SV.Earnings" in APP and "drain_runs" in APP and "open_earnings" in DEFS),
 (26, "concept HUD",                         lambda: all(k in OV for k in ("rounded_frame","readout_rows","value_bars"))),
 (27, "credits on the map",                  lambda: "deposit_value" in PV and "deposit_value" in OV),
 (28, "drive route numbered",                lambda: "drive_route" in PV and "drive_route" in OV),
 (29, "another tool's CSV import",           lambda: wired("import_finds") and "detect_import_format" in DEFS),
 (30, "/v1/sites returns status+uploader",   lambda: "AS uploader" in SRV and "AS status" in SRV),
 (31, "/v1/deposits has worked_out",         lambda: "depleted" in SRV),
 (32, "system is a prefix match",            lambda: "prefix_pattern" in SRV),
 (33, "proximity search",                    lambda: "near_clause" in SRV and "systems" in SRV),
 (34, "site roll-up has a LIMIT",            lambda: "LIMIT ?" in SRV),
 (35, "commodity filter uses an index",      lambda: "EXISTS (SELECT 1 FROM deposits t" in SRV),
 (37, "best sell prices",                    lambda: "/v1/sell" in SRV and "def sell" in EDO),
 (38, "auto-updater",                        lambda: wired("check_updates") and "self.updates.check(" in APP),
 ("38a","update downloads itself, checked",  lambda: wired("fetch_update") and wired("update_downloaded")
        and "def download_verified" in EDO and "sha256" in src("build/site.py")),
 ("38b","one click installs it",             lambda: wired("install_update") and wired("update_button_pressed")
        and "skipifnotsilent" in src("build/installer.iss")),
 (39, "one-command version bump",            lambda: os.path.exists("build/bump.py")),
 (40, "website list from CHANGELOG",         lambda: os.path.exists("build/site.py")),
 (41, "installer keeps user data",           lambda: "AppId" in src("build/installer.iss")),
 (44, "repo scaffolding present",            lambda: all(os.path.exists(f) for f in
        (".gitignore","CONTRIBUTING.md","SECURITY.md",".github/ISSUE_TEMPLATE/bug_report.yml"))),
 (45, "VirusTotal position stated",          lambda: "VirusTotal" in src("SECURITY.md")),
 (48, "EDCD writeup exists",                 lambda: os.path.exists("docs/SURFACE-MINING-JOURNAL.md")),
 (49, "landing page exists",                 lambda: os.path.exists("site/edsmt.html")),
 (50, "where to land, ranked and live",     lambda: wired("open_land") and "SV.rank_bodies" in APP
        and wired("follow_land") and "def system_bodies" in JN and "/v1/grounds" in SRV),
 (51, "survey area: centre, border, swept %", lambda: wired("set_survey_centre") and wired("set_survey_border")
        and "AREA SWEPT" in OV),
 (52, "UPDATE a deposit's Amount in place",  lambda: wired("update_deposit_here") and "btn_update_deposit" in APP),
 (53, "other commanders' finds on the map",  lambda: wired("want_shared") and wired("take_shared")),
 (54, "rig down key, each rig, TOO FAR",      lambda: wired("drop_rigs") and wired("watch_rigs")
        and wired("sound_alarm") and "def _rig_banner" in OV and "TOO FAR FROM RIG" in OV and "def _rig_marks" in OV),
 # 1.10029
 (58, "keys Alt+1..Alt+6, one table",        lambda: '"hotkey_location": "ALT+1"' in OV and "WORK_KEYS" in APP
        and "KEYS_LEVEL = 4" in APP and wired("upgrade_hotkeys")),
 (59, "GUIDE box, step by step",             lambda: wired("guide_card") and "def draw_guide" in OV),
 (60, "rig down shows what it mines",        lambda: wired("rig_commodity") and "rigtype" in OV),
 (61, "Basic settings first",                lambda: '"Basic settings"' in APP and wired("save_and_restart")),
 (62, "ten or more themes, app and overlay", lambda: "PALETTES" in OV and wired("apply_app_theme")),
 (63, "tonnes mined per deposit",            lambda: wired("credit_refined") and "def credit_refined" in SV),
 (64, "cargo aboard, no double count",       lambda: "sessions-seen.json" in SV and wired("hold_now")),
 (65, "where to sell from here",             lambda: wired("quote_hold") and wired("take_quote")),
 (66, "Find paged, Last seen",               lambda: "last_seen" in SRV and "def last_seen" in APP),
 (67, "names from symbols (Eau)",            lambda: "def english_name" in SV and "hold_label" in JN),
 (68, "targeted signal picked",              lambda: wired("follow_target") and "#index=" in JN),
 (69, "scope is the signal you are at",      lambda: wired("follow_arrival") and "near_m=PV.SIGNAL_REACH_M" in OV
        and "SIGNAL_AT_M" in PV),
 (70, "key boxes hidden with Show",          lambda: wired("reveal") and wired("hide_secrets") and "REVEAL_S" in APP),
 (71, "My sites",                            lambda: wired("open_sites") and "class SitesWindow" in APP
        and "def sites(self)" in SV),
 (72, "UK English enforced",                 lambda: os.path.exists("tests/test_spelling.py")),
 (73, "share a find, distance from centre",  lambda: wired("copy_selected") and wired("paste_shared")
        and wired("take_share_lines") and wired("from_centre")),
 (74, "CI green on a small runner",          lambda: "Set-DisplayResolution" in src(".github/workflows/build.yml")),
 (75, "scope labels never overlap",          lambda: "def free_spot" in OV and "def _scope_labels" in OV),
 (76, "no empty sideways scrollbar",         lambda: "grid_forget()" in APP and "place_forget()" in APP),
 (77, "deposit you drive onto is picked",    lambda: wired("follow_deposit") and "self.follow_deposit(state)" in APP),
 (78, "guide to a picked deposit",           lambda: wired("guide_to") and "_target_id" in OV and '"GO"' in OV),
 (79, "own tonnes, cycles, holds and left",  lambda: wired("tonnes_lines") and "def close_cycle" in SV
        and '"cycles"' in SV),
 (80, "tonnes shown when the laser pauses",  lambda: wired("show_tonnes") and "TONNES_QUIET_S" in APP),
 (81, "border before centre kept",           lambda: wired("_border_after_centre")),
 (82, "Where to land Carrying filter",       lambda: wired("land_carrying") and '"carries"' in SV),
 (83, "clipboard survives closing",          lambda: wired("put_on_clipboard") and "CF_UNICODETEXT" in APP),
 (85, "worked-out age shown",                lambda: wired("worked_out_age")),
 # journal rules
 ("J1","sticky EOF handled",                 lambda: "seek" in JN and "SEEK_END" in JN),
 ("J2","no mtime gate on Status.json",       lambda: "st_mtime" not in JN.split("def _read_status")[1][:900] if "def _read_status" in JN else True),
 ("J3","torn lines held back",               lambda: "partial" in JN or "_tail" in JN),
 ("J4","Continued rollover",                 lambda: "Continued" in JN),
]
fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

print("== every numbered requirement is reachable in the code ==")
for num, claim, test in CHECKS:
    try:
        ok, why = bool(test()), ""
    except Exception as exc:
        ok, why = False, "check raised %s" % exc
    check("#%s  %s" % (num, claim), ok, why or "not found in the source")

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
