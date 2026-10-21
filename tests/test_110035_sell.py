"""1.10035: one stop for the whole hold, selling within N jumps, and which
way a station's price and demand are moving.

The rules are checked as plain functions first (sellplan.py), then the
journal reader's jump range, then the app and the Earnings window on the
real toolkit. Every station and system here is made up.

    python tests/test_110035_sell.py
"""
import os, sys, json, time, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-sell-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import sellplan as SP    # noqa: E402
import journal as JN     # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=4)
        return fn
    return wrap


NOW = time.time()


def stamp(ago_s=0):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW - ago_s))


def row(station, system, sell, demand, ly, ago=600, kind="Coriolis Starport", stale=False):
    return {"station": station, "system": system, "sell": sell, "demand": demand,
            "distance_ly": ly, "seen": stamp(ago), "age_s": ago, "stale": stale,
            "station_type": kind}


HOLD = {"Iridium": 239, "Osmium": 67, "Platinum": 47, "Samarium": 44}
PRICES = {
    "Iridium": [row("Oriole Port", "Vela Nine", 824191, 15352, 189.6, ago=3 * 3600),
                row("Hayden Hub", "Agni Two", 845000, 9000, 211.9),
                row("K7Q-1HT", "Vela Nine", 990000, 99999, 189.6, kind="Fleet Carrier"),
                row("Old Dock", "Rust", 999999, 99999, 20.0, ago=3 * 86400, stale=True),
                row("Far Away", "Remote", 950000, 99999, 300.0)],
    "Osmium": [row("Oriole Port", "Vela Nine", 273000, 256159, 189.6, ago=4 * 3600)],
    "Platinum": [row("Oriole Port", "Vela Nine", 200000, 20, 189.6)],
    "Samarium": [],
}


@section("sellplan: jumps, and the distance a number of jumps covers")
def _jumps():
    check("the same system is no jumps", SP.jumps_for(0, 20) == 0)
    check("20 Ly at 20 a jump is one", SP.jumps_for(20, 20) == 1)
    check("20.1 Ly at 20 a jump is two", SP.jumps_for(20.1, 20) == 2)
    check("unknown distance or range: no answer",
          SP.jumps_for(None, 20) is None and SP.jumps_for(50, 0) is None)
    check("4 jumps at the ship's 42.7 Ly is 170.8 Ly, not a guess",
          SP.radius_for("4 jumps", 42.7) == (170.8, 42.7, False), SP.radius_for("4 jumps", 42.7))
    check("with no range known it says it is guessing at 20 Ly a jump",
          SP.radius_for("2 jumps", None) == (40.0, 20.0, True))
    check("a distance in light years is not a jump choice", SP.radius_for("100 Ly", 30) is None)


@section("sellplan: the one station that takes the most of the hold")
def _one_stop():
    found = SP.whole_hold(HOLD, PRICES.get, within_ly=250)
    names = [s["station"] for s in found]
    check("best first: the station buying three of the four", names[:2] == ["Oriole Port", "Hayden Hub"], names)
    check("no fleet carriers, no stale price, nothing beyond the distance",
          not {"K7Q-1HT", "Old Dock", "Far Away"} & set(names), names)
    best = found[0]
    check("demand is a cap: 20 t of the Platinum, not 47",
          [p["tonnes"] for p in best["parts"] if p["commodity"] == "Platinum"] == [20], best["parts"])
    check("it takes 326 of 397 t and says what it does not buy",
          best["tonnes"] == 239 + 67 + 20 and best["of"] == 397 and best["missing"] == ["Samarium"],
          (best["tonnes"], best["of"], best["missing"]))
    check("the total is what it would pay",
          best["total"] == 239 * 824191 + 67 * 273000 + 20 * 200000, best["total"])
    check("its oldest price is the Osmium, 4 hours", abs(best["oldest_s"] - 4 * 3600) < 1, best["oldest_s"])
    everywhere = SP.whole_hold(HOLD, PRICES.get, within_ly=None, top=0)
    check("with no distance limit the far market counts too",
          "Far Away" in [s["station"] for s in everywhere])
    carriers = SP.whole_hold(HOLD, PRICES.get, no_carriers=False, top=0)
    check("carriers can be let back in", "K7Q-1HT" in [s["station"] for s in carriers])
    check("nothing aboard, nothing to say", SP.whole_hold({}, PRICES.get) == [])
    unknown = SP.whole_hold({"Gold": 10}, lambda n: [dict(row("A", "B", 50000, None, 5))])
    check("demand not given: the whole load counts", unknown[0]["tonnes"] == 10, unknown)


@section("sellplan: which way a price and its demand are moving")
def _trends():
    book = SP.Trends()
    first = row("Oriole Port", "Vela Nine", 845417, 16234, 189.6, ago=5280 + 600)
    later = row("Oriole Port", "Vela Nine", 824191, 15352, 189.6, ago=600)
    check("one reading is not a trend", book.note([first], "Iridium") == 1
          and book.trend(first, "Iridium") is None)
    check("the same reading again is not new", book.note([dict(first)], "Iridium") == 0)
    book.note([later], "Iridium")
    moved = book.trend(later, "Iridium")
    check("two readings 1 h 28 min apart make a trend",
          moved and moved["price_from"] == 845417 and moved["price_to"] == 824191
          and moved["demand_from"] == 16234 and abs(moved["span_s"] - 5280) < 2, moved)
    words = SP.trend_words(moved)
    check("said the way a commander reads it",
          "demand 16,234 → 15,352" in words and "price 845,417 → 824,191" in words
          and words.endswith("in 1 h 28 min"), words)
    check("an older reading than the newest is ignored", book.note([first], "Iridium") == 0)
    stale = SP.Trends()
    stale.note([row("X", "Y", 100, 5, 1, ago=3 * 86400)], "Gold")
    stale.note([row("X", "Y", 120, 5, 1, ago=60)], "Gold")
    check("a reading more than a day older is history, not a trend",
          stale.trend(row("X", "Y", 120, 5, 1, ago=60), "Gold") is None)
    folder = os.path.join(TMP, "trends")
    keep = SP.Trends(folder)
    keep.note([first, later], "Iridium")
    check("kept on disk", keep.save() and SP.Trends(folder).trend(later, "Iridium") is not None)
    found = SP.whole_hold({"Iridium": 239}, lambda n: [later], trends=book)
    check("the one-stop answer carries the trend of each commodity",
          found[0]["parts"][0]["trend"] == moved, found[0]["parts"][0])
    check("ages are said in words", SP.age_words(60) == "just now" and SP.age_words(1920) == "32 min"
          and SP.age_words(3 * 3600) == "3 h 00 min" and SP.age_words(None) == "age unknown")


@section("the reader keeps the ship's jump range from its Loadout")
def _reader():
    game = os.path.join(TMP, "game")
    os.makedirs(game)
    with open(os.path.join(game, "Journal.2026-10-20T120000.01.log"), "w", encoding="utf-8") as out:
        for event in ({"timestamp": stamp(60), "event": "Fileheader", "part": 1},
                      {"timestamp": stamp(50), "event": "Loadout", "Ship": "panthermkii",
                       "ShipID": 94, "CargoCapacity": 736, "MaxJumpRange": 42.739}):
            out.write(json.dumps(event) + "\n")
    reader = JN.JournalWatcher(game)
    reader.poll()
    check("MaxJumpRange is kept", reader.max_jump_ly == 42.74, reader.max_jump_ly)


# ---------------------------------------------------------------------------
HAVE_DISPLAY = True
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    HAVE_DISPLAY = False
    print("\n  SKIP  the toolkit half of this file - no display (%s). "
          "Run it under xvfb-run." % _exc)


def on_screen(title):
    def wrap(fn):
        if not HAVE_DISPLAY:
            print("== %s ==\n  SKIP  needs a display" % title)
            return fn
        return section(title)(fn)
    return wrap


if HAVE_DISPLAY:
    import overlay as OV    # noqa: E402
    OV.foreground_is_game = lambda: None
    import edsmt as A       # noqa: E402
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "journal_dir": JOURNALS}, _f)
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *args, **kwargs: None

    def pump(times=4):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    pump()


@on_screen("the app: jump range from Settings or the ship, and the hold split")
def _app():
    app.settings["jump_range_ly"] = 0
    app.watcher.max_jump_ly = 42.7
    check("no setting: the ship's own range", app.jump_range() == 42.7)
    app.settings["jump_range_ly"] = 30
    check("a setting wins over the ship", app.jump_range() == 30.0)
    app.settings["jump_range_ly"] = 0
    app.watcher.max_jump_ly = None
    check("neither: unknown", app.jump_range() is None)
    app.watcher.holds = {"Ship": {"Iridium": 239, "Osmium": 67, "Platinum": 47, "Samarium": 44},
                         "SRV": {"Iridium": 12}}
    check("ship and SRV tonnes apart", app.hold_split() == (397, 12), app.hold_split())
    app.sell_rows_for = lambda name: PRICES.get(name, [])
    found = app.one_stop(within_ly=250)
    check("the app's one stop is the same answer, SRV tonnes included",
          found and found[0]["station"] == "Oriole Port"
          and [p["tonnes"] for p in found[0]["parts"] if p["commodity"] == "Iridium"] == [251], found[:1])


@on_screen("Earnings: one stop for the whole hold, within N jumps")
def _window():
    app.watcher.max_jump_ly = 42.7
    win = app.open_earnings() or getattr(app, "earnings_window", None)
    pump(4)
    if win is None:
        win = [w for w in app.winfo_children() if isinstance(w, A.EarningsWindow)][0]
    values = list(win.sell_within.cget("values"))
    check("the distance box offers jumps as well as light years",
          all(v in values for v in ("1 jump", "2 jumps", "4 jumps", "8 jumps", "100 Ly")), values)
    win.sell_within.set("4 jumps")
    check("4 jumps at 42.7 Ly asks within 171 Ly", win._radius() == 171, win._radius())
    lines = win.one_stop_lines()
    text = "\n".join(t for t, _c in lines)
    check("it heads the answer with the reach", text.startswith("One stop for the whole hold - within 171 Ly")
          and "at 42.7 Ly a jump" in text, text[:200])
    check("the SRV tonnes are said apart and counted",
          "397 t in the ship + 12 t in the SRV" in text, text)
    win.sell_within.set("250 Ly")
    text = "\n".join(t for t, _c in win.one_stop_lines())
    check("#1 is the station that takes the most, with its jumps and its age",
          "#1" in text and "Oriole Port, Vela Nine (189.6 Ly, ~5 jumps)" in text
          and "takes 338 of 409 t" in text and "prices 4 h 00 min old" in text, text)
    check("each commodity's tonnes and price, the demand cap, and what it does not buy",
          "Platinum 20 t at" in text and "(demand 20 of your 47 t)" in text
          and "not bought there: Samarium" in text, text)
    app.watcher.max_jump_ly = None
    win.sell_within.set("2 jumps")
    text = "\n".join(t for t, _c in win.one_stop_lines())
    check("with no range known it says so and how to set it",
          "at 20 Ly a jump - set your own in Settings > Basics" in text, text[:300])
    app.sell_rows_for = lambda name: []
    text = "\n".join(t for t, _c in win.one_stop_lines())
    check("nothing priced: it says what to do", "No one station has a fresh price" in text, text)
    win.destroy()
    pump()


@on_screen("Settings: the jump range is a number of light years, or blank")
def _settings():
    win = A.SettingsWindow(app)
    pump(4)
    said, saved = [], []
    win.say = lambda text, colour=None: said.append(text)
    real_apply = app.apply_settings
    app.apply_settings = lambda data: saved.append(data)
    try:
        check("Basics has the box, with a tip", "jump_range_ly" in win.fields
              and "jump_range_ly" in A.SETTING_TIPS)
        for typed, ok, value in (("lots", False, None), ("200", False, None),
                                 ("42.7", True, 42.7), ("20 ly", True, 20), ("", True, 0)):
            win.fields["jump_range_ly"].delete(0, "end")
            win.fields["jump_range_ly"].insert(0, typed)
            before = len(saved)
            win.save()
            pump(2)
            check("a jump range of %r is %s" % (typed, "saved" if ok else "refused"),
                  (len(saved) > before) == ok and (not ok or saved[-1].get("jump_range_ly") == value)
                  and (ok or "light years a jump" in said[-1]), (said[-1:], saved[-1:]))
    finally:
        app.apply_settings = real_apply
        win.destroy()
        pump()


if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
