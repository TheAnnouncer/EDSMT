"""1.10040: the big tables on the toolkit's own tree view, only the rows on
screen in it (#308).

Find, Sessions, My sites and Where to land were grids of labels - a thousand
rows ten thousand widgets, built again on every sort - and the label grid
is what let the scrollbar loop in 1.10037. They now sit on a tree view that
holds only the rows on screen. This checks the arithmetic, then times 2,000
rows drawn and scrolled against a budget, then each of the four windows.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_tables.py
"""
import faulthandler
import json
import os
import sys
import tempfile
import time

faulthandler.dump_traceback_later(240, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-tables-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import tableview as TV  # noqa: E402

fails = []

# The budgets. Measured in the cloud at about a tenth of each (2,000 rows
# shown in 0.06 s, 200 wheel steps in 1.2 s); on a Windows desktop, 5 Nov
# 2026: 200 wheel steps in 7.95 s, 100 drags in 4.04 s - Tk on Windows draws
# a tree view several times slower. The label grids this replaced took
# seconds for one redraw, so these still catch that.
SHOW_BUDGET_S = 1.0
SCROLL_BUDGET_S = 16.0         # 200 wheel steps, each drawn
DRAG_BUDGET_S = 8.0            # 100 scrollbar drags, each drawn
SORT_BUDGET_S = 1.0


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


print("== the arithmetic, with no display ==")
check("rows that fit under the headings, at least one",
      TV.visible_rows(500, 30, 20) == 23 and TV.visible_rows(10, 30, 20) == 1)
check("the first row on screen stays inside the rows there are",
      TV.clamp_offset(-5, 10, 100) == 0 and TV.clamp_offset(95, 10, 100) == 90
      and TV.clamp_offset(3, 10, 4) == 0)
check("the scrollbar says what share is on screen",
      TV.fractions(0, 10, 100) == (0.0, 0.1) and TV.fractions(90, 10, 100) == (0.9, 1.0)
      and TV.fractions(0, 10, 0) == (0.0, 1.0))
check("a drag to half way puts row 50 of 100 at the top",
      TV.offset_at(0.5, 10, 100) == 50 and TV.offset_at("x", 10, 100) == 0)
check("a unit is a row and a page is a screen less one",
      TV.scrolled(0, 3, "units", 10, 100) == 3 and TV.scrolled(0, 1, "pages", 10, 100) == 9
      and TV.scrolled(5, -9, "units", 10, 100) == 0)
check("moving the focus moves the view as little as it can",
      TV.into_view(12, 0, 10, 100) == 3 and TV.into_view(2, 5, 10, 100) == 2
      and TV.into_view(7, 5, 10, 100) == 5)
check("the rows on screen", list(TV.window(95, 10, 100)) == list(range(90, 100)))
roles = {"bad": "#r", "caution": "#a", "good": "#g"}
check("a row takes its strongest cell's colour: red, then amber, then green",
      TV.row_tone(["#g", "#a"], roles) == "caution" and TV.row_tone(["#g", "#R"], roles) == "bad"
      and TV.row_tone([None, "#g"], roles) == "good" and TV.row_tone([None, "#d"], roles) == "")
check("a cell's lines sit side by side on its one row",
      TV.one_line("57t: Iridium 57\nRhino A: 30t") == "57t: Iridium 57 · Rhino A: 30t"
      and TV.one_line(None) == "")
check("Copy takes each cell whole, on one line",
      TV.line_of(["a", "b\nc"]) == "a | b c"
      and TV.block_of(["H1", "H2"], [["a", "b"], ["c", "d"]]) == "H1 | H2\na | b\nc | d")
check("the columns are sized by the first rows and the longest further down",
      TV.sample(1000, [999, 5])[:3] == [0, 1, 2] and 999 in TV.sample(1000, [999])
      and len(TV.sample(1000, [999])) == TV.WIDTH_SAMPLE + 1)
check("a column is as wide as its widest text, within its limits",
      TV.column_width("Rigs", ["6", "12"], lambda t: 10 * len(t), least=30, most=200, pad=10) == 50
      and TV.column_width("H", ["x" * 100], lambda t: 10 * len(t), most=200) == 200)
check("a click picks one row; Ctrl adds or takes away; Shift picks a run",
      TV.picked_after({1}, 4, 1) == ({4}, 4)
      and TV.picked_after({1}, 4, 1, ctrl=True) == ({1, 4}, 4)
      and TV.picked_after({1, 4}, 4, 1, ctrl=True) == ({1}, 4)
      and TV.picked_after({1}, 4, 1, shift=True) == ({1, 2, 3, 4}, 1))

try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as exc:
    print("  SKIP  the rest needs a display (%s). Run it under xvfb-run." % exc)
    print()
    print("FAILURES:", len(fails))
    sys.exit(1 if fails else 0)

import overlay as OV  # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A     # noqa: E402

A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
               "welcome_seen_version": A.APP_VERSION, "find_unlocked": True}, handle)

app = A.EDSMT()
app.geometry("1400x900+0+0")
app.updates.check = lambda *args, **kwargs: None


def pump(seconds=0.3):
    until = time.time() + seconds
    while True:
        app.update_idletasks()
        app.update()
        if time.time() >= until:
            break
        time.sleep(0.01)


def settle_until(cond, seconds=5.0):
    """Wait for `cond`, up to a deadline - never a fixed number of loops."""
    until = time.time() + seconds
    while time.time() < until:
        if cond():
            return True
        pump(0.05)
    return bool(cond())


class Wheel:
    """A wheel notch down, as X sends it."""
    delta, num, state = 0, 5, 0


pump(1.0)

print("== 2,000 rows, drawn and scrolled, timed ==")
shell = A.ctk.CTkToplevel(app)
shell.geometry("1200x700+0+0")
copied, done = [], []
table = A.NativeTable(shell, copy=lambda what, text: copied.append((what, text)))
table.pack(fill="both", expand=True)
ROWS = [{"system": "Sys %04d" % i, "n": i} for i in range(2000)]


def cells(row):
    n = row["n"]
    return [(row["system"], A.GREEN if n % 3 == 0 else (A.AMBER if n % 3 == 1 else None)),
            ("{:,}".format(n * 1000), None, n),
            ("why %d" % n, A.DIM, n, "The whole sentence for row %d." % n),
            ("two\nlines", None)]


sorts = []
pump(0.5)
started = time.perf_counter()
table.show(["System", "Credits", "Why", "Notes"], ROWS, cells,
           actions=lambda row: [("system", lambda r=row: done.append(r["system"]), False),
                                ("delete", lambda: None, A.BTN_DANGER)],
           on_sort=sorts.append)
app.update_idletasks()
app.update()
took = time.perf_counter() - started
print("        shown in %.3f s" % took)
show_took = took
check("2,000 rows are shown within %.1f s" % SHOW_BUDGET_S, took < SHOW_BUDGET_S, "%.3f s" % took)
check("every row is in hand", table.row_count() == 2000, table.row_count())
pump(0.3)
items = len(table.tree.get_children())
check("but only the rows on screen are in the tree", 1 < items <= table._visible + 1 < 200,
      (items, table._visible))
check("the headings and the first rows are what is shown",
      table.texts()[:6] == ["System", "Credits", "Why", "Notes", "Sys 0000", "0"], table.texts()[:6])
check("a cell's two lines are on its one row", "two · lines" in table.texts())
check("the Why cell shows its short words, and keeps its sentence for the tip and Copy",
      table.cell_text(5, 2) == ("why 5", "The whole sentence for row 5."))
check("rows take their cells' colour: green good, amber caution",
      table.row_tone(0) == "good" and table.row_tone(1) == "caution" and table.row_tone(2) == "")
first = table.tree.get_children()[0]
check("and the row picked first wears the picked colour",
      "picked" in table.tree.item(first, "tags"), table.tree.item(first, "tags"))
started = time.perf_counter()
for _ in range(200):
    table.wheel(Wheel())
    app.update_idletasks()
    app.update()
took = time.perf_counter() - started
print("        200 wheel steps in %.3f s" % took)
check("200 wheel steps, each drawn, within %.1f s" % SCROLL_BUDGET_S, took < SCROLL_BUDGET_S,
      "%.3f s" % took)
low, high = table.yview()
check("and the view has moved 600 rows down", abs(low - 0.3) < 0.002, (low, high))
check("still only a screenful in the tree", len(table.tree.get_children()) <= table._visible + 1)
started = time.perf_counter()
for step in range(100):
    table.yview("moveto", step / 100.0)
    app.update_idletasks()
    app.update()
took = time.perf_counter() - started
print("        100 scrollbar drags in %.3f s" % took)
check("100 scrollbar drags, each drawn, within %.1f s" % DRAG_BUDGET_S, took < DRAG_BUDGET_S,
      "%.3f s" % took)
table.yview("moveto", 1.0)
pump(0.1)
check("dragged to the end, the last row is on screen", "Sys 1999" in table.texts(),
      table.texts()[-8:])
table.top()
pump(0.1)
check("top() is back at the first row", table.yview()[0] == 0.0 and "Sys 0000" in table.texts())

print("== headings, picking, the buttons, copying ==")
heading_command = table.tree.heading("c1", "command")
table.tree.tk.call(heading_command)
check("a click on a heading asks the window to sort on that column", sorts == [1], sorts)
started = time.perf_counter()
table.show(["System", "Credits", "Why", "Notes"], list(reversed(ROWS)), cells,
           sort=(1, True), on_sort=sorts.append)
app.update_idletasks()
took = time.perf_counter() - started
check("the window's sorted rows are shown again within %.1f s" % SORT_BUDGET_S,
      took < SORT_BUDGET_S, "%.3f s" % took)
check("with the heading saying which way", table.tree.heading("c1", "text") == "Credits v",
      table.tree.heading("c1", "text"))
check("the row that was picked is still picked, wherever it went",
      table.focus_row() is ROWS[0], table.focus_row())
table.show(["System", "Credits", "Why", "Notes"], ROWS, cells,
           actions=lambda row: [("system", lambda r=row: done.append(r["system"]), False),
                                ("delete", lambda: None, A.BTN_DANGER)])
table.top()
pump(0.2)
table.pick(4)
pump(0.2)
bar = [w.cget("text") for w in table.bar.winfo_children()]
check("the picked row's buttons are on the line under the table",
      bar[0] == "Sys 0004:" and bar[1:] == ["copy row", "system", "delete"], bar)
next(w for w in table.bar.winfo_children() if w.cget("text") == "system").event_generate("<Button-1>")
pump(0.1)
check("and a press on one does that row's job", done[-1:] == ["Sys 0004"], done)
table.copy_rows()
check("copy row takes every cell whole",
      copied[-1] == ("this row", "Sys 0004 | 4,000 | The whole sentence for row 4. | two lines"),
      copied[-1:])
table.pick(6, shift=True)
check("Shift picks a run", [r["n"] for r in table.picked_rows()] == [4, 5, 6])
table.copy_rows()
check("and Copy takes the run with the headings over it",
      copied[-1][0] == "3 rows" and copied[-1][1].splitlines()[0] == "System | Credits | Why | Notes"
      and len(copied[-1][1].splitlines()) == 4, copied[-1:])
table.pick(9, ctrl=True)
check("Ctrl adds a row", [r["n"] for r in table.picked_rows()] == [4, 5, 6, 9])
table.pick(2)
table.tree.focus_set()
pump(0.1)
table._key(type("E", (), {"state": 0})(), 1)
check("the down arrow moves the pick", table.focus_row()["n"] == 3)
table._key(type("E", (), {"state": 0})(), "end")
pump(0.1)
check("End goes to the last row and brings it into view",
      table.focus_row()["n"] == 1999 and "Sys 1999" in table.texts())
table.top()
pump(0.2)
item = table.tree.get_children()[1]
box = table.tree.bbox(item, "#1")
table._double_click(type("E", (), {"x": box[0] + 4, "y": box[1] + 4})())
check("a double-click does the row's first job", done[-1:] == ["Sys 0001"], done[-3:])
check("every row offers its own buttons", [b[0] for b in table.actions_for(1500)] == ["system", "delete"])

print("== nothing to show ==")
table.show_empty("Nothing shared yet for that filter.")
pump(0.1)
check("an empty table says what fills it, and the tree goes",
      table.advice.winfo_ismapped() and not table.tree.winfo_ismapped()
      and table.row_count() == 0)
table.show(["System"], ROWS[:3], lambda row: [(row["system"], None)])
pump(0.1)
check("rows again bring the tree back", table.tree.winfo_ismapped()
      and not table.advice.winfo_ismapped() and table.texts() == ["System", "Sys 0000", "Sys 0001", "Sys 0002"],
      table.texts())

print("== what the label grid took, for the record ==")
# Three hundred rows, not two thousand: a label grid much taller than that
# asks X for a picture of itself bigger than it will make, and the toolkit
# dies drawing it - one reason Find drew a hundred rows at a time.
grid = A.ScrollTable(shell)
table.pack_forget()
grid.pack(fill="both", expand=True)
pump(0.2)
started = time.perf_counter()
for index, row in enumerate(ROWS[:300], start=1):
    for column, cell in enumerate(cells(row)):
        text, colour, _key = A.EarningsWindow._cell(cell)
        A.cell_label(grid.inner, index, column, text, colour, full=A.cell_full(cell))
    A.row_buttons(grid.inner, index, [("system", lambda: None, False), ("delete", lambda: None, A.BTN_DANGER)])
app.update_idletasks()
app.update()
grid_took = time.perf_counter() - started
print("        the label grid drew 300 rows in %.2f s" % grid_took)
check("the tree view shows 2,000 rows quicker than the label grid drew 300",
      grid_took > 5 * show_took, (grid_took, show_took))
shell.destroy()
pump(0.2)

print("== the four windows ==")
NOW = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
SITES = [{"system": "Near %d" % i, "planet": "Near %d A 1" % i, "spot": str(1 + i % 3), "rigs": 1 + i % 6,
          "types": ["Platinum"], "age_days": i % 60, "uploader": "CMDR R%d" % i,
          "score": float(i % 10), "intact_confidence": 0.9, "distance_ly": i * 0.1}
         for i in range(2000)]
find = app.open_find() or app.finder
find = app.docked_tools.get("find") or find
pump(0.5)
started = time.perf_counter()
find.results("sites", json.dumps({"sites": SITES, "count": len(SITES), "complete": True}), True)
app.update_idletasks()
app.update()
took = time.perf_counter() - started
print("        Find took 2,000 sites in %.2f s" % took)
check("Find's results are a tree view table", isinstance(find.scroller, A.NativeTable)
      and find.table is find.scroller, type(find.scroller).__name__)
check("every one of the 2,000 is in the table at once - no Show more",
      find.scroller.row_count() == 2000 and len(find._rows) == 2000, find.scroller.row_count())
check("and the answer is on screen within a budget", took < 4.0, "%.2f s" % took)
check("a row is green while its last sighting is fresh", find.scroller.row_tone(0) == "good")
check("the picked site carries its buttons - the system, and its marks",
      [b[0] for b in find.scroller.actions_for(0)][:1] == ["system"]
      and any(b[0].startswith("good") for b in find.scroller.actions_for(0)),
      [b[0] for b in find.scroller.actions_for(0)])
find.sort_by(find._headers.index("Score"))
pump(0.2)
check("a heading sorts the window's rows, and the tree shows them",
      find.scroller.payload(0)["score"] == 0.0 and find.scroller.tree.heading("c%d" % find._headers.index("Score"), "text").endswith("^"))
for _ in range(30):
    find.scroller.wheel(Wheel())
pump(0.1)
check("the wheel scrolls it", find.scroller.yview()[0] > 0)

ledger = app.open_earnings() or app.ledger
ledger = app.docked_tools.get("earnings") or ledger
for index in range(300):
    started_at = "2026-10-{:02d}T{:02d}:00:00Z".format(1 + index % 28, index % 24)
    ledger.app.earnings.sessions.append(dict({k: "" for k in A.SV.SESSION_FIELDS}, **{
        "id": "s%d" % index, "started": started_at, "ended": started_at, "closed": started_at,
        "system": "Sys %d" % index, "body": "Sys %d A 1" % index, "kind": A.SV.RHINO,
        "mined": "Iridium:%d" % (10 + index), "transferred": "Iridium:%d" % (10 + index),
        "sold": "Iridium:%d" % (10 + index) if index % 2 else "",
        "credits": "%d" % (index * 100000 if index % 2 else 0)}))
ledger.app.earnings.save()
ledger.show_page("Sessions")
ledger.refresh()
pump(0.3)
check("Sessions are a tree view table with every session in it",
      isinstance(ledger.scroller, A.NativeTable) and ledger.scroller.row_count() == len(ledger._rows) >= 300,
      (type(ledger.scroller).__name__, ledger.scroller.row_count() if hasattr(ledger.scroller, "row_count") else None))
check("each session row carries its card and delete buttons",
      [b[0] for b in ledger.scroller.actions_for(0)][-2:] == ["card", "delete"],
      [b[0] for b in ledger.scroller.actions_for(0)])
check("a sold session reads green", any(ledger.scroller.row_tone(i) == "good" for i in range(4)))

sites_window = app.open_sites()
sites_window = app.docked_tools.get("sites") or sites_window
for index in range(250):
    app.store.set_location("Wyrd %d" % index, "Wyrd %d A 1" % index, "1", lat=1.0, lon=2.0, radius_m=2e6)
sites_window.refresh()
pump(0.3)
check("My sites is a tree view table with every site in it",
      isinstance(sites_window.scroller, A.NativeTable)
      and sites_window.scroller.row_count() == len(sites_window._rows) >= 250,
      type(sites_window.scroller).__name__)
check("each site carries its star and remove buttons",
      [b[0] for b in sites_window.scroller.actions_for(0)][:3] == ["system", "☆", "remove"],
      [b[0] for b in sites_window.scroller.actions_for(0)])

lander = app.open_land()
lander = app.docked_tools.get("land") or lander
pump(0.3)
check("Where to land is a tree view table", isinstance(lander.scroller, A.NativeTable)
      and lander.table is lander.scroller, type(lander.scroller).__name__)

app.destroy()
print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
