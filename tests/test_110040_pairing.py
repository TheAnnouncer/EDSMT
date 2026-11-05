"""1.10040: EDSMT pairs with the commander's member page on radioraxxla.com.

The member page (sign in with Discord, then Tools) makes a pairing code such
as PWP4-ZQMA: eight letters and digits, one use, ten minutes. Typed into
Settings > Sharing > Radio Raxxla account, EDSMT hands it in and gets a token
back once. The token is a secret like every other key: behind dots nowhere,
never on the status line, never in the support bundle. Forget pairing drops
it here; the member page revokes it there.

Pure parts run anywhere; the window on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_pairing.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-pairing-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import pairing as PR          # noqa: E402
import supportbundle as SB    # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


TOKEN = "fake-pairing-token-" + "Q7" * 14   # made up; never a real one

print("== the code ==")
check("written any way, it is read the same", PR.normalise(" pwp4-zqma ") == "PWP4ZQMA"
      and PR.normalise("PWP4 ZQMA") == "PWP4ZQMA")
check("eight of the member page's letters and digits look right",
      PR.looks_right("PWP4-ZQMA") and PR.looks_right("pwp4zqma"))
for bad in ("", "PWP4-ZQM", "PWP4-ZQMA1", "PWP0-ZQMA", "PWPI-ZQMA", "PWP4_ZQMA"):
    check("%r does not" % bad, not PR.looks_right(bad))
check("shown as the member page shows it", PR.shown("pwp4zqma") == "PWP4-ZQMA")

print("== what is sent ==")
check("the device is named after the computer", PR.device_name("DESKTOP-ABC") == "EDSMT on DESKTOP-ABC")
check("no name: just EDSMT", PR.device_name("") == "EDSMT" and PR.device_name(None) == "EDSMT")
check("never more than the member page keeps", len(PR.device_name("X" * 200)) <= PR.NAME_MOST)
check("control characters are dropped", PR.device_name("PC\x00\n\tONE") == "EDSMT on PCONE",
      PR.device_name("PC\x00\n\tONE"))
body = PR.claim_body("pwp4-zqma", "EDSMT on PC")
check("the code, the tool and the device name - nothing else",
      body == {"code": "PWP4ZQMA", "tool": "edsmt", "device_name": "EDSMT on PC"}, body)
body = PR.claim_body("pwp4-zqma", "EDSMT on PC", cmdr="  The   Announcer ")
check("with the journal's commander name known, it goes too, tidied - so the member page never needs it typed",
      body == {"code": "PWP4ZQMA", "tool": "edsmt", "device_name": "EDSMT on PC", "cmdr": "The Announcer"}, body)
check("a name is never longer than the board allows", len(PR.claim_body("pwp4-zqma", "PC", cmdr="X" * 90)["cmdr"]) <= 40)
check("to the member page's own address", PR.CLAIM_URL == "https://join.radioraxxla.com/pair/claim")
check("and the member page itself, on its Tools tab", PR.PORTAL_URL == "https://radioraxxla.com/portal.html#tools")

print("== the answer ==")
asked = []


def fake_post(url, payload, timeout=20.0, headers=None):
    asked.append((url, payload))
    return {"ok": True, "token": TOKEN, "device_id": "a1b2c3d4e5f6", "tool": "edsmt"}


got = json.loads(PR.claim_job("PWP4-ZQMA", "EDSMT on PC", fake_post, cmdr="CMDR Bob")())
check("one call, to the claim address, the commander name with it",
      asked == [(PR.CLAIM_URL, PR.claim_body("PWP4-ZQMA", "EDSMT on PC", cmdr="CMDR Bob"))], asked)
check("the token and the device come back", got == {"token": TOKEN, "device": "a1b2c3d4e5f6"}, got)
for reply in ({}, {"token": "short", "device_id": "x"}, {"token": TOKEN}, {"device_id": "a1"}, [1, 2], None,
              {"token": TOKEN, "device_id": "a1b2c3d4e5f6", "tool": "edst"}):
    try:
        PR.read_claim(reply)
        refused = False
    except RuntimeError:
        refused = True
    check("an answer EDSMT cannot use is refused: %r" % (reply,), refused)
check("the member page's own words, without the HTTP wrapping",
      PR.explain("join.radioraxxla.com refused it (HTTP 400): That code is wrong or has expired. "
                 "Make a new one on your member page.")
      == "That code is wrong or has expired. Make a new one on your member page.")
check("no connection says so plainly", PR.explain("could not reach join.radioraxxla.com: timed out").startswith(
    "Could not reach the member page"), PR.explain("could not reach join.radioraxxla.com: timed out"))
check("anything else is passed on", PR.explain("odd") == "odd")
check("and never the token, whatever went wrong", TOKEN not in PR.explain("x %s y" % TOKEN))

print("== where it is kept ==")
check("the token is a secret", SB.is_secret_key("portal_token"))
check("paired only with a token", PR.paired({"portal_token": TOKEN}) and not PR.paired({})
      and not PR.paired({"portal_token": ""}) and not PR.paired(None))
check("forgetting clears both", PR.forget({"portal_token": TOKEN, "portal_device": "a1", "x": 1})
      == {"portal_token": "", "portal_device": "", "x": 1})

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the window needs a display (%s). Run it under xvfb-run." % _exc)

if HAVE_DISPLAY:
    import overlay as OV
    OV.foreground_is_game = lambda: None
    import edsmt as A
    import edonline as EDO
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
                   "welcome_seen_version": A.APP_VERSION}, handle)
    check("a new install is not paired", A.DEFAULT_SETTINGS.get("portal_token") == ""
          and A.DEFAULT_SETTINGS.get("portal_device") == "")

    app = A.EDSMT()
    app.geometry("1600x1000+0+0")
    app.updates.check = lambda *args, **kwargs: None

    def pump(times=3):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    class Worker:
        """Jobs run when the app drains it, as the real one hands them back."""
        def __init__(self):
            self.jobs = []

        def submit(self, tag, fn):
            self.jobs.append((tag, fn))

        def drain(self):
            out = []
            for tag, fn in self.jobs:
                try:
                    out.append((tag, True, fn() or ""))
                except Exception as exc:
                    out.append((tag, False, str(exc)))
            self.jobs = []
            return out

    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)

    def button(widget, text):
        return next((w for w in walk(widget) if isinstance(w, A.ctk.CTkButton)
                     and str(w.cget("text")) == text), None)

    def texts(widget):
        out = []
        for w in walk(widget):
            try:
                out.append(str(w.cget("text")))
            except Exception:
                pass
        return out

    def saved():
        with open(A.SETTINGS_FILE, encoding="utf-8") as handle:
            return json.load(handle)

    app.worker = Worker()
    said = []
    app.say = lambda text, colour=None: said.append(str(text))
    opened = []
    A.open_link = lambda url, *a, **k: opened.append(url) or True
    sent = []

    def answer(url, payload, timeout=20.0, headers=None):
        sent.append((url, payload))
        if payload.get("code") == "BBBBBBBB":
            raise RuntimeError("join.radioraxxla.com refused it (HTTP 400): That code is wrong "
                               "or has expired. Make a new one on your member page.")
        return {"ok": True, "token": TOKEN, "device_id": "a1b2c3d4e5f6", "tool": "edsmt"}

    EDO.post_json = answer

    win = A.SettingsWindow(app)
    pump(4)
    win.tabs.set("Sharing")
    pump(4)
    page = win.pages["Sharing"]
    words = texts(page)
    print("== Settings > Sharing > Radio Raxxla account ==")
    check("the section is there", "RADIO RAXXLA ACCOUNT" in words, [w for w in words if "RADIO" in w])
    check("a box for the code, Pair and Member page",
          isinstance(win.pair_code, A.ctk.CTkEntry) and button(page, "Pair") is not None
          and button(page, "Member page") is not None)
    check("not paired yet, and it says so", "Not paired" in win.pair_line.cget("text"), win.pair_line.cget("text"))
    check("nothing to forget yet", not win.pair_forget.winfo_ismapped())
    button(page, "Member page").invoke()
    check("Member page opens the Tools tab of the member page", opened[-1:] == [PR.PORTAL_URL], opened)

    wsaid = []
    win.say = lambda text, colour=None: wsaid.append(str(text))
    win.pair_code.insert(0, "PWP0-ZQMA")
    button(page, "Pair").invoke()
    check("a code that cannot be right is not sent", not app.worker.jobs and not sent, sent)
    check("and it says what a code looks like", wsaid and "PWP4-ZQMA" in wsaid[-1], wsaid)

    win.pair_code.delete(0, "end")
    win.pair_code.insert(0, "bbbb-bbbb")
    button(page, "Pair").invoke()
    before = len(said)
    app.collect_results()
    pump(2)
    check("a refusal is the member page's own words",
          any(t.startswith("That code is wrong") for t in said[before:]), said[before:])
    check("and nothing is kept", not app.settings.get("portal_token") and not saved().get("portal_token"))

    win.pair_code.delete(0, "end")
    win.pair_code.insert(0, "pwp4 zqma")
    button(page, "Pair").invoke()
    check("it waits for the worker, off the window", len(app.worker.jobs) == 1, app.worker.jobs)
    before = len(said)
    app.collect_results()
    pump(3)
    check("a right code goes as the tool edsmt, with the computer's name",
          sent[-1][0] == PR.CLAIM_URL and sent[-1][1]["code"] == "PWP4ZQMA"
          and sent[-1][1]["tool"] == "edsmt" and sent[-1][1]["device_name"].startswith("EDSMT"), sent[-1:])
    check("the token is kept and written", app.settings.get("portal_token") == TOKEN
          and saved().get("portal_token") == TOKEN and saved().get("portal_device") == "a1b2c3d4e5f6")
    check("it says Paired", any(t.startswith("Paired") for t in said[before:]), said[before:])
    check("and never shows the token", not any(TOKEN in t for t in said + wsaid + texts(win)), said[-2:])
    check("the box is cleared", win.pair_code.get() == "")
    check("Settings says paired", win.pair_line.cget("text").startswith("Paired"), win.pair_line.cget("text"))
    check("Forget pairing is offered", win.pair_forget.winfo_ismapped())
    check("the support bundle hides it", TOKEN not in json.dumps(SB.clean_settings(app.settings))
          and TOKEN in SB.secret_values(app.settings))

    win.save()
    pump(2)
    check("saving Settings keeps the pairing", saved().get("portal_token") == TOKEN)

    win.pair_forget.invoke()
    pump(2)
    check("Forget pairing drops it here", not app.settings.get("portal_token") and not saved().get("portal_token")
          and not saved().get("portal_device"))
    check("and Settings says not paired", "Not paired" in win.pair_line.cget("text"))
    try:
        win.destroy()
        app.destroy()
    except Exception:
        pass

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
