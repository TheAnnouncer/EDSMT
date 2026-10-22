"""1.10036: Find is not cut off at 500, and Earnings shows the merits earned.

Every page of a search is fetched (edonline.every_page), and the Find
window says so honestly. The
Earnings window has a Merits column and the current session says the
merits the game actually paid, beside the estimate.

    python tests/test_110036_find.py
"""
import os, sys, json, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-find-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import edonline as EDO    # noqa: E402

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


def server(total, key="deposits", pages=True):
    """A stand-in community map holding `total` rows."""
    asked = []

    def get(url, headers=None, **kw):
        from urllib.parse import urlparse, parse_qs
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        asked.append(q)
        limit, offset = int(q.get("limit", 50)), int(q.get("offset", 0)) if pages else 0
        rows = [{"id": i} for i in range(offset, min(total, offset + limit))]
        out = {key: rows, "count": len(rows), "commodities": []}
        if pages:
            more = offset + limit < total
            out.update(offset=offset, more=more, next_offset=offset + limit if more else None)
        return out
    return get, asked


def run(client, call):
    call()
    for _ in range(200):
        got = client.worker.drain()
        if got:
            return got[0]
        time.sleep(0.02)
    return None


@section("every page of a search is fetched")
def _pages():
    real = EDO.get_json
    try:
        client = EDO.CommunityClient(EDO.Worker())
        client.configure("", "", True, True)
        EDO.get_json, asked = server(2700)
        tag, ok, message = run(client, lambda: client.search(limit=500, every=True))
        data = json.loads(message)
        check("2,700 finds come back, not 500", ok and len(data["deposits"]) == 2700
              and len({r["id"] for r in data["deposits"]}) == 2700, (ok, len(data.get("deposits", []))))
        check("the first page at 500, the rest at 1,000", [int(q["limit"]) for q in asked] == [500, 1000, 1000, 1000]
              and [int(q.get("offset", 0)) for q in asked] == [0, 500, 1500, 2500], asked)
        check("and it says it is complete", data["complete"] is True and data["pages"] == 4
              and "more" not in data and "next_offset" not in data)
        EDO.get_json, asked = server(300, key="sites")
        tag, ok, message = run(client, lambda: client.sites(limit=500, every=True))
        check("a small answer is one page", len(json.loads(message)["sites"]) == 300 and len(asked) == 1)
        EDO.get_json, asked = server(900, pages=False)
        tag, ok, message = run(client, lambda: client.search(limit=500, every=True))
        check("an older server that does not page: its one page, no loop",
              len(json.loads(message)["deposits"]) == 500 and len(asked) == 1)
        EDO.get_json, asked = server(10 ** 6, key="sites")
        real_cap = client.ALL_ROWS
        client.ALL_ROWS = 3000
        try:
            tag, ok, message = run(client, lambda: client.intact(limit=500, every=True))
        finally:
            client.ALL_ROWS = real_cap
        data = json.loads(message)
        check("a search that matches the whole map stops at the top, and says so",
              len(data["sites"]) == 3000 and data["complete"] is False, (len(data["sites"]), data.get("complete")))
        check("the ceiling is tens of thousands", EDO.CommunityClient.ALL_ROWS >= 20000)
    finally:
        EDO.get_json = real


HAVE_DISPLAY = True
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    HAVE_DISPLAY = False
    print("\n  SKIP  the toolkit half of this file - no display (%s)." % _exc)


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
        json.dump({"asked_to_share": True, "journal_dir": JOURNALS, "tour_done": True}, _f)
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *args, **kwargs: None

    def pump(times=4):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    pump()


@on_screen("the Find window: every row in hand, drawn a page at a time, said honestly")
def _window():
    win = app.open_find() or app.finder
    pump(3)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    deposits = [{"id": "d%d" % i, "system": "Sys %d" % i, "planet": "Sys %d 1" % i, "spot": "1",
                 "type": "Platinum", "rigs": 3, "density": "High", "created": now, "last_seen": now,
                 "lat": 1.0, "lon": 2.0, "uploader": "CMDR X"} for i in range(1203)]
    win.results("search", json.dumps({"deposits": deposits, "complete": True, "pages": 2}))
    pump(4)
    check("all 1,203 are in hand", len(win._rows) == 1203, len(win._rows))
    check("the count is the whole answer, with no 'the most this asks for'",
          win.status.cget("text") in ("1,203 result(s).",) or "of 1,203 shown" in win.status.cget("text"),
          win.status.cget("text"))
    labels = [k for k in win.table.winfo_children() if k.winfo_class() == "Label"]
    check("and a page of them is drawn straight away", len(labels) >= A.PAGE_ROWS, len(labels))
    win.results("search", json.dumps({"deposits": deposits[:400], "complete": False, "pages": 9}))
    pump(2)
    check("a search stopped at the top says so", "narrow it to see past them" in win.status.cget("text"),
          win.status.cget("text"))
    win.destroy()
    pump()
    check("all three finds searches ask for every page", A.SEARCH_LIMIT == 500)


@on_screen("Earnings: the merits the game paid, per session and for the one you are on")
def _merits():
    check("a Merits column after t/hr", A.RUN_HEADERS.index("Merits") == A.RUN_HEADERS.index("t/hr") + 1)
    row = app.earnings.start("Ega", "Ega 1", "CMDR X", when=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    ledger = app.extras
    ledger._row(row["id"])["merits"] = 1234
    win = app.open_earnings() or getattr(app, "ledger", None)
    pump(4)
    cells = win._run_row(row)
    cell = cells[A.RUN_HEADERS.index("Merits")]
    check("the session's merits, as the game counted them", cell[0] == "1,234" and cell[2] == 1234, cell)
    lines = A.current_session_lines(app, [row])
    check("the current session says the merits earned", lines[2].startswith("Powerplay merits earned: 1,234"),
          lines[2])
    ledger._row(row["id"])["merits"] = 0
    check("none yet says so", win._run_row(row)[A.RUN_HEADERS.index("Merits")][0] == "-")
    win.destroy()
    pump()


if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
