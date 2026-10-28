"""1.10038: Earnings in four pages, and short "Why" cells.

Asked on 28 Oct: "the tabs for earning and other areas feel cluttered and
filters should actually match what the tabs are."

- Earnings is four pages - This session, Where to sell, Sessions, System
  prices - and each shows only its own controls. The session's numbers are
  stat cards, its controls sit with it, and the page is remembered.
- Where to land and Powerplay say "Why" in a few words; the whole sentence
  is the cell's tooltip and what Copy copies.
- Powerplay's four filters are on "Where it counts" only.

Pure parts run anywhere; the windows on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110038_earnings.py
"""
import os, sys, json, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-earn38-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import survey as S       # noqa: E402
import powerplay as PW   # noqa: E402

fails = []
# A short phrase: what fits in a cell without making the row tall.
SHORT_WORDS = 6


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
            traceback.print_exc(limit=6)
        return fn
    return wrap


def words(text):
    return len(str(text or "").split())


# ---------------------------------------------------------------------------
# Where to land: one body for each kind of verdict.
SYSTEM = "Col 285 Sector ZL-K b22-2"
BODIES = [
    {"body": SYSTEM + " A 1", "landable": True, "distance_ls": 400.0,
     "planet_class": S.ROCKY, "locations": 4, "mapped": True},
    {"body": SYSTEM + " A 2", "landable": True, "distance_ls": 90.0,
     "planet_class": S.HMC, "locations": 0, "mapped": False},
    {"body": SYSTEM + " A 3", "landable": True, "distance_ls": 1800.0,
     "planet_class": S.ICY, "locations": 0, "mapped": True},
    {"body": SYSTEM + " A 4", "landable": False, "distance_ls": 60.0,
     "planet_class": "Water world", "locations": 0, "mapped": False},
    {"body": SYSTEM + " A 5", "landable": True, "distance_ls": 3000.0,
     "planet_class": S.ROCKY, "locations": 3, "mapped": True},
    {"body": SYSTEM + " A 6", "landable": True, "distance_ls": 3100.0,
     "planet_class": S.ROCKY, "locations": 1, "mapped": True},
    {"body": SYSTEM + " A 7", "landable": True, "distance_ls": 3200.0,
     "planet_class": S.ROCKY, "locations": 1, "mapped": True},
]
SITES = [
    # A 1: one intact site, three more locations nobody has shared.
    {"system": SYSTEM, "planet": SYSTEM + " A 1", "spot": "1", "rigs": 6,
     "types": ["Monazite"], "worked_out": False, "status": "verified"},
    # A 6: every known site worked out.
    {"system": SYSTEM, "planet": SYSTEM + " A 6", "spot": "1", "rigs": 3,
     "types": ["Ruby"], "worked_out": True, "status": "reported"},
    # A 7: intact, nothing more to find.
    {"system": SYSTEM, "planet": SYSTEM + " A 7", "spot": "1", "rigs": 4,
     "types": ["Ruby"], "worked_out": False, "status": "reported"},
]
LAND = {r["short"]: r for r in S.rank_bodies(SYSTEM, BODIES, None, SITES, {}, [], [], {},
                                             landable_only=False)}


@section("Where to land: Why is a short phrase; the sentence is kept")
def _land_why():
    expect = {"A 1": ("1 intact", "unshared"), "A 2": ("Not mapped",),
              "A 3": ("no locations",), "A 4": ("Not landable",),
              "A 5": ("3 locations",), "A 6": ("worked out",), "A 7": ("1 intact",)}
    for short, bits in expect.items():
        row = LAND[short]
        check("%s: a short phrase of at most %d words - %r" % (short, SHORT_WORDS, row.get("why")),
              0 < words(row.get("why")) <= SHORT_WORDS
              and all(b in row["why"] for b in bits), row.get("why"))
        check("%s: and the full sentence is still the note, never shorter than the phrase" % short,
              words(row["note"]) >= words(row["why"]) and row["note"].endswith("."), row["note"])
    check("the sentence is unchanged: a DSS map is what an unmapped body needs",
          "DSS" in LAND["A 2"]["note"] and "no mining" in LAND["A 3"]["note"])


# ---------------------------------------------------------------------------
# Powerplay: a made-up pledge and the systems round it, one per verdict.
POWER, RIVAL = "Nakato Kaine", "Zemina Torval"
PLACES = {
    "Kaine Hold": ((0.0, 0.0, 0.0), POWER, "Stronghold"),
    "Kaine Fort": ((100.0, 0.0, 0.0), POWER, "Fortified"),
    "Kaine Mine": ((0.0, 50.0, 0.0), POWER, "Exploited"),
    "Open Near": ((24.0, 0.0, 0.0), "", "Unoccupied"),
    "Open Far": ((0.0, 0.0, 40.0), "", "Unoccupied"),
    "Open Nowhere": (None, "", "Unoccupied"),
    "Torval Near": ((0.0, 0.0, -12.0), RIVAL, "Exploited"),
    "Torval Far": ((0.0, 0.0, -300.0), RIVAL, "Fortified"),
    "Quiet Rock": ((5.0, 5.0, 5.0), "", ""),
}


def power_book(pledged=True):
    book = PW.PowerBook()
    if pledged:
        book.observe(PW.pledge_note({"event": "Powerplay", "Power": POWER, "Rank": 50,
                                     "Merits": 1000, "timestamp": "2026-10-28T10:00:00Z"}))
    for n, (name, (pos, power, state)) in enumerate(sorted(PLACES.items())):
        event = {"timestamp": "2026-10-28T10:%02d:00Z" % (n + 1), "event": "FSDJump",
                 "StarSystem": name, "SystemAddress": 9000 + n,
                 "PowerplayState": state, "Powers": [power] if power else [POWER, RIVAL]}
        if pos is not None:
            event["StarPos"] = list(pos)
        if power:
            event["ControllingPower"] = power
        book.observe(PW.system_note(event))
    return book


BOOK = power_book()
VERDICTS = [
    ("no pledge", power_book(False).verdict("Kaine Hold", "Kaine Hold"), ("pledge",)),
    ("a system not in the record", BOOK.verdict("Kaine Hold", "Somewhere New"), ("record",)),
    ("goods from a system not in the record", BOOK.verdict("Nowhere", "Kaine Hold"),
     ("record",)),
    ("no Powerplay state", BOOK.verdict("Quiet Rock", "Quiet Rock"), ("state",)),
    ("Reinforce", BOOK.verdict("Kaine Hold", "Kaine Hold"), ("your Power", "Stronghold")),
    ("Undermine in range", BOOK.verdict("Torval Near", "Torval Near"), ("Rival", "reach")),
    ("Undermine with the range rule off", BOOK.verdict("Torval Far", "Torval Far", False),
     ("Rival", "rule off")),
    ("a rival out of range", BOOK.verdict("Torval Far", "Torval Far"), ("Rival", "out of")),
    ("mined and sold unoccupied", BOOK.verdict("Open Near", "Open Near"), ("Unoccupied",)),
    ("expanding from an Exploited system", BOOK.verdict("Kaine Mine", "Open Near"),
     ("Stronghold or Fortified",)),
    ("no position to measure", BOOK.verdict("Kaine Hold", "Open Nowhere"), ("position",)),
    ("Expand", BOOK.verdict("Kaine Hold", "Open Near"), ("24.0 Ly", "30 Ly")),
    ("too far to expand", BOOK.verdict("Kaine Hold", "Open Far"), ("40.0 Ly", "beyond")),
    ("sold away from where it was mined", BOOK.verdict("Kaine Hold", "Kaine Fort"),
     ("where it was mined",)),
]


@section("Powerplay: every verdict has a short phrase beside its sentence")
def _power_brief():
    seen = set()
    for label, verdict, bits in VERDICTS:
        brief = verdict.get("brief")
        check("%s: %r, at most %d words" % (label, brief, SHORT_WORDS),
              0 < words(brief) <= SHORT_WORDS and all(b in brief for b in bits)
              and words(verdict["why"]) > words(brief), (brief, verdict["why"]))
        seen.add(brief)
    check("each verdict says something of its own", len(seen) == len(VERDICTS), sorted(seen))
    rows = PW.system_rows(BOOK, "Kaine Hold", (0.0, 0.0, 0.0))
    check("the system list carries the phrase and the sentence, row by row",
          rows and all(r["brief"] == BOOK.verdict("Kaine Hold", r["system"])["brief"]
                       and r["why"] == BOOK.verdict("Kaine Hold", r["system"])["why"]
                       for r in rows), rows[:2])


# ---------------------------------------------------------------------------
# The windows, on the real toolkit. Nothing leaves the machine: every
# network connection is refused before the app is made.
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  the windows need a display (%s). Run it under xvfb-run." % _exc)
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    raise SystemExit(1 if fails else 0)

import socket            # noqa: E402


def _refuse(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise OSError("this check runs offline")
    return _real_connect(self, address)


_real_connect = socket.socket.connect
socket.socket.connect = _refuse
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))

import overlay as OV     # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A        # noqa: E402
import survey as SV      # noqa: E402
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS}, _f)
app = A.EDSMT()
app.geometry("1600x1000+0+0")
app.updates.check = lambda *args, **kwargs: None


def pump(times=4):
    for _ in range(times):
        app.update_idletasks()
        app.update()


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


def labels_in(widget):
    return [w for w in walk(widget) if isinstance(w, tkinter.Label)]


def text_of(widget):
    try:
        return str(widget.cget("text"))
    except Exception:
        return ""


def shown(widget):
    """On screen: mapped, and every frame it sits in mapped too."""
    try:
        return bool(widget.winfo_viewable())
    except Exception:
        return False


pump()


@section("Where to land: the short phrase on screen, the sentence on hover and in Copy")
def _land_window():
    rows = S.rank_bodies(SYSTEM, BODIES, None, SITES, {}, [], [], {})
    app.watcher.system = SYSTEM
    app.land_rows = lambda system, landable_only=True: [dict(r) for r in rows]
    lander = app.open_land()
    lander._paint()
    pump(6)
    top = lander._rows[0]
    cells = {text_of(w): w for w in labels_in(lander.table)}
    check("the Why cell shows the few words", top["why"] in cells, sorted(cells)[:12])
    check("not the sentence", top["note"] not in cells)
    cell = cells.get(top["why"])
    check("the sentence is the cell's tooltip",
          getattr(cell, "_edsmt_tip", None) == top["note"], getattr(cell, "_edsmt_tip", None))
    app.settings["show_tips"] = False
    try:
        cell._edsmt_tooltip._show()
        check("and it shows with tips switched off - it is the table's content, not a "
              "note on a control", cell._edsmt_tooltip._win is not None)
        cell._edsmt_tooltip._hide()
        button = next(w for w in walk(lander) if text_of(w) == "Copy all")
        button._edsmt_tooltip._show()
        check("while a control's note still stays hidden with tips off",
              button._edsmt_tooltip._win is None)
    finally:
        app.settings["show_tips"] = True
    copied = dict((what, text) for _label, what, text in lander._copies(top))
    check("Copy on the row takes the whole sentence", top["note"] in copied.get("this body", ""),
          copied)
    check("and so does Copy all", top["note"] in lander.as_text(), lander.as_text()[:200])
    lander.destroy()
    pump()
    del app.land_rows


@section("Powerplay: the short phrase on screen, the sentence on hover and in Copy")
def _power_window():
    app.powerbook = power_book()
    app.watcher.system = "Kaine Hold"
    win = app.open_powerplay()
    pump(4)
    win.show_page(0)
    pump(4)
    rows = PW.system_rows(app.powerbook, win.app.power_view(None, None)["origin"], None)
    expand = next(r for r in rows if r["system"] == "Open Near")
    cells = [w for w in labels_in(win.count_grid.table) if text_of(w) == expand["brief"]]
    check("the Why cell shows the few words: %r" % expand["brief"], len(cells) == 1,
          [text_of(w) for w in labels_in(win.count_grid.table)][:16])
    check("not the sentence", not any(text_of(w) == expand["why"]
                                      for w in labels_in(win.count_grid.table)))
    check("the sentence is the cell's tooltip",
          cells and getattr(cells[0], "_edsmt_tip", None) == expand["why"])
    line = next(A.GridTable.line_of(c) for c in win.count_grid.rows if c[0][0] == "Open Near")
    check("Copy on the row takes the whole sentence", expand["why"] in line, line)
    check("and so does Copy all", expand["why"] in win.count_grid.as_text())


@section("Powerplay: its four filters are on Where it counts, and only there")
def _power_filters():
    win = app.power_window
    boxes = [w for w in walk(win) if isinstance(w, A.ctk.CTkCheckBox)
             and text_of(w) in ("Undermine needs range", "Only where it counts")]
    filters = [win.mined_box, win.sell_box] + boxes
    check("Mined in, Selling in, Undermine needs range and Only where it counts",
          len(filters) == 4, [text_of(b) for b in boxes])
    win.show_page(0)
    pump(4)
    check("all four are on screen on Where it counts", all(shown(w) for w in filters),
          [shown(w) for w in filters])
    win.show_page(1)
    pump(4)
    check("none of them on Where to sell", not any(shown(w) for w in filters),
          [shown(w) for w in filters])
    check("where its own Order is", shown(win.order_box))
    win.destroy()
    pump()


# ---------------------------------------------------------------------------
PAGES = ("This session", "Where to sell", "Sessions", "System prices")


def page_widgets(win):
    """What belongs to each Earnings page, and nowhere else."""
    return {
        "This session": [box for box, _value in win.cards.values()]
        + [win.holding, win.session_note, win.start_button, win.pause_button,
           win.end_button, win.multi_box, win.session_copy],
        "Where to sell": [win.sell_title, win.sell_within, win.check_button,
                          win.sell_scroller],
        "Sessions": [win.scroller, win.summary, win.refresh_button, win.sessions_copy],
        "System prices": [win.system_box, win.system_pick, win.best_box,
                          win.search_button, win.prices_copy, win.scroller],
    }


def stamp(ago_s=0.0):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ago_s))


@section("Earnings: four pages, and each shows only its own")
def _pages():
    app.settings.pop("earnings_page", None)
    win = app.open_earnings()
    pump(6)
    check("This session, Where to sell, Sessions, System prices - in that order",
          tuple(win.page_buttons) == PAGES, tuple(getattr(win, "page_buttons", ())))
    check("a new commander starts on This session", win.page == "This session", win.page)
    groups = page_widgets(win)
    for page in PAGES:
        win.show_page(page)
        pump(4)
        mine = groups[page]
        others = [w for name, ws in groups.items() if name != page for w in ws
                  if w not in mine]
        check("%s: all of its own on screen" % page, all(shown(w) for w in mine),
              [(text_of(w) or type(w).__name__) for w in mine if not shown(w)])
        check("%s: nothing of the other pages" % page, not any(shown(w) for w in others),
              [(text_of(w) or type(w).__name__) for w in others if shown(w)])
        check("%s: its button is the one lit" % page,
              all((b.cget("fg_color") == A.BTN_PRIMARY["fg_color"]) == (name == page)
                  for name, b in win.page_buttons.items()))
        check("%s: the title, the one-line summary and the status line stay" % page,
              shown(win.current) and shown(win.status) and "\n" not in text_of(win.current))
    win.show_page("Sessions")
    pump(4)
    check("the status line on Sessions is about the sessions",
          "Rhino session" in text_of(win.status), text_of(win.status))
    win.show_page("This session")
    win.refresh()
    pump(4)
    check("and a table that is not on show says nothing on another page's status line",
          "Rhino session" not in text_of(win.status), text_of(win.status))
    check("the session controls are with the session: Start, Pause, End and Multi-session",
          [text_of(w) for w in (win.start_button, win.pause_button, win.end_button)]
          == ["Start session", "Pause", "End session"]
          and "Multi-session" in text_of(win.multi_box))
    win.show_page("Where to sell")
    pump(4)
    check("Check prices is Where to sell's one primary action",
          win.check_button.cget("fg_color") == A.BTN_PRIMARY["fg_color"])
    # The price check the window runs by itself when something is aboard
    # is Where to sell's news: on This session it said "Asking for the
    # best price..." over the session, and kept saying it.
    app.quote_hold = lambda radius: (2, "")
    app.quote_asked = {"system": "Ega", "radius": 100, "at": time.time()}
    try:
        win.show_page("This session")
        win.check_prices(quiet=True)
        pump(2)
        check("a price check made on This session says nothing on its status line",
              text_of(win.status) == "", text_of(win.status))
        win.show_page("Where to sell")
        win.check_prices(quiet=True)
        pump(2)
        check("and on Where to sell it says what it is asking for",
              text_of(win.status).startswith("Asking for the best price for 2 commodities"),
              text_of(win.status))
    finally:
        del app.quote_hold, app.quote_asked
    win.destroy()
    pump()


@section("Earnings: the page is remembered")
def _remembered():
    win = app.open_earnings()
    pump(4)
    win.show_page("Sessions")
    pump(2)
    with open(A.SETTINGS_FILE, encoding="utf-8") as handle:
        saved = json.load(handle)
    check("the page picked is kept in the settings, and on disk",
          app.settings.get("earnings_page") == "Sessions"
          and saved.get("earnings_page") == "Sessions", saved.get("earnings_page"))
    win.destroy()
    pump()
    win = app.open_earnings()
    pump(4)
    check("opened again, it is on that page", win.page == "Sessions" and shown(win.scroller)
          and not shown(win.start_button), win.page)
    win.destroy()
    pump()
    app.settings["earnings_page"] = "Rhino sessions"
    win = app.open_earnings()
    pump(4)
    check("a page it does not know opens This session", win.page == "This session", win.page)
    check("a new settings file starts on This session",
          A.DEFAULT_SETTINGS.get("earnings_page") == "This session")
    win.destroy()
    pump()


@section("Earnings: a system search lands on System prices; Copy all copies the page's table")
def _prices():
    win = app.open_earnings()
    pump(4)
    win.show_page("This session")
    win._system_asked = {"system": "Wyrd", "picked": [], "at": time.time()}
    win.system_results(True, json.dumps({"system": "Wyrd", "upstream_status": "live", "prices": [
        {"commodity": "Monazite", "station": "Black Hide", "station_type": "CraterOutpost",
         "pad": 2, "sell": 120500, "demand": 40, "seen": SV.utc_now(), "source": "community"}]}))
    pump(4)
    check("the answer opens System prices", win.page == "System prices"
          and shown(win.search_button) and win._view == "prices", win.page)
    win.prices_copy.invoke()
    pump(2)
    check("its Copy all copies the prices", app.clipboard_get().startswith("Wyrd - last known prices"),
          app.clipboard_get()[:60])
    win.show_view("sessions")
    pump(4)
    check("show_view('sessions') is the Sessions page", win.page == "Sessions"
          and win._view == "sessions")
    row = app.earnings.start("Ega", "Ega 1", "CMDR X", when=stamp(3600))
    row.update({"mined": "Iridium:12", "closed": stamp(60), "ended": stamp(60)})
    app.earnings.save()
    win.refresh_button.invoke()
    pump(4)
    win.sessions_copy.invoke()
    pump(2)
    check("and its Copy all copies the sessions",
          app.clipboard_get().startswith(" | ".join(A.RUN_HEADERS)), app.clipboard_get()[:60])
    win.destroy()
    pump()


@section("This session: the numbers are stat cards, and they keep up")
def _cards():
    app.settings["earnings_page"] = "This session"
    run = app.earnings.start("Ega", "Ega 1", "CMDR X", when=stamp(2 * 3600))
    run["mined"] = "Iridium:120"
    app.extras._row(run["id"])["merits"] = 1234
    est = {"hours": 2.0, "tonnes": 120, "t_hr": 60.0, "earned": 0.0, "value": 23344800.0,
           "cr_hr": 11672400.0, "merits_hr": 2076.4, "lines": [], "kinds": {"market"}}
    app.session_estimate = lambda _run: dict(est)
    try:
        win = app.open_earnings()
        pump(6)
        check("seven cards: Time, Mined, t/hr, Est. value, Cr/hr, Merits earned, Merits/hr",
              tuple(win.cards) == ("Time", "Mined", "t/hr", "Est. value", "Cr/hr",
                                   "Merits earned", "Merits/hr"), tuple(win.cards))
        values = {name: text_of(value) for name, (_box, value) in win.cards.items()}
        check("each says its number", values == {
            "Time": "2h 00m", "Mined": "120 t", "t/hr": "60.0", "Est. value": "23,344,800 Cr",
            "Cr/hr": "11,672,400", "Merits earned": "1,234", "Merits/hr": "~2,076"}, values)
        check("the summary line says which session, and what is sold so far",
              text_of(win.current).startswith("CURRENT SESSION")
              and "sold so far 0 Cr" in text_of(win.current), text_of(win.current))
        check("under the cards, one line on what the value rests on",
              "best price seen in the last day" in text_of(win.session_note)
              and "\n" not in text_of(win.session_note), text_of(win.session_note))
        check("the merits cards explain themselves on hover",
              getattr(win.cards["Merits/hr"][0], "_edsmt_tip", "") == A.MERITS_TIP)
        win.session_copy.invoke()
        pump(2)
        copied = app.clipboard_get()
        check("Copy on This session puts the session on the clipboard as text",
              copied.startswith("CURRENT SESSION   2h 00m   120 t mined")
              and "Estimated 23,344,800 Cr" in copied
              and "Powerplay merits earned: 1,234" in copied, copied)
        est.update(hours=3.0, tonnes=180, value=30000000.0, merits_hr=None)
        app.extras._row(run["id"])["merits"] = 0
        win.live()
        pump(2)
        values = {name: text_of(value) for name, (_box, value) in win.cards.items()}
        check("left open, the cards move with the session",
              values["Time"] == "3h 00m" and values["Mined"] == "180 t"
              and values["Est. value"] == "30,000,000 Cr", values)
        check("no merits yet, and no rate learnt, say so",
              values["Merits earned"] == "none yet" and values["Merits/hr"] == A.CARD_NONE,
              values)
        app.geometry("1600x1000")
        pump(6)
        tops = {box.winfo_y() for box, _v in win.cards.values()}
        check("on a wide window the cards are one row", len(tops) == 1, tops)
        app.geometry("900x700")
        pump(10)
        right = win.winfo_rootx() + win.winfo_width()
        tops = {box.winfo_y() for box, _v in win.cards.values()}
        check("on a narrow one they wrap into rows, every card inside the window",
              len(tops) > 1 and all(box.winfo_rootx() + box.winfo_width() <= right + 1
                                    for box, _v in win.cards.values()), (tops, right))
        wraps = [int(float(label.cget("wraplength"))) for label in (win.holding, win.session_note)]
        check("and the hold line and the note under the cards wrap inside it, not off the edge",
              all(0 < wrap <= win.winfo_width() for wrap in wraps), (wraps, win.winfo_width()))
        app.geometry("1600x1000")
        pump(4)
        app.earnings.finish()
        win.refresh()
        pump(2)
        check("with no session open, the last one is shown, and says so",
              text_of(win.current).startswith("LAST SESSION"), text_of(win.current))
        win.destroy()
        pump()
    finally:
        del app.session_estimate


@section("Earnings in a window of its own: the same pages")
def _windowed():
    app.settings["tools_as_tabs"] = False
    try:
        win = app.open_earnings()
        pump(6)
        check("it opens as a window", not win.docked)
        win.show_page("System prices")
        pump(4)
        check("and its pages work the same way", shown(win.search_button)
              and not shown(win.start_button))
        win.destroy()
        pump()
    finally:
        app.settings["tools_as_tabs"] = True


if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
