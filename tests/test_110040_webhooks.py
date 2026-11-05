"""1.10040: several Discord webhooks of the commander's own (#315).

Asked on 29 Oct: "we need to also be able to add multi discord webhooks for
example I have 'The Announcer' and also 'Radio Raxxla' discords I would like
to post it in".

- Up to five webhooks, each with a name, its address and three switches:
  Finds, Sessions, Session map. Test and Remove on each row, Add a webhook
  under the list.
- A settings file with the one webhook of 1.10039 becomes one entry named
  "My Discord" with the switches it had; the old keys go.
- A find goes to every webhook with Finds on; a session summary to every
  one with Sessions on, and the message edited after the sale is that
  webhook's own message. One webhook failing is named and stops nothing.
- Every address is a secret wherever the single one was: the support
  bundle, the crash log and the notes on the controls.
- Settings says, in one line, that every find also reaches the Radio Raxxla
  Discord through the community map, with a Join the Discord button. The
  app never holds that channel's webhook.

Pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_webhooks.py
"""
import os, sys, json, tempfile, time, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-hooks40-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import webhooks as WH        # noqa: E402

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


def hook(ident, letter):
    """A webhook address with the shape of a real one. Made up."""
    return "https://discord.com/api/webhooks/%s/%s" % (ident, letter * 6 + "Zq-9_" + letter * 57)


HOOK_A = hook("112233445566778899", "a")
HOOK_B = hook("223344556677889900", "b")
HOOK_C = hook("334455667788990011", "c")
HOOK_D = hook("445566778899001122", "d")


@section("an older settings file: its one webhook becomes one entry")
def _upgrade():
    old = {"discord_webhook": HOOK_A, "discord_post_finds": True, "discord_post_sessions": False,
           "discord_attach_map": False, "discord_finds_level": 1, "inara_enabled": True}
    up = WH.upgrade(dict(old), old)
    check("one entry named My Discord, with the address it had",
          len(up["discord_webhooks"]) == 1 and up["discord_webhooks"][0]["name"] == "My Discord"
          and up["discord_webhooks"][0]["url"] == HOOK_A, up.get("discord_webhooks"))
    check("and the switches it had - nothing it posted stops, nothing new starts",
          {k: up["discord_webhooks"][0][k] for k in ("finds", "sessions", "map")}
          == {"finds": True, "sessions": False, "map": False}, up["discord_webhooks"])
    check("the old keys are gone", not [k for k in ("discord_webhook", "discord_post_finds",
                                                    "discord_post_sessions", "discord_attach_map",
                                                    "discord_finds_level") if k in up], sorted(up))
    check("and nothing else is touched", up["inara_enabled"] is True)
    first = {"discord_webhook": HOOK_A}
    up = WH.upgrade(dict(first), first)
    check("a 1.10034 file (no switches written) keeps posting summaries with the map, not finds",
          {k: up["discord_webhooks"][0][k] for k in ("finds", "sessions", "map")}
          == {"finds": False, "sessions": True, "map": True}, up["discord_webhooks"])
    pre35 = {"discord_webhook": HOOK_A, "discord_post_finds": True}
    check("one from before 1.10035 that had finds on by default has them off, as 1.10035 decided",
          WH.upgrade(dict(pre35), pre35)["discord_webhooks"][0]["finds"] is False)
    none = {"discord_webhook": "", "discord_post_finds": True}
    up = WH.upgrade(dict(none), none)
    check("a file that never had a webhook gets an empty list", up["discord_webhooks"] == []
          and "discord_post_finds" not in up, up)
    check("so does a first start", WH.upgrade({}, {})["discord_webhooks"] == [])
    listed = {"discord_webhooks": [{"name": "Radio Raxxla", "url": HOOK_B, "finds": True,
                                    "sessions": False, "map": False}]}
    up = WH.upgrade(json.loads(json.dumps(listed)), listed)
    check("a file that already has the list keeps it exactly", up["discord_webhooks"] == listed["discord_webhooks"],
          up["discord_webhooks"])


@section("the list as the app reads it")
def _clean():
    rows = WH.clean([{"name": "", "url": HOOK_A}, "junk", {"name": " The Announcer ", "url": HOOK_B,
                                                           "finds": 1, "sessions": 0}]
                    + [{"url": HOOK_C}] * 6)
    check("at most five rows", len(rows) == WH.MAX_HOOKS == 5, len(rows))
    check("a blank name reads Discord N, by its place in the list",
          rows[0]["name"] == "Discord 1" and rows[2]["name"] == "Discord 3", [r["name"] for r in rows])
    check("names are trimmed, switches are true or false",
          rows[1] == {"name": "The Announcer", "url": HOOK_B, "finds": True, "sessions": False, "map": True,
                      "card": False}, rows[1])
    check("anything that is not a list is no webhooks", WH.clean("x") == [] and WH.clean(None) == [])
    ok = lambda url: url.startswith("https://discord.com/api/webhooks/")
    three = [WH.entry("One", HOOK_A, finds=True), WH.entry("Two", HOOK_B, finds=False),
             WH.entry("Three", HOOK_C, finds=True), WH.entry("Four", "https://example.com/x", finds=True)]
    check("a find goes to the rows with Finds on and an address that is a webhook",
          [r["name"] for r in WH.wanted(three, "finds", ok)] == ["One", "Three"])
    check("a key for each webhook that is not its address, and the same every time",
          WH.hook_key(HOOK_A) == WH.hook_key(HOOK_A + "/") and WH.hook_key(HOOK_A) != WH.hook_key(HOOK_B)
          and "112233445566778899" not in WH.hook_key(HOOK_A) and len(WH.hook_key(HOOK_A)) == 16
          and WH.hook_key("") == "")


# ---------------------------------------------------------------------------
# The app, on the real toolkit
# ---------------------------------------------------------------------------
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % _exc)
    print("\nFAILURES:", len(fails))
    sys.exit(1 if fails else 0)

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
import edonline as EDO   # noqa: E402
import sessionledger as SL  # noqa: E402
import supportbundle as SB  # noqa: E402
import survey as SV      # noqa: E402
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
# The settings file of a commander coming from 1.10039: one webhook, finds on.
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
               "welcome_seen_version": A.APP_VERSION,
               "discord_webhook": HOOK_A, "discord_post_finds": True, "discord_post_sessions": True,
               "discord_attach_map": True, "discord_finds_level": 1}, _f)


@section("1.10039's settings file, read by the app")
def _loaded():
    data = A.load_settings()
    check("the webhook is one entry named My Discord, finds still on",
          data.get("discord_webhooks") == [WH.entry("My Discord", HOOK_A, finds=True, sessions=True, map=True)],
          data.get("discord_webhooks"))
    check("and no old key is left", not [k for k in WH.OLD_KEYS if k in data], [k for k in WH.OLD_KEYS if k in data])
    check("a new install starts with no webhooks", A.DEFAULT_SETTINGS.get("discord_webhooks") == []
          and not [k for k in WH.OLD_KEYS if k in A.DEFAULT_SETTINGS])


# A session posted by 1.10039, before the update, and not yet sold: its
# message is kept under the session alone. The app has to know it is My
# Discord's, or the sale would never be edited into it.
OLD_SID, OLD_MESSAGE = "0190aaaabbbb001", "887766554433221100"
with open(os.path.join(A.DATA_DIR, SL.POSTS_FILE), "w", encoding="utf-8") as _f:
    json.dump({OLD_SID: {"id": OLD_MESSAGE, "attachments": [], "when": time.time() - 600,
                         "state": [0], "seen_state": [0], "changed_at": time.time() - 600,
                         "edited_at": 0.0, "edits": 0, "dead": False, "image": ""}}, _f)

app = A.EDSMT()
app.geometry("1600x1000+0+0")
app.updates.check = lambda *args, **kwargs: None


def pump(times=3):
    for _ in range(times):
        app.update_idletasks()
        app.update()


class Worker:
    """Stands in for the app's worker: jobs wait until run(), and come back
    the way the real one hands them back - (tag, ok, message)."""
    def __init__(self):
        self.jobs = []

    def submit(self, tag, fn):
        self.jobs.append((tag, fn))

    def run(self):
        out = []
        for tag, fn in self.jobs:
            try:
                out.append((tag, True, fn() or ""))
            except Exception as exc:
                out.append((tag, False, str(exc)))
        self.jobs = []
        return out


SENT, EDITS = [], []
_ids = iter(range(900000000000000001, 900000000000009999))
DEAD = set()


def _refused(url):
    if any(url.startswith(dead) for dead in DEAD):
        raise RuntimeError("discord.com refused it (HTTP 404): Unknown Webhook")


def _post_json(url, payload, timeout=20.0, headers=None):
    _refused(url)
    SENT.append(("POST", url.split("?")[0], payload))
    return {"id": str(next(_ids)), "attachments": []}


def _post_file(url, payload, filename, data, timeout=40.0):
    _refused(url)
    SENT.append(("POST-FILE", url.split("?")[0], payload))
    return {"id": str(next(_ids)), "attachments": [{"id": "5550001", "filename": filename}]}


def _edit(url, message_id, payload, keep=(), timeout=20.0):
    _refused(url)
    EDITS.append((url, str(message_id), payload, list(keep)))
    return {"id": message_id}


EDO.post_json, EDO.discord_post_file, EDO.discord_edit = _post_json, _post_file, _edit
said = []
_real_say = app.say
app.say = lambda text, colour=None: said.append(str(text))


@section("a message posted before the update is still My Discord's to edit")
def _claimed():
    key = SL.post_key(OLD_SID, WH.hook_key(HOOK_A))
    check("the 1.10039 post is now filed under My Discord's webhook",
          key in app.post_book.posted and app.post_book.posted[key]["id"] == OLD_MESSAGE
          and OLD_SID not in app.post_book.posted, sorted(app.post_book.posted))


@section("a find goes to every webhook with Finds on, and only those")
def _finds():
    app.settings["discord_webhooks"] = [WH.entry("One", HOOK_A, finds=True),
                                        WH.entry("Two", HOOK_B, finds=False),
                                        WH.entry("Three", HOOK_C, finds=True)]
    app.worker = Worker()
    del SENT[:]
    record = {"commodity": "Monazite", "rigs": "4", "system": "Ega", "body": "Ega 1",
              "location": "3", "amount": "High", "density": "Medium", "lat": "1.5", "lon": "2.5"}
    check("one job per webhook with Finds on", app.post_discord_find(record) and len(app.worker.jobs) == 2,
          len(app.worker.jobs))
    for tag, ok, message in app.worker.run():
        app.take_discord(tag, ok, message)
    check("the two of three with Finds on got it, the third did not",
          sorted(url for _k, url, _p in SENT) == sorted([HOOK_A, HOOK_C]), [u[-12:] for _k, u, _p in SENT])
    check("the same find in each", len({json.dumps(p, sort_keys=True) for _k, _u, p in SENT}) == 1)
    del SENT[:], said[:]
    DEAD.add(HOOK_C)
    app.post_discord_find(record)
    results = app.worker.run()
    for tag, ok, message in results:
        app.take_discord(tag, ok, message)
    DEAD.clear()
    check("one webhook failing does not stop the other", [u for _k, u, _p in SENT] == [HOOK_A], SENT)
    check("and the one that failed is named", any("Three" in s and "did not take it" in s for s in said), said)
    check("never by its address", not any(HOOK_C in s or "334455667788990011" in s for s in said), said)
    app.settings["discord_webhooks"] = [WH.entry("Two", HOOK_B, finds=False)]
    check("with no webhook taking finds, nothing is posted",
          app.post_discord_find(record) is False and app.worker.jobs == [])


def session_world(tag):
    folder = os.path.join(TMP, "flow-" + tag)
    os.makedirs(folder, exist_ok=True)
    app.earnings = SV.Earnings(folder)
    app.extras = SL.SessionLedger(folder)
    app.post_book = SL.PostBook(folder)
    app.worker = Worker()
    app._discord_seen = None
    app._pictures = []
    return folder


@section("a session goes to every webhook with Sessions on; each edit to its own message")
def _sessions():
    folder = session_world("a")
    app.settings["discord_webhooks"] = [WH.entry("One", HOOK_A, sessions=True, map=True),
                                        WH.entry("Two", HOOK_B, sessions=True, map=False),
                                        WH.entry("Three", HOOK_C, sessions=False)]
    app.settings["discord_edit_after_sale"] = True
    app.post_discord_sessions()                     # the first look: nothing closed yet
    live = app.earnings.start("Col 1 Sector AA-A c1-1", "Col 1 Sector AA-A c1-1 BC 2", "Jameson",
                              when=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3 * 3600)))
    ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 60))
    live.update({"mined": "Iridium:707", "ended": ended, "closed": ended})
    app.earnings.save()
    picture = os.path.join(folder, "map.png")
    with open(picture, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n" + b"x" * 4000)
    app._pictures = [(time.time() - 60, picture)]
    del SENT[:]
    sid = str(live["id"])
    check("one post for each webhook with Sessions on", app.post_discord_sessions() == 2
          and len(app.worker.jobs) == 2, len(app.worker.jobs))
    results = app.worker.run()
    for tag, ok, message in results:
        app.take_discord(tag, ok, message)
    posted = {url: kind for kind, url, _p in SENT}
    check("the third, with Sessions off, got nothing", HOOK_C not in posted and len(posted) == 2, posted)
    check("the map picture went to the one with Session map on, not to the other",
          posted.get(HOOK_A) == "POST-FILE" and posted.get(HOOK_B) == "POST", posted)
    key_a, key_b = SL.post_key(sid, WH.hook_key(HOOK_A)), SL.post_key(sid, WH.hook_key(HOOK_B))
    entry_a, entry_b = app.post_book.posted.get(key_a), app.post_book.posted.get(key_b)
    check("each webhook keeps its own message id",
          entry_a and entry_b and entry_a["id"] and entry_b["id"] and entry_a["id"] != entry_b["id"],
          (entry_a, entry_b))
    check("never a second post, however often the tick asks",
          all(app.post_discord_sessions() == 0 for _ in range(3)) and app.worker.jobs == [])
    # The sale comes in.
    live.update({"sold": "Iridium:690", "credits": "134232600", "sales": "1"})
    for entry in (entry_a, entry_b):
        entry["changed_at"] = time.time() - SL.EDIT_QUIET_S - 1
        entry["seen_state"] = app.discord_state(live)
    del EDITS[:]
    app.post_discord_sessions()
    app.worker.run()
    pairs = sorted((url, mid) for url, mid, _p, _k in EDITS)
    check("after the sale, each webhook's own message is edited - and no other",
          pairs == sorted([(HOOK_A, entry_a["id"]), (HOOK_B, entry_b["id"])]), pairs)
    check("the one with the picture keeps it", [k for u, _m, _p, k in EDITS if u == HOOK_A] == [["5550001"]],
          EDITS)


@section("a session to a webhook that fails: named, and the others still post")
def _session_fails():
    session_world("b")
    app.settings["discord_webhooks"] = [WH.entry("One", HOOK_A), WH.entry("Two", HOOK_B)]
    app.post_discord_sessions()
    live = app.earnings.start("Ega", "Ega 1", "Jameson",
                              when=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7200)))
    ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 30))
    live.update({"mined": "Painite:200", "ended": ended, "closed": ended})
    del SENT[:], said[:]
    DEAD.add(HOOK_B)
    app.post_discord_sessions()
    for tag, ok, message in app.worker.run():
        app.take_discord(tag, ok, message)
    DEAD.clear()
    check("the good one posted", [u for _k, u, _p in SENT] == [HOOK_A], SENT)
    check("the bad one is named", any("Two" in s and "did not take it" in s for s in said), said)
    check("never by its address", not any(HOOK_B in s or "223344556677889900" in s for s in said), said)
    sid = str(live["id"])
    check("and the good one's message is kept",
          app.post_book.posted[SL.post_key(sid, WH.hook_key(HOOK_A))]["id"] != "")


def walk(widget):
    out = [widget]
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        out += walk(child)
    return out


def texts_in(widget):
    found = []
    for w in walk(widget):
        try:
            text = w.cget("text")
        except Exception:
            continue
        if isinstance(text, str) and text:
            found.append(text)
    return found


def shown(widget):
    try:
        return bool(widget.winfo_manager()) and bool(widget.winfo_ismapped())
    except Exception:
        return False


@section("Settings -> Discord: the community line, then your own webhooks as rows")
def _settings():
    import webbrowser
    app.settings["discord_webhooks"] = [WH.entry("The Announcer", HOOK_A, finds=True, map=False),
                                        WH.entry("Radio Raxxla", HOOK_B)]
    app.worker = Worker()
    win = A.SettingsWindow(app)
    pump(4)
    win.tabs.set("Sharing")
    pump(4)
    wsaid, saved = [], []
    win.say = lambda text, colour=None: wsaid.append(str(text))
    real_apply = app.apply_settings
    app.apply_settings = lambda data: saved.append(json.loads(json.dumps(data)))
    try:
        texts = texts_in(win.pages["Sharing"])
        check("the line about the community feed, word for word",
              "Every find also appears in #edsmt-finds on the Radio Raxxla Discord, posted by the "
              "community map - nothing to set up." in texts, [t for t in texts if "edsmt" in t])
        opened = []
        real_open = webbrowser.open
        webbrowser.open = lambda url, *a, **k: opened.append(url) or True
        try:
            join = [w for w in walk(win.pages["Sharing"])
                    if isinstance(w, A.ctk.CTkButton) and w.cget("text") == "Join the Discord"]
            check("with a Join the Discord button", len(join) == 1, len(join))
            if join:
                join[0].invoke()
        finally:
            webbrowser.open = real_open
        check("that opens the invite", opened == ["https://discord.gg/DjH9uZabet"], opened)
        import re
        held = [name for name in os.listdir(REPO) if name.endswith(".py")
                and re.search(r"discord(?:app)?\.com/api/webhooks/\d",
                              open(os.path.join(REPO, name), encoding="utf-8").read())]
        check("the app holds no webhook address at all - the community channel's lives on the server",
              not held, held)
        rows = win.hook_rows
        check("one row for each webhook, in order, with its name and address",
              [(r["name"].get(), r["url"].get()) for r in rows] == [("The Announcer", HOOK_A), ("Radio Raxxla", HOOK_B)],
              [(r["name"].get(), r["url"].get()[-6:]) for r in rows])
        check("and its own switches: Finds, Sessions, Session map, Session card (1.10040, #151)",
              {k: v.get() for k, v in rows[0]["vars"].items()} == {"finds": True, "sessions": True, "map": False,
                                                                  "card": False},
              {k: v.get() for k, v in rows[0]["vars"].items()})
        check("every address is dots", all(r["url"]._entry.cget("show") == A.MASK for r in rows),
              [r["url"]._entry.cget("show") for r in rows])
        rows[1]["show"].invoke(); pump(2)
        check("Show shows that one only", rows[1]["url"]._entry.cget("show") == ""
              and rows[0]["url"]._entry.cget("show") == A.MASK)
        rows[1]["show"].invoke(); pump(2)
        check("and Hide hides it", rows[1]["url"]._entry.cget("show") == A.MASK)
        check("Add a webhook is there under two", shown(win.hook_add))
        for _ in range(3):
            win.hook_add.invoke(); pump(2)
        check("up to five", len(win.hook_rows) == 5, len(win.hook_rows))
        check("and then Add a webhook is gone", not shown(win.hook_add))
        win.add_hook_row(); pump(1)
        check("a sixth is never made", len(win.hook_rows) == 5)
        check("a new row's switches are a summary with its map, no card",
              {k: v.get() for k, v in win.hook_rows[2]["vars"].items()}
              == {"finds": False, "sessions": True, "map": True, "card": False})
        win.hook_rows[4]["remove"].invoke(); pump(2)
        check("Remove takes that row away", len(win.hook_rows) == 4)
        check("and Add a webhook is back", shown(win.hook_add))
        # Test on a row that has not been saved: what is in its box goes.
        third = win.hook_rows[2]
        third["name"].insert(0, "Squadron")
        third["url"].insert(0, HOOK_D)
        pump(1)
        check("an address typed into a new row is dots as it is typed",
              third["url"]._entry.cget("show") == A.MASK, third["url"]._entry.cget("show"))
        del SENT[:], said[:]
        third["test"].invoke(); pump(1)
        check("Test posts one message, to that row's webhook only",
              [t for t, _f in app.worker.jobs] == [EDO.DISCORD_TEST_TAG], app.worker.jobs)
        for tag, ok, message in app.worker.run():
            app.take_discord(tag, ok, message)
        check("saved or not", [u for _k, u, _p in SENT] == [HOOK_D], SENT)
        check("and Discord taking it is said, with the row's name",
              any("Squadron" in s and "took the test message" in s for s in said), said)
        DEAD.add(HOOK_D)
        third["test"].invoke(); pump(1)
        for tag, ok, message in app.worker.run():
            app.take_discord(tag, ok, message)
        DEAD.clear()
        check("a test Discord refuses is said, with the name and never the address",
              any("Squadron" in s and "did not take it" in s for s in said)
              and not any(HOOK_D in s for s in said), said)
        fourth = win.hook_rows[3]
        fourth["test"].invoke(); pump(1)
        check("Test with nothing in the box asks for the address", wsaid and "Paste the webhook URL first" in wsaid[-1],
              wsaid[-1:])
        fourth["url"].insert(0, "https://example.com/api/webhooks/1/abc")
        fourth["test"].invoke(); pump(1)
        check("and with something that is not a webhook says so, and sends nothing",
              "That is not a Discord webhook address." in wsaid[-1] and app.worker.jobs == [], wsaid[-1:])
        win.save(); pump(1)
        check("Save refuses it with the same words as before, naming the row",
              not saved and "Discord 4: That is not a Discord webhook address. In Discord: channel settings "
              "> Integrations > Webhooks > Copy Webhook URL." == wsaid[-1], wsaid[-1:])
        fourth["url"].delete(0, "end")
        fourth["url"].insert(0, HOOK_C.replace("discord.com", "discordapp.com"))
        fourth["vars"]["finds"].set(True)
        win.save(); pump(1)
        check("a good list is saved", bool(saved), wsaid[-1:])
        if saved:
            got = saved[-1]["discord_webhooks"]
            check("with every row, its name, address and switches - a blank name is Discord N",
                  got == [WH.entry("The Announcer", HOOK_A, finds=True, map=False),
                          WH.entry("Radio Raxxla", HOOK_B),
                          WH.entry("Squadron", HOOK_D),
                          WH.entry("Discord 4", HOOK_C.replace("discord.com", "discordapp.com"), finds=True)],
                  got)
            check("and no old key comes back", not [k for k in WH.OLD_KEYS if k in saved[-1]])
        everything = walk(win)
        notes = [str(getattr(w, "_edsmt_tip", "")) for w in everything]
        words = texts_in(win)
        check("no note on any control holds an address, or any part of one",
              not [n for n in notes if "api/webhooks/" in n or "112233445566778899" in n or "aaaaaaZq" in n])
        check("nor any label or button", not [t for t in words if "api/webhooks/1" in t or "aaaaaaZq" in t])
        check("every control the rows add has a note",
              all(getattr(w, "_edsmt_tip", "") for r in win.hook_rows
                  for w in (r["name"], r["url"], r["show"], r["test"], r["remove"], *r["switches"].values())))
        app.settings["discord_webhooks"] = [WH.entry("Only", HOOK_B)]
        win.load(); pump(2)
        check("loading Settings again shows the list as it is now",
              [r["name"].get() for r in win.hook_rows] == ["Only"]
              and win.hook_rows[0]["url"]._entry.cget("show") == A.MASK)
        win.add_hook_row(); win.add_hook_row(); pump(1)
        win.hook_rows[0]["remove"].invoke(); pump(1)
        check("a blank name's hint follows its place when one above it goes",
              [r["name"].cget("placeholder_text") for r in win.hook_rows] == ["Discord 1", "Discord 2"],
              [r["name"].cget("placeholder_text") for r in win.hook_rows])
    finally:
        app.apply_settings = real_apply
        win.destroy()
        pump(2)


TOKEN_A = HOOK_A.rsplit("/", 1)[1]
TOKEN_B = HOOK_B.rsplit("/", 1)[1]


@section("every address is a secret: the support bundle")
def _bundle():
    settings = dict(A.DEFAULT_SETTINGS, discord_webhooks=[
        WH.entry("The Announcer", HOOK_A, finds=True), WH.entry("Radio Raxxla", HOOK_B), WH.entry("Spare", "")])
    folder = os.path.join(TMP, "support-data")
    os.makedirs(folder)
    with open(os.path.join(folder, "crash.log"), "w", encoding="utf-8") as handle:
        handle.write("Traceback (most recent call last):\nRuntimeError: could not post to %s\n"
                     "and the token on its own: %s\n" % (HOOK_A, TOKEN_B))
    with open(os.path.join(folder, "app.log"), "w", encoding="utf-8") as handle:
        handle.write("2026-10-29 12:00:00  Discord did not take it: refused %s\n" % HOOK_B)
    bundle = SB.make_bundle(os.path.join(TMP, "support-out"), folder, settings, "1.10040", "installed")
    with zipfile.ZipFile(bundle) as z:
        members = {n: z.read(n).decode("utf-8", "replace") for n in z.namelist()}
    everything = "\n".join(members.values())
    for label, value in (("first address", HOOK_A), ("second address", HOOK_B),
                         ("first token", TOKEN_A), ("second token", TOKEN_B)):
        check("the %s is nowhere in the zip" % label, value not in everything)
    out = json.loads(members["settings.json"])["discord_webhooks"]
    check("the settings in it keep each webhook's name and switches, the address reads [removed]",
          out == [dict(WH.entry("The Announcer", "", finds=True), url="[removed]"),
                  dict(WH.entry("Radio Raxxla", ""), url="[removed]"), WH.entry("Spare", "")], out)
    check("the list is a secret by its name", SB.is_secret_key("discord_webhooks")
          and "discord_webhooks" in SB.SECRET_KEYS)
    check("and every address and token in it is searched for",
          {HOOK_A, HOOK_B, TOKEN_A, TOKEN_B} <= set(SB.secret_values(settings)))


@section("every address is a secret: the crash log")
def _crash():
    app.settings["discord_webhooks"] = [WH.entry("The Announcer", HOOK_A), WH.entry("Radio Raxxla", HOOK_B)]
    log = os.path.join(A.DATA_DIR, "crash.log")
    if os.path.exists(log):
        os.remove(log)
    try:
        raise RuntimeError("could not post to %s (token %s)" % (HOOK_A, TOKEN_B))
    except RuntimeError as exc:
        app.trouble("Discord", exc)
    try:
        raise ValueError("a callback with %s in it" % HOOK_B)
    except ValueError as exc:
        app._callback_failed(type(exc), exc, exc.__traceback__)
    text = open(log, encoding="utf-8").read()
    check("the fault is written down", "RuntimeError" in text and "ValueError" in text and "Traceback" in text,
          text[:200])
    check("without any address or token in it",
          not [v for v in (HOOK_A, HOOK_B, TOKEN_A, TOKEN_B) if v in text], text)
    check("and what is on the status line has none either",
          not [s for s in said if HOOK_A in s or HOOK_B in s or TOKEN_B in s], said[-3:])


print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
