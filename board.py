"""The community leaderboard: what the window shows, worked out from the
server's answer (1.10036).

Pure logic: no Tk, no network. Every commander who shares a find is on
the board until they press Leave (finds always carry the CMDR name). The
seasons are the week since the Powerplay tick (Thursday 07:00 UTC), calendar
months in UTC, and all time. Powerplay merits the game paid for mined cargo
sit beside the points - they are not points - with totals per Power.
"""
import datetime as dt
import json

SEASONS = (("This week", "week"), ("This month", ""), ("Last month", "previous"),
           ("All time", "all"))
VIEWS = (("By points", "points"), ("By Powerplay merits", "merits"))
HEADERS = ("Rank", "Commander", "Power", "Points", "Merits", "Finds",
           "First on a body", "Confirmed", "Old sites seen", "Worked-out reports",
           "Regrowth", "Rig layouts")
# The Powerplay week turns at the cycle tick, Thursday 07:00 UTC.
TICK_WEEKDAY, TICK_HOUR = 3, 7
ROW_LIMIT = 50
WEB_PAGE = "https://api.radioraxxla.com/leaderboard"
LIVE_PAGE = "https://api.radioraxxla.com/live"

# What the server gives, said the way a commander reads it. Kept here as
# well as on the server so the window can say it before any answer comes.
POINTS = {"find": 10, "complete": 2, "first_body": 15, "verified": 5,
          "report": 3, "agreed": 2, "layout": 5, "confirmed_old": 3,
          "regrowth": 5}

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def week_start(now=None):
    """The last Powerplay tick at or before `now`."""
    now = now or dt.datetime.now(dt.timezone.utc)
    tick = now.replace(hour=TICK_HOUR, minute=0, second=0, microsecond=0)
    tick -= dt.timedelta(days=(now.weekday() - TICK_WEEKDAY) % 7)
    if tick > now:
        tick -= dt.timedelta(days=7)
    return tick


def season_now(now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    return now.strftime("%Y-%m")


def previous_season(season):
    try:
        year, month = int(season[:4]), int(season[5:7])
    except (TypeError, ValueError):
        return ""
    year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return "%04d-%02d" % (year, month)


def season_for(choice, now=None):
    """The season to ask for: "week", "" (this month), "all", or "YYYY-MM"."""
    wanted = dict(SEASONS).get(choice, choice)
    if wanted == "previous":
        return previous_season(season_now(now))
    return wanted or ""


def season_words(season, now=None, start=""):
    """"October 2026", "all time", "the week since the tick on Thursday 22
    October" (`start` is the server's week_start when it gave one)."""
    season = str(season or "") or season_now(now)
    if season == "all":
        return "all time"
    if season == "week":
        tick = None
        try:
            tick = dt.datetime.fromisoformat(str(start).replace("Z", "+00:00")) if start else None
        except ValueError:
            tick = None
        tick = tick or week_start(now)
        return "the week since the tick on %s %d %s" % (
            ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
             "Sunday")[tick.weekday()], tick.day, MONTHS[tick.month - 1])
    try:
        return "%s %s" % (MONTHS[int(season[5:7]) - 1], season[:4])
    except (ValueError, IndexError):
        return season


def points_words(points=None):
    """One line saying how points are given."""
    p = dict(POINTS)
    if isinstance(points, dict):
        p.update({k: _int(v, p.get(k, 0)) for k, v in points.items() if k in p})
    return ("Points: %(find)d a find, +%(complete)d when it has rigs, amount and "
            "density, +%(first_body)d for the first find on a body, "
            "+%(verified)d when staff confirm it, %(confirmed_old)d for seeing "
            "a site nobody had seen for a week, %(report)d a worked-out report "
            "(+%(agreed)d when another commander agrees), %(regrowth)d for "
            "finding a worked-out deposit grown back, %(layout)d a shared rig "
            "layout." % p)


def parse(message):
    """The server's answer as a dict, or None when it is not one."""
    if isinstance(message, dict):
        return message
    try:
        data = json.loads(message)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def same_name(a, b):
    return str(a or "").strip().lower() == str(b or "").strip().lower() != ""


def cells(answer, cmdr=""):
    """The table rows as cells (text, colour key, sort key). Colour keys are
    "you" for the commander's own row, else "". The commander's own row is
    added at the bottom when it is outside the rows shown."""
    rows = [r for r in (answer or {}).get("rows") or () if isinstance(r, dict)]
    you = (answer or {}).get("you")
    out = []
    shown = False
    for r in rows + ([you] if isinstance(you, dict) else []):
        mine = same_name(r.get("cmdr"), cmdr)
        if mine and shown:
            continue
        if r is you and not mine:
            continue
        shown = shown or mine
        tone = "you" if mine else ""
        rank = _int(r.get("rank"))
        out.append([("%d" % rank if rank else "-", tone, rank or 10 ** 6),
                    (str(r.get("cmdr") or ""), tone, str(r.get("cmdr") or "").lower()),
                    (str(r.get("power") or "-"), tone, str(r.get("power") or "~").lower()),
                    ("{:,}".format(_int(r.get("points"))), tone, _int(r.get("points"))),
                    ("{:,}".format(_int(r.get("merits"))), tone, _int(r.get("merits"))),
                    ("%d" % _int(r.get("finds")), tone, _int(r.get("finds"))),
                    ("%d" % _int(r.get("first_bodies")), tone, _int(r.get("first_bodies"))),
                    ("%d" % _int(r.get("verified")), tone, _int(r.get("verified"))),
                    ("%d" % _int(r.get("confirmations")), tone, _int(r.get("confirmations"))),
                    ("%d" % _int(r.get("reports")), tone, _int(r.get("reports"))),
                    ("%d" % _int(r.get("regrowth")), tone, _int(r.get("regrowth"))),
                    ("%d" % _int(r.get("layouts")), tone, _int(r.get("layouts")))])
    return out


def you_words(answer, cmdr="", opted=False, sharing=True):
    """The line about the commander's own place, or how to get one."""
    answer = answer or {}
    if not str(cmdr or "").strip():
        return "Your CMDR name is read from the journal - start the game once and it shows here."
    if not opted:
        return "You left the board. Join puts %s back on it." % cmdr
    you = answer.get("you")
    if isinstance(you, dict) and _int(you.get("rank")):
        line = "%s: number %d of %d this season, %s points" % (
            cmdr, _int(you.get("rank")), max(_int(answer.get("ranked")), _int(you.get("rank"))),
            "{:,}".format(_int(you.get("points"))))
        if _int(you.get("merits")):
            line += ", %s merits for %s" % ("{:,}".format(_int(you.get("merits"))),
                                            you.get("power") or "your Power")
        return line + "."
    return "%s is on the board - no points this season yet." % cmdr


def board_words(answer, now=None):
    """The headline: which season, and how many are on the board."""
    answer = answer or {}
    if answer.get("missing"):
        return "The community server has no leaderboard yet - it arrives with the next server update."
    season = season_words(answer.get("season"), now, answer.get("week_start"))
    on = _int(answer.get("commanders"))
    ranked = _int(answer.get("ranked"))
    if not on:
        return "Nobody has joined the board yet - %s." % season
    return "%s: %d commander%s on the board, %d %s." % (
        season[:1].upper() + season[1:], on, "" if on == 1 else "s", ranked,
        "with merits" if answer.get("sort") == "merits" else "with points")


def powers_words(answer, now=None):
    """One line: merits paid for mined cargo this season, per Power."""
    answer = answer or {}
    if answer.get("missing"):
        return ""
    powers = [p for p in answer.get("powers") or () if isinstance(p, dict)
              and _int(p.get("merits")) > 0 and str(p.get("power") or "").strip()]
    season = season_words(answer.get("season"), now, answer.get("week_start"))
    if not powers:
        return "Powers: no merits from mining for %s yet." % season
    return "Powers, %s, merits from mining: %s." % (season, "  |  ".join(
        "%s %s (%d CMDR%s)" % (p["power"], "{:,}".format(_int(p.get("merits"))),
                               _int(p.get("commanders")),
                               "" if _int(p.get("commanders")) == 1 else "s")
        for p in powers))


def merits_report(note, power, cmdr):
    """What goes to the board when the game pays merits for a sale of mined
    cargo: None when there is nothing to send."""
    note = note or {}
    name, power = str(cmdr or "").strip(), str(power or "").strip()
    merits = _int(note.get("merits"))
    when = str(note.get("when") or "").strip()
    if not (name and power and merits > 0 and len(when) >= 10):
        return None
    return {"cmdr": name, "power": power, "merits": merits, "when": when}


def should_send(settings, cmdr, sent, tell_off=False):
    """(send, on) for the commander in the journal now. On goes once a
    session for each commander who wants the board; off goes only after the
    switch was turned off (`tell_off`), once for each commander seen after.
    `sent` is {lower name: on} of what went."""
    name = str(cmdr or "").strip()
    if not name:
        return (False, False)
    wanted = bool(settings.get("leaderboard_optin", True))
    already = sent.get(name.lower())
    if wanted and already is not True:
        return (True, True)
    if not wanted and tell_off and already is not False:
        return (True, False)
    return (False, wanted)


def changed(old, new):
    """True when the settings change asks the board to be told again."""
    def want(s):
        return bool((s or {}).get("leaderboard_optin", True))
    return want(old) != want(new)
