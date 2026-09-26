"""My sites: every signal you have logged and every find you have marked,
on every body - without a display.

A tester asked: "how to find a list of the planets and spots I've logged
(all 2 of them so far...) so I can return to them?" The main window only
ever shows the body you are on, and Find searches what everybody shared.
"""
import os, sys, tempfile, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-sites-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A  # noqa
# Copies go to the Windows clipboard directly on Windows. These checks
# read what a window put on ITS clipboard, so they take the Tk path
# everywhere - and never touch the real clipboard on the machine running them.
A._windows_clipboard = lambda *args, **kwargs: False
import survey as SV  # noqa

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


R = 1_800_000.0
store = SV.Survey(os.path.join(TMP, "store"))
# Two spots, as the tester had: one signal logged with finds in it, and one
# body where a find was marked without the signal ever being logged.
store.set_location("HR 7280", "HR 7280 A 3", "5", lat=10.0, lon=20.0,
                   radius_m=R, commodities=["Haematite", "Copper", "Thorium"],
                   depleted=["Thorium"])
store.add_deposit(system="HR 7280", body="HR 7280 A 3", location="5",
                  commodity="Haematite", rigs="4", amount="High",
                  lat="10.001", lon="20.001", recorded="2026-09-20T10:00:00Z",
                  mined="Haematite:12;Water:3")
store.add_deposit(system="HR 7280", body="HR 7280 A 3", location="5",
                  commodity="Haematite", rigs="2", amount="Medium",
                  lat="10.002", lon="20.002", recorded="2026-09-21T10:00:00Z")
store.add_deposit(system="HR 7280", body="HR 7280 A 3", location="5",
                  commodity="Copper", rigs="3", amount="Depleted",
                  lat="10.003", lon="20.003", recorded="2026-09-19T10:00:00Z",
                  mined="Copper:30")
store.add_deposit(system="Ega", body="Ega 1", location="2",
                  commodity="Samarium", rigs="", amount="Low",
                  lat="-5.0", lon="7.0", recorded="2026-09-23T08:00:00Z")
store.set_location("Ega", "Ega 3 a", "1", lat=1.0, lon=1.0, radius_m=R)

print("== every place, from the records ==")
sites = store.sites()
check("one row per signal, across bodies and systems", len(sites) == 3,
      [(s["system"], s["body"], s["signal"]) for s in sites])
hr = next(s for s in sites if s["body"] == "HR 7280 A 3")
check("the logged signal knows what the game said it offers",
      hr["logged"] and hr["offers"] == ["Haematite", "Copper", "Thorium"]
      and hr["depleted"] == ["Thorium"], hr)
check("three finds, two still there", hr["finds"] == 3 and hr["intact"] == 2, hr)
check("rigs still to be had leave out the depleted deposit", hr["rigs"] == 6, hr["rigs"])
check("tonnes mined count each deposit's own commodity, not its by-products",
      hr["mined"] == {"Haematite": 12, "Copper": 30}, hr["mined"])
check("what is there counts the intact finds", hr["types"] == {"Haematite": 2},
      hr["types"])
ega = next(s for s in sites if s["body"] == "Ega 1")
check("a find whose signal was never logged is still a site",
      not ega["logged"] and ega["finds"] == 1 and ega["signal"] == "2", ega)
empty = next(s for s in sites if s["body"] == "Ega 3 a")
check("and a signal logged with nothing marked yet", empty["logged"]
      and empty["finds"] == 0, empty)
check("most recent first", sites[0]["body"] == "Ega 1"
      or sites[0]["last"] >= sites[1]["last"], [s["last"] for s in sites])
check("a find with no system or body is left out, not a crash",
      SV.Survey(os.path.join(TMP, "blank")).sites() == [])

print("== what the table says ==")
cells = A.site_cells(hr, here=("hr 7280", "HR 7280 A 3"))
texts = [c[0] for c in cells]
check("the columns match the headings", len(cells) == len(A.SITES_HEADERS))
check("where you are now is marked", texts[1].endswith("(here)")
      and cells[0][1] == A.GREEN, texts[:2])
check("what is there: the finds, what the signal offers that is not found "
      "yet, and what the game says is worked out",
      texts[3] == "Haematite x2\noffers Copper\nworked out: Thorium", texts[3])
check("finds say how many are depleted", texts[4] == "3 (1 depleted)", texts[4])
check("rigs and tonnes", texts[5] == "6" and texts[6] == "42t", texts[5:7])
check("when, in words and a date", re.search(r"^\w.* \(\d{4}-\d\d-\d\d\)$", texts[7]),
      texts[7])
elsewhere = A.site_cells(hr, here=("Ega", "Ega 1"))
check("somewhere else is not marked here", not elsewhere[1][0].endswith("(here)")
      and elsewhere[0][1] is None)
blank = [c[0] for c in A.site_cells(empty)]
check("a signal with nothing marked reads as dashes, not zeros",
      blank[3] == "-" and blank[4] == "-" and blank[5] == "-" and blank[6] == "-",
      blank)

print("== where a find is from the middle of its signal ==")
_hr_finds = store.at("HR 7280", "HR 7280 A 3", "5")
_line = A.from_centre(store, _hr_finds[0])
check("measured from where the signal was logged, with the compass point",
      re.match(r"^from the signal centre: 4\d m NE 04[45]$", _line), _line)
check("a find whose signal was never logged has no such line",
      A.from_centre(store, store.at("Ega", "Ega 1")[0]) == "")
check("nor does one with no position",
      A.from_centre(store, dict(_hr_finds[0], lat="", lon="")) == "")
check("it is on the deposit's details", "centre = from_centre(self.store, deposit)"
      in open(A.__file__, encoding="utf-8").read())

print("== a find as a line of text, and back ==")
_dep = dict(_hr_finds[0])
_line = A.share_line(_dep)
check("one readable line: system, body, signal, what, rigs, amount, where",
      _line == "EDSMT find | HR 7280 | HR 7280 A 3 | signal 5 | Haematite | "
               "rigs 4 | amount High | density ? | 10.00100, 20.00100", _line)
check("and it says nothing about who found it",
      "CMDR" not in _line and "cmdr" not in _line.lower())
_other = SV.Survey(os.path.join(TMP, "friend"))
_chat = ("look at this one\n`%s`\n%s\nEDSMT find | broken line\n"
         "EDSMT find | Ega | Ega 1 | signal 2 | ? | rigs ? | amount ? | density ? | 1, 2\n"
         "EDSMT find | Ega | Ega 1 | signal 2 | Gold | rigs 9 | amount ? | density ? | 95, 2\n"
         % (_line, A.share_line(_hr_finds[1])))
_got = A.take_share_lines(_other, _chat)
check("pasted into another commander's EDSMT, the finds are added",
      _got["taken"] == 2 and len(_other.deposits) == 2, _got)
check("chat around them is ignored, and the broken lines are counted",
      _got["unreadable"] == 3, _got)
_added = _other.deposits[0]
check("with what, where, rigs and signal intact",
      (_added["system"], _added["body"], _added["location"], _added["commodity"],
       _added["rigs"], _added["amount"], _added["lat"], _added["lon"])
      == ("HR 7280", "HR 7280 A 3", "5", "Haematite", "4", "High",
          "10.001000", "20.001000"), _added)
check("a blank from the line stays blank, not the word '?'",
      _added["density"] == "", _added["density"])
check("marked as reported, and noted as pasted",
      _added["status"] == SV.STATUS_REPORTED and "pasted" in _added["notes"])
check("and the signal is on their list too",
      _other.location("HR 7280", "HR 7280 A 3", "5") is not None and _got["signals"] == 1)
_again = A.take_share_lines(_other, _chat)
check("pasting the same thing twice adds nothing",
      _again["taken"] == 0 and _again["duplicates"] == 2 and len(_other.deposits) == 2, _again)
check("a find already marked here is not added again",
      A.take_share_lines(store, _line)["duplicates"] == 1)
check("the summary says what happened",
      A.share_summary(_got) == "Added 2 find(s), 3 line(s) could not be read.",
      A.share_summary(_got))
check("and says what to copy when there was nothing",
      "EDSMT find" in A.share_summary(A.take_share_lines(_other, "hello")))
_src = open(A.__file__, encoding="utf-8").read()
check("Copy to share is on a deposit, Paste shared finds in Settings",
      "command=self.copy_selected" in _src and "command=self.paste_shared" in _src)

print("== the filter ==")
check("by system", [s["body"] for s in A.sites_matching(sites, "hr 72")]
      == ["HR 7280 A 3"])
check("by commodity, found or offered",
      {s["body"] for s in A.sites_matching(sites, "samar")} == {"Ega 1"}
      and {s["body"] for s in A.sites_matching(sites, "thorium")} == {"HR 7280 A 3"})
check("blank is everything", len(A.sites_matching(sites, "  ")) == 3)

print("== sorting keeps each column's own order ==")
keys = [A.EarningsWindow._cell(A.site_cells(s)[7])[2] for s in sites]
check("Last there sorts by age, not by the words",
      sorted(range(3), key=lambda i: keys[i])[0] == 0, keys)

print("== the window ==")
check("the top bar has a My sites button",
      'text="My sites"' in open(A.__file__, encoding="utf-8").read()
      and 'command=self.open_sites' in open(A.__file__, encoding="utf-8").read())
app = _ctkstub.ctk.CTk()
app.store = store
app.settings = dict(A.DEFAULT_SETTINGS)
app.here = lambda: ("HR 7280", "HR 7280 A 3")
win = A.SitesWindow(app)
check("it opens with every site in it", len(win._rows) == 3, len(win._rows))
check("and says how many, where", "3 signal(s) on 3 bodies in 2 system(s)"
      in win.summary.cget("text"), win.summary.cget("text"))
win.filter_box.insert(0, "ega")
win._paint()
check("typing in the filter narrows it", len(win._rows) == 2
      and "2 match the filter" in win.summary.cget("text"), len(win._rows))
copied = []
win.clipboard_clear = lambda: None
win.clipboard_append = lambda text: copied.append(text)
win.copy_text("the system name", "Ega")
check("copying a system name puts it on the clipboard", copied == ["Ega"])
win.filter_box.delete(0, "end"); win._paint()
win.copy_all()
check("Copy all is a header and one line a site",
      copied[-1].splitlines()[1].startswith("System | Body")
      and len(copied[-1].splitlines()) == 5, copied[-1:])
nothing = _ctkstub.ctk.CTk()
nothing.store = SV.Survey(os.path.join(TMP, "none"))
nothing.settings = dict(A.DEFAULT_SETTINGS)
nothing.here = lambda: ("", "")
empty_win = A.SitesWindow(nothing)
check("with nothing logged it says how to log something, with the real keys",
      "Alt+1" in empty_win._advice() and "Alt+3" in empty_win._advice(),
      empty_win._advice())

print("== a pasted find a few metres from one of yours is that one ==")
_mine = SV.Survey(os.path.join(TMP, "near"))
_mine.set_location("HR 7280", "HR 7280 A 3", "5", lat=10.0, lon=20.0, radius_m=R)
_mine.add_deposit(system="HR 7280", body="HR 7280 A 3", location="5",
                  commodity="Haematite", rigs="4", lat="10.001000", lon="20.001000")
_twenty_m = 20.0 / R * 57.29577951308232
_friend = ("EDSMT find | HR 7280 | HR 7280 A 3 | signal 5 | Haematite | rigs 4 | "
           "amount ? | density ? | %.5f, 20.00100" % (10.001 + _twenty_m))
check("same commodity within 100 m of one marked is not added twice",
      A.take_share_lines(_mine, _friend)["duplicates"] == 1 and len(_mine.deposits) == 1)
_other_kind = _friend.replace("Haematite", "Copper")
check("a different commodity there is its own find",
      A.take_share_lines(_mine, _other_kind)["taken"] == 1)

print("== My sites opens on where you are ==")
_order = A.SitesWindow._sorted(type("W", (), {"_sort_column": None,
                                              "_here": lambda self: ("Ega", "Ega 3 a")})(),
                               sites)
check("the body you are on is first, the rest most recent first",
      _order[0]["body"] == "Ega 3 a" and [x["body"] for x in _order[1:]]
      == [x["body"] for x in sites if x["body"] != "Ega 3 a"],
      [x["body"] for x in _order])

print("== how long ago a deposit was worked out ==")
import time as _t
_now = _t.mktime((2026, 9, 29, 12, 0, 0, 0, 0, -1))
check("from its MINED OUT stamp, in days",
      A.worked_out_age({"amount": "Depleted", "notes": "found it\nMined 20/09/2026 10:05"},
                       now=_now) == "worked out 9 days ago")
check("the latest stamp counts",
      A.worked_out_age({"amount": "Depleted",
                        "notes": "Mined 01/09/2026 10:05\nMined out after 40t 28/09/2026 09:00"},
                       now=_now) == "worked out yesterday")
check("nothing for a deposit still there, or with no stamp",
      A.worked_out_age({"amount": "High", "notes": "Mined 20/09/2026 10:05"}, now=_now) == ""
      and A.worked_out_age({"amount": "Depleted", "notes": ""}, now=_now) == "")
check("and it is on the details", "age = worked_out_age(deposit)" in
      open(A.__file__, encoding="utf-8").read())

print("== Where to land, only the bodies carrying one commodity ==")
_land = [{"short": "A 1", "carries": ["haematite", "monazite"]},
         {"short": "A 2", "carries": ["olivine"]}, {"short": "A 3"}]
check("Any is every body", len(A.land_carrying(_land, "")) == 3)
check("a commodity keeps the bodies that carry it, however it is spelt",
      [r["short"] for r in A.land_carrying(_land, "MONAZITE")] == ["A 1"])
check("and the window has the box", "text=\"Carrying\"" in
      open(A.__file__, encoding="utf-8").read())

print("== nothing takes the game's keyboard on its own ==")
# Something arriving in the background - a scan, an answer from a server -
# must never bring a window forward over the game. Only a click or a key
# the commander pressed may raise or focus one.
import ast as _ast
_tree = _ast.parse(open(A.__file__, encoding="utf-8").read())
_raisers = {}
for _node in _ast.walk(_tree):
    if isinstance(_node, _ast.FunctionDef):
        for _sub in _ast.walk(_node):
            if (isinstance(_sub, _ast.Call) and isinstance(_sub.func, _ast.Attribute)
                    and _sub.func.attr in ("lift", "focus_force", "deiconify",
                                           "grab_set", "tkraise")):
                _raisers.setdefault(_node.name, set()).add(_sub.func.attr)
check("only windows opened by a click, a typed box and the key capture do",
      set(_raisers) == {"open_sites", "open_land", "_capture", "__init__", "show"},
      _raisers)

print("== every copy goes through the one clipboard writer ==")
_src_all = open(A.__file__, encoding="utf-8").read()
check("the Win32 writer on Windows, Tk only as the fallback",
      _src_all.count("clipboard_append(") == 1 and _src_all.count("put_on_clipboard(self,") >= 8)

print("== a tonne shows once the laser pauses, not once a tonne ==")
_st = A.EDSMT.__new__(A.EDSMT)
_shown = []
_st.selected = {"id": "d1"}
_st.on_pick = lambda row: _shown.append("details")
_st.refresh_deposits = lambda: _shown.append("list")
_st._tonnes_changed = ("d1", 1000.0)
check("while tonnes are still coming in, nothing is redrawn",
      _st.show_tonnes(now=1000.0 + A.TONNES_QUIET_S - 1) is False and _shown == [])
check("a few seconds after the last, the details and the list follow",
      _st.show_tonnes(now=1000.0 + A.TONNES_QUIET_S + 0.1) and _shown == ["details", "list"],
      _shown)
check("and only once", _st.show_tonnes(now=2000.0) is False and len(_shown) == 2)

print("== a table's scrollbars go when there is nothing to scroll ==")
# Seen on every table on a real screen: a full-width sideways scrollbar with
# nothing to scroll to. Tk can leave a bar drawn when it is forgotten between
# being gridded and being drawn; the toolkit also re-grids a bar on rescale
# unless grid_forget is what took it off.
class _Bar:
    def __init__(self, managed, mapped_after_forget):
        self.managed, self.mapped = managed, managed
        self.stuck = mapped_after_forget
        self.calls = []
    def set(self, low, high): self.calls.append(("set", low, high))
    def winfo_manager(self): return "grid" if self.managed else ""
    def winfo_ismapped(self): return self.mapped
    def grid(self, **kw): self.calls.append("grid"); self.managed = True
    def grid_forget(self):
        self.calls.append("grid_forget"); self.managed = False
        self.mapped = self.stuck
    def grid_remove(self): self.calls.append("grid_remove"); self.managed = False
    def place(self, **kw): self.calls.append("place")
    def place_forget(self): self.calls.append("place_forget"); self.mapped = False
stuck = _Bar(managed=True, mapped_after_forget=True)
A.ScrollTable._toggle(stuck, "0.0", "1.0", {})
check("forgotten with grid_forget, which the toolkit does not undo",
      "grid_forget" in stuck.calls and "grid_remove" not in stuck.calls, stuck.calls)
check("and taken off the screen even when Tk leaves it drawn",
      stuck.calls[-2:] == ["place", "place_forget"] and not stuck.mapped, stuck.calls)
clean = _Bar(managed=True, mapped_after_forget=False)
A.ScrollTable._toggle(clean, "0.0", "1.0", {})
check("a bar that went quietly is not touched again",
      "place" not in clean.calls, clean.calls)
needed = _Bar(managed=False, mapped_after_forget=False)
A.ScrollTable._toggle(needed, "0.0", "0.6", {"row": 1})
check("and one that is needed is put back", "grid" in needed.calls, needed.calls)
again = _Bar(managed=True, mapped_after_forget=False)
A.ScrollTable._toggle(again, "0.0", "0.6", {"row": 1})
check("but not gridded twice", "grid" not in again.calls, again.calls)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
