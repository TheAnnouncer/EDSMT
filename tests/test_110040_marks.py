"""1.10040 (#302): a Good and a Bad mark on a shared site.

- On a shared site - a row of My sites, a row of Find's Sites, and the site
  of the mining location you are in - a "good" and a "bad" mark. One per
  commander per site, changed as often as you like; your own mark shows lit.
- Sent to the community map the way a depletion report is - the same
  header, the same key - and kept when there is no connection, to go when
  there is one.
- The counts the map gives for a site are shown beside the marks.

Pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_marks.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-marks-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import edonline as EDO     # noqa: E402
import sitemarks as SM     # noqa: E402

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
            traceback.print_exc(limit=6)
        return fn
    return wrap


def answer(site, mark, reply=None, error=None, refused=False):
    data = {"site": list(site), "mark": mark}
    if error is not None:
        data.update(error=error, refused=refused)
    else:
        data["reply"] = reply or {}
    return json.dumps(data)


@section("the book of marks: one per site, changeable, kept until sent")
def _book():
    path = os.path.join(TMP, "book", SM.FILE_NAME)
    book = SM.MarkBook(path)
    check("nothing marked to begin with", book.mine("Ega", "Ega 1", "7") == "")
    check("a good mark is kept", book.mark("Ega", "Ega 1", "7", SM.GOOD, now=100.0)
          and book.mine("Ega", "Ega 1", "7") == "good")
    check("the site is matched whatever its case or spacing",
          book.mine("EGA", " ega  1 ", "7") == "good")
    check("changeable: bad replaces good - one mark per site",
          book.mark("Ega", "Ega 1", "7", SM.BAD, now=101.0) and book.mine("Ega", "Ega 1", "7") == "bad"
          and len(book.marks) == 1)
    check("only good or bad", not book.mark("Ega", "Ega 1", "7", "great")
          and book.mine("Ega", "Ega 1", "7") == "bad")
    due = book.due(now=102.0)
    check("an unsent mark is due to go", [e["mark"] for e in due] == ["bad"]
          and due[0]["system"] == "Ega" and due[0]["planet"] == "Ega 1" and due[0]["spot"] == "7", due)
    book.sending(due[0], now=102.0)
    check("once on its way it is not sent twice at once", book.due(now=110.0) == [])
    status, words = book.answered(answer(("Ega", "Ega 1", "7"), "bad", error="could not reach the server"))
    check("no connection: kept, and said so", status == "later" and "kept" in words.lower(), (status, words))
    check("and tried again after a while, not at once",
          book.due(now=110.0) == [] and len(book.due(now=102.0 + SM.RETRY_S + 1)) == 1)
    status, words = book.answered(answer(("Ega", "Ega 1", "7"), "bad", reply={"ok": True, "good": 2, "bad": 1}))
    check("answered: sent, with the site's counts now", status == "sent"
          and book.counts_for("Ega", "Ega 1", "7") == (2, 1) and book.due(now=1e9) == [], (status, words))
    check("and the line says what the map now holds", "2 good, 1 bad" in words, words)
    check("the same mark again is no change and nothing to send",
          not book.mark("Ega", "Ega 1", "7", SM.BAD) and book.due(now=1e9) == [])
    book.mark("Ega", "Ega 1", "7", SM.GOOD, now=200.0)
    book.answered(answer(("Ega", "Ega 1", "7"), "bad", reply={"ok": True, "good": 2, "bad": 1}))
    check("an answer for an older mark does not tick off a newer one",
          [e["mark"] for e in book.due(now=1e9)] == ["good"])
    book.mark("Ega", "Ega 2", "1", SM.GOOD)
    status, _words = book.answered(answer(("Ega", "Ega 2", "1"), "good", error="HTTP 404", refused=True))
    check("refused - no shared site there: dropped, not tried for ever",
          status == "refused" and book.mine("Ega", "Ega 2", "1") == "" and
          all(e["planet"] != "Ega 2" for e in book.due(now=1e9)))
    check("an answer that is not one of ours is nothing", book.answered("rubbish")[0] == ""
          and book.answered(json.dumps({"x": 1}))[0] == "")
    book.save()
    again = SM.MarkBook(path)
    again.load()
    check("kept on disk: marks, what is still to send, and the counts",
          again.mine("Ega", "Ega 1", "7") == "good" and len(again.due(now=1e9)) == 1
          and again.counts_for("Ega", "Ega 1", "7") == (2, 1))
    broken = os.path.join(TMP, "broken.json")
    with open(broken, "w", encoding="utf-8") as handle:
        handle.write("{not json")
    book = SM.MarkBook(broken)
    check("a damaged file is an empty book, not a crash", book.load() is False and book.marks == {})
    book = SM.MarkBook(None)
    book.take_rows([{"system": "Ega", "planet": "Ega 3", "spot": "2", "good_marks": 4, "bad_marks": 1},
                    {"system": "Ega", "body": "Ega 4", "location": "5", "good_marks": "x"},
                    {"system": "Ega", "planet": "Ega 5", "spot": "1"}])
    check("the counts come off any answer that lists sites or finds",
          book.counts_for("Ega", "Ega 3", "2") == (4, 1) and book.counts_for("Ega", "Ega 5", "1") is None
          and book.counts_for("Ega", "Ega 4", "5") is None)
    check("the buttons: lowercase words, the count beside each where known, yours lit",
          SM.buttons(book, "Ega", "Ega 3", "2") == [("good 4", "good", False), ("bad 1", "bad", False)])
    book.mark("Ega", "Ega 3", "2", SM.GOOD)
    check("your own mark lit", SM.buttons(book, "Ega", "Ega 3", "2")[0][2] is True
          and SM.buttons(book, "Ega", "Ega 3", "2")[1][2] is False)
    check("no counts yet: the words alone",
          [b[0] for b in SM.buttons(book, "Ega", "Ega 9", "1")] == ["good", "bad"])


@section("the client sends a mark the way it sends a depletion report")
def _client():
    class Worker:
        def __init__(self):
            self.jobs = []

        def submit(self, tag, fn):
            self.jobs.append((tag, fn))

    sent = []

    def post(url, payload, timeout=20.0, headers=None):
        sent.append((url, payload, headers))
        return {"ok": True, "mark": payload["message"]["mark"], "good": 1, "bad": 0}

    real = EDO.post_json
    EDO.post_json = post
    try:
        client = EDO.CommunityClient(Worker())
        client.configure("", token="", enabled=False)
        check("with sharing off nothing is sent", not client.mark_site("CMDR X", "Ega", "Ega 1", "7", "good"))
        client.configure("", token="staff-token", enabled=True)
        check("with it on, a mark goes", client.mark_site("CMDR X", "Ega", "Ega 1", "7", "good"))
        check("but only good or bad", not client.mark_site("CMDR X", "Ega", "Ega 1", "7", "meh"))
        tag, job = client.worker.jobs[-1]
        reply = json.loads(job())
        url, payload, headers = sent[-1]
        check("to /v1/marks under its own tag", url == client.base_url + "/v1/marks" and tag == EDO.MARK_TAG)
        check("in the same envelope as a depletion report: schema, commander, software",
              payload["$schema"] == EDO.MARK_SCHEMA and payload["header"]["uploaderID"] == "CMDR X"
              and payload["header"]["softwareName"] == "EDSMT"
              and payload["message"] == {"system": "Ega", "planet": "Ega 1", "spot": "7", "mark": "good"},
              payload)
        check("with the same headers the client sends every write with", headers == client._headers())
        check("the answer names the site and the mark", reply["site"] == ["Ega", "Ega 1", "7"]
              and reply["mark"] == "good" and reply["reply"]["good"] == 1, reply)

        def offline(url, payload, timeout=20.0, headers=None):
            raise RuntimeError("could not reach api.radioraxxla.com: timed out")
        EDO.post_json = offline
        client.mark_site("CMDR X", "Ega", "Ega 1", "7", "bad")
        reply = json.loads(client.worker.jobs[-1][1]())
        check("no connection is an answer too, not refused", reply["error"] and not reply["refused"], reply)

        def gone(url, payload, timeout=20.0, headers=None):
            raise RuntimeError("api.radioraxxla.com refused it (HTTP 404): No shared site there to mark.")
        EDO.post_json = gone
        client.mark_site("CMDR X", "Ega", "Ega 1", "7", "bad")
        reply = json.loads(client.worker.jobs[-1][1]())
        check("a site the map does not have is refused", reply["refused"] is True, reply)

        def busy(url, payload, timeout=20.0, headers=None):
            raise RuntimeError("api.radioraxxla.com refused it (HTTP 429): more than an hour's worth")
        EDO.post_json = busy
        client.mark_site("CMDR X", "Ega", "Ega 1", "7", "bad")
        reply = json.loads(client.worker.jobs[-1][1]())
        check("too many in an hour is tried again later, not refused", reply["refused"] is False, reply)
    finally:
        EDO.post_json = real


# ---------------------------------------------------------------------------
# The app on the real toolkit. Nothing leaves the machine.
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % _exc)
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
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "welcome_seen_version": A.APP_VERSION, "tour_done": True,
               "journal_dir": JOURNALS, "find_unlocked": True}, _f)


class Link:
    """Stands in for the community link: records marks, sends nothing."""
    ready = False
    can_read = True
    can_verify = False
    share_name = True
    enabled = True

    def __init__(self):
        self.marks = []

    def mark_site(self, cmdr, system, planet, spot, mark, tag=EDO.MARK_TAG):
        if not self.ready:
            return False
        self.marks.append((cmdr, system, planet, spot, mark))
        return True

    def __getattr__(self, name):
        return lambda *args, **kwargs: False


app = A.EDSMT()
app.geometry("1600x1000+0+0")
app.updates.check = lambda *args, **kwargs: None
app.community.enabled = False
app.community = Link()
app.watcher.cmdr = "Jameson"


def pump(times=3):
    for _ in range(times):
        app.update_idletasks()
        app.update()


def settle(seconds=1.0):
    until = time.time() + seconds
    while time.time() < until:
        pump(1)
        time.sleep(0.02)


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


def labels(widget):
    out = []
    for child in walk(widget):
        try:
            out.append((str(child.cget("text")), child))
        except Exception:
            continue
    return out


settle(3.0)


@section("the app: Find's sites rows carry the marks, with the map's counts")
def _find():
    app.open_find()
    settle(1.0)
    finder = app.finder
    finder.results("sites", json.dumps({"sites": [
        {"system": "Ega", "planet": "Ega 1", "spot": "7", "rigs": 4, "types": ["Gold"], "score": 3.0,
         "intact_confidence": 0.9, "age_days": 2, "good_marks": 3, "bad_marks": 1}]}), True)
    settle(0.8)
    found = [w for text, w in labels(finder.table) if text in ("good 3", "bad 1")]
    check("a good and a bad mark on the row, each with its count", len(found) == 2,
          [t for t, _w in labels(finder.table)][-12:])
    check("the app learnt the counts from the answer", app.site_marks().counts_for("Ega", "Ega 1", "7") == (3, 1))
    good = next(w for text, w in labels(finder.table) if text == "good 3")
    unlit = good.cget("bg")
    good.event_generate("<Button-1>")
    settle(0.5)
    check("pressed: kept as your mark", app.site_marks().mine("Ega", "Ega 1", "7") == "good")
    check("sharing off: nothing went, and the status line says it will",
          app.community.marks == [] and "when" in str(app.status.cget("text")).lower(),
          app.status.cget("text"))
    lit = next(w for text, w in labels(finder.table) if text.startswith("good"))
    check("and the row shows it lit", lit.cget("bg") != unlit, (lit.cget("bg"), unlit))
    finder.results("intact", json.dumps({"sites": [
        {"system": "Ega", "planet": "Ega 1", "spot": "7", "rigs": 4, "types": ["Gold"],
         "intact_confidence": 0.9, "good_marks": 3, "bad_marks": 1}]}), True)
    settle(0.5)
    check("the Still there rows carry them too",
          any(text.startswith("good") for text, _w in labels(finder.table))
          and any(text.startswith("bad") for text, _w in labels(finder.table)))
    finder.results("prices", json.dumps({"prices": [{"commodity": "Gold", "station": "Hub", "system": "Ega",
                                                     "sell": 50000}]}), True)
    settle(0.5)
    check("a price row is not a site and has none",
          not any(text.startswith(("good", "bad")) for text, _w in labels(finder.table)))


@section("the app: kept with no connection, sent when there is one")
def _queue():
    check("sharing off: still waiting", app.community.marks == []
          and len(app.site_marks().due(now=1e12)) == 1)
    app.community.ready = True
    sent = app.send_marks(now=time.time())
    check("sharing on: the waiting mark goes, with the commander from the journal",
          sent == 1 and app.community.marks == [("Jameson", "Ega", "Ega 1", "7", "good")], app.community.marks)
    check("and is not sent twice while it is on its way", app.send_marks(now=time.time()) == 0)
    app.take_mark(True, answer(("Ega", "Ega 1", "7"), "good", error="could not reach the server"))
    check("no connection: kept for later", len(app.site_marks().due(now=time.time() + SM.RETRY_S + 1)) == 1)
    check("the app tries again on its own as time goes by",
          "self.send_marks()" in open(A.__file__, encoding="utf-8").read())
    app.take_mark(True, answer(("Ega", "Ega 1", "7"), "good", reply={"ok": True, "good": 4, "bad": 1}))
    check("answered: sent, and the counts move on", app.site_marks().due(now=1e12) == []
          and app.site_marks().counts_for("Ega", "Ega 1", "7") == (4, 1))
    check("the answer is handed over from the worker by its tag",
          "if tag == EDO.MARK_TAG:" in open(A.__file__, encoding="utf-8").read())
    finder = app.finder
    finder.results("sites", json.dumps({"sites": [
        {"system": "Ega", "planet": "Ega 1", "spot": "7", "rigs": 4, "types": ["Gold"], "score": 3.0,
         "intact_confidence": 0.9, "age_days": 2, "good_marks": 4, "bad_marks": 1}]}), True)
    settle(0.5)
    bad = next(w for text, w in labels(finder.table) if text.startswith("bad"))
    bad.event_generate("<Button-1>")
    settle(0.5)
    check("changed to bad: sent at once with sharing on",
          app.community.marks[-1] == ("Jameson", "Ega", "Ega 1", "7", "bad")
          and app.site_marks().mine("Ega", "Ega 1", "7") == "bad")
    again = SM.MarkBook(os.path.join(app.store.folder, SM.FILE_NAME))
    again.load()
    check("written to the data folder", again.mine("Ega", "Ega 1", "7") == "bad")


@section("the app: My sites rows carry the marks")
def _sites():
    app.store.set_location("Ega", "Ega 2", "3", lat=1.0, lon=2.0, radius_m=2e6)
    app.store.add_deposit(system="Ega", body="Ega 2", location="3", commodity="Gold", rigs="2",
                          amount="High", density="Medium", lat="1.000000", lon="2.000000")
    window = app.open_sites()
    settle(1.0)
    window.refresh()
    settle(0.8)
    texts = [text for text, _w in labels(window.table)]
    check("the site with a find on it has a good and a bad mark",
          "good" in texts and "bad" in texts, texts[-14:])
    good = next(w for text, w in labels(window.table) if text == "good")
    good.event_generate("<Button-1>")
    settle(0.5)
    check("pressed: marked, and sent", app.site_marks().mine("Ega", "Ega 2", "3") == "good"
          and app.community.marks[-1] == ("Jameson", "Ega", "Ega 2", "3", "good"))


@section("the app: the site of the location you are in carries them under its shared finds")
def _zone():
    shared = [{"id": "shared-1", "system": "Ega", "body": "Ega 1", "location": "7", "commodity": "Gold",
               "rigs": "4", "amount": "High", "lat": "1.000000", "lon": "1.000000", "cmdr": "CMDR Other",
               "shared": True, "good_marks": 4, "bad_marks": 1}]
    app.shared = {("ega", "ega 1"): {"at": time.time(), "rows": shared}}
    app.here = lambda: ("Ega", "Ega 1")
    app.signal = lambda: "7"
    app.refresh_deposits()
    settle(0.5)
    texts = [text for text, _w in labels(app.deposit_list)]
    check("under the shared finds: this site's marks, yours lit, the counts beside them",
          any(t.startswith("This site") for t in texts) and "good 4" in texts and "bad 1" in texts, texts)
    good = next(w for text, w in labels(app.deposit_list) if text == "good 4")
    good.event_generate("<Button-1>")
    settle(0.5)
    check("pressed: the location's site is marked good",
          app.site_marks().mine("Ega", "Ega 1", "7") == "good"
          and app.community.marks[-1] == ("Jameson", "Ega", "Ega 1", "7", "good"))
    app.take_shared(True, json.dumps({"system": "Ega", "body": "Ega 3", "deposits": [
        {"id": 9, "system": "Ega", "planet": "Ega 3", "spot": "2", "type": "Gold", "rigs": 1,
         "lat": 1.0, "lon": 1.0, "good_marks": 6, "bad_marks": 0}]}))
    check("a body's shared finds bring their site's counts with them",
          app.site_marks().counts_for("Ega", "Ega 3", "2") == (6, 0))
    app.take_landing(True, json.dumps({"system": "Ega", "sites": [
        {"system": "Ega", "planet": "Ega 4", "spot": "1", "rigs": 2, "types": ["Gold"],
         "good_marks": 0, "bad_marks": 2}]}))
    check("and so do a system's shared sites", app.site_marks().counts_for("Ega", "Ega 4", "1") == (0, 2))


if __name__ == "__main__":
    print()
    print("FAILURES:", len(fails))
    for f in fails:
        print("  -", f)
    try:
        app.destroy()
    except Exception:
        pass
    sys.exit(1 if fails else 0)
