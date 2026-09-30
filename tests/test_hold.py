"""What is aboard, and where to sell it - without a display.

Reported: the earnings showed nothing for a commander who already had ore in
the ship or the SRV, Sapphire showed one station's price with nothing to say
so, and nothing asked what the system you are actually in pays. This drives
the app's side of all three: both holds added up, the lookup asked from the
current system by name, the answers filed, and the strip that quotes them.
"""
import os, sys, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-hold-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A  # noqa
import survey as SV  # noqa

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


print("== both holds, added up ==")
holds = {"Ship": {"Haematite": 30, "Tea": 2}, "SRV": {"Haematite": 6, "Sapphire": 1}}
check("ship and SRV together",
      A.combined_hold(holds) == {"Haematite": 36, "Tea": 2, "Sapphire": 1},
      A.combined_hold(holds))
check("a reader with only the one hold still answers",
      A.combined_hold({}, {"Gold": 4}) == {"Gold": 4})
check("nonsense counts are left out, not a crash",
      A.combined_hold({"Ship": {"Gold": "x", "Silver": 0, "Ruby": 2}}) == {"Ruby": 2})

print("== what gets asked about ==")
order = A.worth_asking({"Haematite": 40, "Sapphire": 1, "Tea": 5, "Gold": 3})
check("a tonne of Sapphire is asked about before forty of Haematite",
      order.index("Sapphire") < order.index("Haematite"), order)
check("anything without a published figure still gets asked, last",
      order[-1] == "Tea", order)
check("and no more than the cap",
      len(A.worth_asking({str(n): 1 for n in range(20)})) == A.QUOTE_MAX)

print("== reading an answer ==")
ANSWER = {"commodity": "Sapphire", "best_sell": 648000,
          "market": [
              {"commodity": "Sapphire", "station": "Oblivion Station",
               "system": "HIP 99012", "sell": 127000, "distance_ly": 40.2,
               "seen": "2026-09-20T10:00:00Z", "source": "market"},
              {"commodity": "Sapphire", "station": "Mandi Port",
               "system": "Ten Mandi", "sell": 648000, "distance_ly": 8.2,
               "seen": "2026-09-23T10:00:00Z", "source": "market"}],
          "community": [
              {"commodity": "Sapphire", "station": "Home Dock",
               "system": "HR 7280", "sell": 301000, "seen": "2026-09-24",
               "source": "community"},
              {"commodity": "Sapphire", "station": "Nothing", "system": "X",
               "sell": 0}]}
commodity, best, here = A.read_quote(json.dumps(ANSWER), "HR 7280")
check("it knows which commodity it was", commodity == "Sapphire", commodity)
check("the best is the best anywhere in it",
      best and best["station"] == "Mandi Port", best)
check("and the system you are in has its own figure beside it",
      here and here["sell"] == 301000, here)
check("where it is, with how far",
      A.quote_where(best) == "Mandi Port, Ten Mandi (8.2 Ly)", A.quote_where(best))
check("a row with no distance just leaves it off",
      A.quote_where(here) == "Home Dock, HR 7280", A.quote_where(here))
check("nothing is a dash", A.quote_where(None) == "-")
_c, _b, nowhere = A.read_quote(ANSWER, "Somewhere Else")
check("no station in your system is no figure, not a zero", nowhere is None)
_c, empty, _h = A.read_quote({"commodity": "Ruby"}, "HR 7280")
check("an empty answer is no best, not a crash", empty is None)


print("== asking, from the app ==")
class _Comm:
    can_read = True
    def __init__(self): self.calls = []
    def sell(self, **k): self.calls.append(k); return True


class _Watcher:
    system = "HR 7280"
    star_pos = (1.0, 2.0, 3.0)
    holds = {"Ship": {"Haematite": 30}, "SRV": {"Sapphire": 2, "Tea": 1}}
    cargo = {"Sapphire": 2, "Tea": 1}
    market = None


class _Books:
    """What recent Rhino sessions dug up and have not sold. The Tea in the
    SRV was picked up, not mined - 1.10031: "The earnings tab is picking up
    stuff to do with normal hauling lets not do that"."""
    current = rhino = None
    paused = False
    def unsold(self): return {"Haematite": 30, "Sapphire": 2}


app = A.EDSMT.__new__(A.EDSMT)
app.community = _Comm()
app.watcher = _Watcher()
app.earnings = _Books()
timers = []
app.after = lambda ms, fn: timers.append((ms, fn))
check("what is priced is what was mined, not the whole hold",
      app.mined_aboard() == {"Haematite": 30, "Sapphire": 2}, app.mined_aboard())
count, why = app.quote_hold(50)
check("one ask per mined commodity aboard - the hauled Tea is not asked about",
      count == 2 and not why, (count, why))
check("spaced out, so the market index answers every one of them",
      [ms for ms, _fn in timers] == [0, A.QUOTE_GAP_MS],
      [ms for ms, _fn in timers])
for _ms, fn in timers:
    fn()
sent = app.community.calls
check("asked from the system I am in, by name",
      all(k.get("near_system") == "HR 7280" for k in sent), sent)
check("and by position, with the radius chosen",
      all(k.get("near") == (1.0, 2.0, 3.0) and k.get("within_ly") == 50
          for k in sent), sent)
check("answered to the app, not to the Find window",
      all(k.get("tag") == A.QUOTE_TAG for k in sent) and A.QUOTE_TAG not in A.FIND_TAGS,
      sent)
check("the most valuable first", sent[0]["commodity"] == "Sapphire", sent[0])

nobody = A.EDSMT.__new__(A.EDSMT)
nobody.community = type("C", (), {"can_read": False})()
nobody.watcher = _Watcher()
check("no community URL says so rather than asking",
      nobody.quote_hold()[0] == 0 and "Settings" in nobody.quote_hold()[1])
lost = A.EDSMT.__new__(A.EDSMT)
lost.community = _Comm()
lost.watcher = type("W", (), {"system": "", "holds": {"Ship": {"Gold": 1}},
                              "cargo": {}})()
check("no system yet says so", lost.quote_hold()[0] == 0
      and "system" in lost.quote_hold()[1], lost.quote_hold())
empty_hold = A.EDSMT.__new__(A.EDSMT)
empty_hold.community = _Comm()
empty_hold.watcher = type("W", (), {"system": "Sol", "holds": {}, "cargo": {}})()
check("an empty hold asks nothing", empty_hold.quote_hold()[0] == 0)

print("== answers filed, and quoted on the strip ==")
strip = []
app.t_earnings = type("L", (), {"configure": lambda self, **k: strip.append(k.get("text"))})()
app.take_quote(True, json.dumps(ANSWER))
filed = app.fresh_quotes().get(SV.fold("Sapphire"))
check("the answer is filed under its commodity",
      filed and filed["best"]["sell"] == 648000 and filed["here"]["sell"] == 301000,
      filed)
check("the strip says what the hold fetches at the best price found, and that "
      "not everything is priced yet",
      strip and "up to 1,296,000 Cr within 50 Ly" in strip[-1]
      and "(1 of 2 priced)" in strip[-1], strip[-1:])
check("and the ship and SRV are both in the mined figure, the Tea left out",
      strip and strip[-1].startswith("mined aboard 32t"), strip[-1:])
for name, price in (("Haematite", 9000),):
    app.take_quote(True, json.dumps({"commodity": name, "market": [
        {"station": "S", "system": "Ten Mandi", "sell": price, "distance_ly": 8.2}]}))
check("once everything is priced the caveat goes",
      "up to 1,566,000 Cr within 50 Ly" in strip[-1] and "priced)" not in strip[-1],
      strip[-1:])
app.watcher.system = "Somewhere Else"
app.update_earnings()
check("move system and the old quotes stop being quoted",
      "up to" not in strip[-1], strip[-1:])
app.watcher.system = "HR 7280"
for quote in app.sell_quotes.values():
    quote["at"] -= A.QUOTE_FRESH_S + 1
app.update_earnings()
check("and so do quotes older than half an hour", "up to" not in strip[-1], strip[-1:])
app.take_quote(False, "HTTP 503")
check("a refused ask is kept to be said, not a crash",
      app.quote_problem == "HTTP 503")
before = dict(app.sell_quotes)
app.take_quote(True, "not json")
check("an unreadable answer files nothing", app.sell_quotes == before)
app.take_quote(True, json.dumps(ANSWER))
check("and the next good answer clears the problem", app.quote_problem == "")

print("== routed by the app's result loop ==")
routed = []
router = A.EDSMT.__new__(A.EDSMT)
router.worker = type("W", (), {"drain": lambda self: [(A.QUOTE_TAG, True, "{}")]})()
router.take_quote = lambda ok, message: routed.append((ok, message))
router.collect_results()
check("a hold-sell answer reaches take_quote", routed == [(True, "{}")], routed)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
