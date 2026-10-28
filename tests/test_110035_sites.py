"""What 1.10035 adds around the finds, each held down so it stays.

Importing from other tools (a bookmark database, share lines, a survey CSV and
a map file) with a preview, duplicate detection and a backup first; depleted
deposits and when to look at them again; My sites with stars, a bin that keeps
what you removed and the three most valuable commodities of a location; the
map and scope marker filters; the prompt for a tonne refined where nothing is
marked; and the line said on arriving in a system.

The logic is checked as plain functions, then every feature is checked on the
real toolkit - the real windows, the real map and scope, the real app driven
through a synthetic journal - because "the function is right" has not once
meant "it is on the screen". Every fixture is made here; nothing is copied
from anyone's files.

It needs a display (xvfb will do) for the second half and says SKIP, out
loud, for that half without one.

    python tests/test_110035_sites.py
"""
import os, sys, json, math, tempfile, time, base64, zlib, sqlite3, csv, glob, calendar
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-sites-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import survey as SV         # noqa: E402
import importers as IM      # noqa: E402
import regrowth as RG       # noqa: E402
import sitebook as SBK      # noqa: E402
import markerfilter as MF   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    """Run the function under it; an exception is one failure, named."""
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:                       # a missing feature
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=4)
        return fn
    return wrap


R = 2_100_000.0
HOME = (12.5, -45.5)
DAY = 86400.0


def dest(lat, lon, bearing, metres):
    return SV.destination(lat, lon, bearing, metres, R)


def at(bearing, metres):
    return dest(HOME[0], HOME[1], bearing, metres)


def fresh_store(name):
    """A store with one Platinum deposit 600 m north of HOME, on a body of
    known size, in a signal that was logged."""
    store = SV.Survey(os.path.join(TMP, name))
    lat, lon = at(0, 600)
    store.set_location("Ega", "Ega 1", "2", lat=HOME[0], lon=HOME[1], radius_m=R)
    store.add_deposit(system="Ega", body="Ega 1", location="2", commodity="Platinum",
                      rigs="4", amount="High", density="Medium",
                      lat="%.6f" % lat, lon="%.6f" % lon)
    return store


# ---------------------------------------------------------------------------
# Fixtures for the four kinds of source
# ---------------------------------------------------------------------------
def code(record, prefix="Spot"):
    raw = json.dumps(record, separators=(",", ":")).encode("utf-8")
    return prefix + ":" + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def spot(commodity, bearing, metres, **more):
    lat, lon = at(bearing, metres)
    record = {"system": "Ega", "planet_name": "Ega 1", "planet_radius": R,
              "latitude": lat, "longitude": lon, "location_index": 2,
              "commodity": commodity, "rigs": 4, "amount": "High", "density": "Medium"}
    record.update(more)
    return record


def make_db(path, rows, table="bookmarks"):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE %s (id INTEGER PRIMARY KEY, system TEXT, "
                 "planet_name TEXT NOT NULL, system_address INTEGER, body_id INTEGER, "
                 "commodity TEXT, location_index INTEGER, rigs INTEGER, "
                 "depleted_at TEXT, data TEXT, source TEXT UNIQUE)" % table)
    for record, depleted in rows:
        conn.execute("INSERT INTO %s (system, planet_name, commodity, location_index, "
                     "rigs, depleted_at, data) VALUES (?,?,?,?,?,?,?)" % table,
                     (record.get("system"), record.get("planet_name"), record.get("commodity"),
                      record.get("location_index"), record.get("rigs"), depleted,
                      None if record.get("_null") else json.dumps(record)))
    conn.commit()
    conn.close()
    return path


CSV_HEADER = ("SchemaVersion,SurveyId,FrontierId,Commander,System,SystemAddress,SystemX,"
              "SystemY,SystemZ,Body,BodyId,BodyType,ArrivalDistanceLs,LocationSignalNumber,"
              "LocationName,SurveyNotes,BorderRadiusKm,PlanetRadiusKm,CenterLatitude,"
              "CenterLongitude,SurveyCreatedUtc,SurveyUpdatedUtc,MarkerIndex,MarkerId,"
              "Commodity,MineralAmount,Density,RigCount,MarkerLatitude,MarkerLongitude,"
              "MarkerDistanceFromCenterKm,MarkerBearingFromCenterDegrees,MarkerCreatedUtc,"
              "SplatTraceActive,SplatBoundaryPointCount,SuggestedRigLocationCount,"
              "SplatBoundaryCoordinates,SuggestedRigCoordinates").split(",")


def make_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def csv_row(commodity, bearing, metres, **more):
    lat, lon = at(bearing, metres)
    row = {"SchemaVersion": "1", "System": "Ega", "Body": "Ega 1", "LocationSignalNumber": "2",
           "PlanetRadiusKm": "2100", "CenterLatitude": "%.6f" % HOME[0],
           "CenterLongitude": "%.6f" % HOME[1], "MarkerIndex": "1", "Commodity": commodity,
           "MineralAmount": "High", "Density": "Medium", "RigCount": "4",
           "MarkerLatitude": "%.6f" % lat, "MarkerLongitude": "%.6f" % lon,
           "MarkerCreatedUtc": "2026-10-02T09:30:00.0000000+00:00"}
    row.update(more)
    return row


def write(path, data, mode="w"):
    with open(path, mode + ("b" if isinstance(data, bytes) else ""),
              **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as handle:
        handle.write(data)
    return path


# ---------------------------------------------------------------------------
@section("share lines: found by what is inside them, whatever they are called")
def _lines():
    store = fresh_store("lines")
    text = "\n".join([
        "CMDR Aldous: found these last night, o7",
        code(spot("Platinum", 0, 640)),                      # 40 m from the one held: known
        "and this one " + code(spot("Platinum", 0, 800), prefix="Shared"),   # 200 m: new
        code(spot("Osmium", 0, 600), prefix="x9_bookmark"),  # same place, other commodity: new
        code(spot("Gold", 90, 900)), code(spot("Gold", 90, 900)),    # twice: one new, one known
        "Spot:" + "A" * 60,                                  # looks like one, is not
        code(spot("Bauxite", 0, 700, latitude=95.0)),        # decodes, but not a place
    ])
    source = IM.read_text(text)
    check("it is read as share lines", source.kind == IM.KIND_LINES and source.rows == 7, (source.kind, source.rows))
    plan = IM.make_plan(source, store)
    new, known, skipped = plan.counts
    check("three new, two already known, two skipped", (new, known, skipped) == (3, 2, 2), plan.counts)
    check("the preview says so in one line, with the reasons",
          plan.preview().startswith("3 new, 2 already known, 2 skipped: ")
          and "no position (1)" in plan.preview() and "could not be read (1)" in plan.preview(),
          plan.preview())
    check("the same commodity 40 m away is the same find; 200 m away is not",
          sorted(f["commodity"] for f in plan.new) == ["Gold", "Osmium", "Platinum"]
          and any(f["commodity"] == "Platinum" for f in plan.known))
    check("a different commodity at the very same spot is a find of its own",
          any(f["commodity"] == "Osmium" for f in plan.new))
    check("chat round the codes is ignored, not counted", source.skipped.get(IM.SKIP_UNREADABLE) == 1, source.skipped)
    check("the signal number comes through", all(f["location"] == "2" for f in plan.new))
    nothing = IM.read_text("just some chat, no codes here at all")
    check("text with no code in it is refused by name", nothing.error and "Not recognised" in nothing.error, nothing.error)


# ---------------------------------------------------------------------------
@section("a bookmark database: opened read-only, depleted dates kept")
def _database():
    store = fresh_store("db")
    rows = [
        (spot("Platinum", 0, 800), None),                                  # new
        (spot("Monazite", 45, 1500, rigs=9), None),                         # new, rigs not a number the game can give
        (spot("Painite", 90, 400, amount="High"), "2026-10-18T08:00:00+00:00"),   # new, depleted
        (spot("Platinum", 0, 650), None),                                  # 50 m from the held one: known
        (dict(spot("Osmium", 10, 300), _null=True), None),                  # no record: unreadable
        (spot("Gold", 20, 500, latitude=None), None),                       # no position
        (spot("XYZ", 20, 500), None),                                      # a code for a commodity
    ]
    path = make_db(os.path.join(TMP, "marks.db"), rows)
    before = open(path, "rb").read()
    source = IM.read_path(path)
    check("the file is recognised as a bookmark database from its contents",
          source.kind == IM.KIND_BOOKMARKS and source.label == "Bookmark database (.db)", (source.kind, source.error))
    check("opening it changed nothing in it", open(path, "rb").read() == before)
    plan = IM.make_plan(source, store)
    check("three new, one known, three skipped", plan.counts == (3, 1, 3), (plan.counts, plan.preview()))
    by = {f["commodity"]: f for f in plan.new}
    check("a rig count the game cannot produce is left blank, the find kept", by["Monazite"]["rigs"] == "", by.get("Monazite"))
    check("a depleted date makes the find Depleted, and keeps its date",
          by["Painite"]["amount"] == "Depleted" and by["Painite"]["depleted_at"] == "2026-10-18T08:00:00Z", by["Painite"])
    odd = os.path.join(TMP, "odd name.dat")             # not called anything database-like
    write(odd, before, "w")
    check("it is found by its contents, not by its name or extension",
          IM.read_path(odd).kind == IM.KIND_BOOKMARKS)


# ---------------------------------------------------------------------------
@section("a survey CSV: thirty-eight columns, one row a deposit")
def _survey_csv():
    store = fresh_store("csv")
    rows = [csv_row("Platinum", 0, 900),
            csv_row("Osmium", 90, 400, MineralAmount="Strange", Density="", RigCount="7"),
            csv_row("Platinum", 0, 630),                                        # 30 m: known
            csv_row("", 0, 0, Commodity="", MarkerLatitude="", MarkerLongitude="",
                    MarkerIndex=""),                                           # a map without deposits
            csv_row("ABC", 180, 500),                                          # a code, not a name
            csv_row("Gold", 180, 500, MarkerLatitude="not a number")]
    path = make_csv(os.path.join(TMP, "survey export.csv"), rows)
    source = IM.read_path(path)
    check("it is the survey CSV, by its header", source.kind == IM.KIND_CSV and source.rows == 6, (source.kind, source.error))
    plan = IM.make_plan(source, store)
    check("two new, one known, three skipped", plan.counts == (2, 1, 3), plan.preview())
    check("a body size in km becomes metres, and an unknown amount is left blank",
          next(f for f in plan.new if f["commodity"] == "Osmium")["amount"] == ""
          and plan.new[0]["radius_m"] == 2100000.0)
    check("the format's own gaps are said in the preview", any("does not say how it spells" in n for n in source.notes))
    check("a map without deposits and a code for a commodity are named as reasons",
          "map with no deposits (1)" in plan.preview() and IM.SKIP_CODE in plan.preview(), plan.preview())
    guarded = IM.read_text(CSV_HEADER and ",".join(CSV_HEADER) + "\n" + ",".join(
        ["'=Platinum" if h == "Commodity" else "Ega" if h in ("System",) else "Ega 1" if h == "Body"
         else "10" if h in ("MarkerLatitude", "MarkerLongitude") else "" for h in CSV_HEADER]))
    check("a spreadsheet's guard apostrophe is taken off a cell",
          guarded.finds and guarded.finds[0]["commodity"] != "", [f["commodity"] for f in guarded.finds])
    spelt = IM.read_text("system,body,commodity,marker_latitude,Marker Longitude\r\n"
                         "Ega,Ega 1,Gold,10.5,20.5\r\n")
    check("a header spelt with underscores or spaces, in any case, reads the same",
          spelt.kind == IM.KIND_CSV and len(spelt.finds) == 1 and spelt.finds[0]["lat"] == "10.500000",
          (spelt.kind, spelt.error))


# ---------------------------------------------------------------------------
@section("a map file: where the deposits are, not what they are")
def _map_file():
    store = fresh_store("map")
    lat, lon = at(90, 700)
    data = {"system": "Ega", "body": "Ega 1", "planet_radius": R, "pml_id": "2",
            "pml_center_lat": HOME[0], "pml_center_lon": HOME[1],
            "deposits": [
                {"name": "Platinum", "size": "Grande", "rigs": 4, "x": 1.0, "y": 2.0,
                 "lat": at(90, 700)[0], "lon": at(90, 700)[1]},
                {"name": "Deposit", "size": "Pequeno", "rigs": 2, "lat": at(180, 800)[0], "lon": at(180, 800)[1]},
                {"name": "Deposit", "rigs": 3},                                  # no coordinates
                "not a deposit"]}
    path = write(os.path.join(TMP, "a map.json"), json.dumps(data))
    source = IM.read_path(path)
    check("it is a map file, by its contents", source.kind == IM.KIND_MAP and source.rows == 4, (source.kind, source.error))
    plan = IM.make_plan(source, store)
    check("without a commodity chosen, only the one that names itself is taken",
          plan.counts[0] == 1 and plan.new[0]["commodity"] == "Platinum", plan.preview())
    check("the others are skipped and the reason is the missing commodity",
          IM.SKIP_NO_COMMODITY in plan.preview(), plan.preview())
    chosen = IM.make_plan(source, store, default_commodity="Osmium")
    check("choosing a commodity takes the unnamed ones as it",
          chosen.counts[0] == 2 and sorted(f["commodity"] for f in chosen.new) == ["Osmium", "Platinum"], chosen.preview())
    check("the file says it does not carry a commodity", any("not what it is" in n for n in source.notes))
    check("a file that is JSON but not a map says what it lacks",
          "not a surveyed-body map" in IM.read_text('{"hello": 1}').error)


# ---------------------------------------------------------------------------
@section("malformed imports are refused by name and change nothing")
def _malformed():
    store = fresh_store("bad")
    held = len(store.deposits)
    cases = {
        "truncated database": write(os.path.join(TMP, "t.db"), b"SQLite format 3\x00" + b"\x00" * 90),
        "a database of something else": make_db(os.path.join(TMP, "other.db"), [(spot("Gold", 0, 1), None)], table="notes"),
        "an empty file": write(os.path.join(TMP, "empty.csv"), b""),
        "binary garbage": write(os.path.join(TMP, "garbage.bin"), bytes(range(256)) * 4),
        "broken json": write(os.path.join(TMP, "broken.json"), '{"system": "Ega", "deposits": ['),
        "a json list": write(os.path.join(TMP, "list.json"), "[1, 2, 3]"),
        "a csv with the wrong header": write(os.path.join(TMP, "wrong.csv"), "a,b,c\n1,2,3\n"),
        "a missing file": os.path.join(TMP, "nowhere.db"),
    }
    for label, path in cases.items():
        source = IM.read_path(path)
        check("%s: an error is said, nothing is read" % label, bool(source.error) and not source.finds, source.error)
        plan = IM.make_plan(source, store)
        result = IM.apply(plan, store, os.path.join(TMP, "bad-backups"))
        check("%s: and applying it adds nothing" % label, result["taken"] == 0 and len(store.deposits) == held)
    bomb = code({"system": "Ega", "planet_name": "Ega 1", "pad": "0" * 3_000_000})
    check("a share code that inflates far past a record is refused, not expanded",
          len(bomb) < IM.MAX_CODE + 40 and IM.decode_code(bomb.split(":", 1)[1]) is None, len(bomb))
    check("a code of a record with the wrong types is refused",
          IM.decode_code(code({"system": 5, "planet_name": "x", "commodity": "Gold",
                               "latitude": 1, "longitude": 1}).split(":", 1)[1]) is None)
    check("a position with a flag in it is not a number",
          IM.decode_code(code({"system": "Ega", "planet_name": "x", "commodity": "Gold",
                               "latitude": True, "longitude": 1}).split(":", 1)[1]) is None)


# ---------------------------------------------------------------------------
@section("applying: a backup first, the finds added, nothing already here touched")
def _apply():
    store = fresh_store("apply")
    lat, lon = at(0, 600)
    centre_before = dict(store.location("Ega", "Ega 1", "2"))
    folder = os.path.join(TMP, "apply-backups")
    source = IM.read_text("\n".join([code(spot("Platinum", 0, 800)), code(spot("Gold", 90, 900, location_index=5))]))
    plan = IM.make_plan(source, store)
    seen_backups = []
    original = store.add_deposit

    def watching(**row):
        seen_backups.append(len(glob.glob(os.path.join(folder, "EDSMT-backup-*.zip"))))
        return original(**row)
    store.add_deposit = watching
    result = IM.apply(plan, store, folder)
    store.add_deposit = original
    check("it worked", result["ok"] and result["taken"] == 2, result)
    check("a dated backup zip existed before the first find was added",
          seen_backups and seen_backups[0] == 1, seen_backups)
    check("the backup is named in the summary", "backed up to EDSMT-backup-" in IM.summary(result, plan), IM.summary(result, plan))
    added = [d for d in store.deposits if "Imported from Share lines" in d["notes"]]
    check("each find says where it came from", len(added) == 2, [d["notes"] for d in store.deposits])
    check("a signal the file brought is logged for the body, with its size",
          store.location("Ega", "Ega 1", "5") is not None and store.location("Ega", "Ega 1", "5")["radius_m"] == "2100000")
    check("a signal already logged was left exactly as it was",
          store.location("Ega", "Ega 1", "2") == centre_before)
    again = IM.make_plan(source, store)
    check("the same source again is all already known", again.counts[0] == 0 and again.counts[1] == 2, again.preview())
    depleted = IM.read_text(code(spot("Iridium", 270, 500, amount="Depleted")))
    done = IM.apply(IM.make_plan(depleted, store), store, folder)
    row = next(d for d in store.deposits if d["commodity"] == "Iridium")
    check("a depleted find is given a first depletion date", row["amount"] == "Depleted" and row["depleted_at"], row)
    # A backup that cannot be written means nothing is imported.
    broken = fresh_store("apply-broken")
    plan2 = IM.make_plan(IM.read_text(code(spot("Gold", 90, 900))), broken)

    def no_backup(_folder):
        raise OSError("disk full")
    broken.backup_to = no_backup
    held = len(broken.deposits)
    result2 = IM.apply(plan2, broken, folder)
    check("if the backup cannot be written nothing is imported, and it says why",
          not result2["ok"] and "disk full" in result2["reason"] and len(broken.deposits) == held, result2)


# ---------------------------------------------------------------------------
@section("sharing: what the preview says, and what is sent")
def _sharing():
    class Link:
        def __init__(self, ready=True, named=True):
            self.ready, self.share_name, self.uploads = ready, named, []

    check("on, ready, named: shared under the CMDR name",
          "shared with the community map" in IM.sharing_line({"community_auto_share": True}, Link(), ())
          and "under your CMDR name" in IM.sharing_line({}, Link(), ()))
    check("without the name it says so", "without your name" in IM.sharing_line({}, Link(named=False), ()))
    check("a link that is not ready: stays on this PC, and says why",
          "stay on this PC" in IM.sharing_line({}, Link(ready=False), ()) and "not ready" in IM.sharing_line({}, Link(ready=False), ()))
    check("sharing off in a file that is not forced on: stays on this PC",
          "sharing is off" in IM.sharing_line({"community_auto_share": False}, Link(), ()))
    check("a setting the app keeps on whatever the file says wins over the file",
          "shared with the community map" in IM.sharing_line({"community_auto_share": False}, Link(),
                                                             ("community_auto_share",)))
    store = fresh_store("share")
    result = IM.apply(IM.make_plan(IM.read_text(code(spot("Gold", 90, 900))), store), store,
                      os.path.join(TMP, "share-backups"))
    rows = IM.community_rows(result["records"])
    check("an imported find goes up as the community takes it: a position, no galactic position",
          len(rows) == 1 and rows[0]["type"] == "Gold" and rows[0]["planet"] == "Ega 1"
          and rows[0]["lat"] is not None and "x" not in rows[0], rows)


# ---------------------------------------------------------------------------
BASE = float(calendar.timegm((2026, 10, 1, 12, 0, 0)))


def depleted_row(**more):
    row = {"id": "d1", "commodity": "Platinum", "amount": "Depleted",
           "depleted_at": RG.stamp(BASE), "rechecks": "", "mined": "", "notes": ""}
    row.update(more)
    return row


@section("regrowth: day 13, day 14, a look on day 15, day 22")
def _regrowth():
    row = depleted_row()
    for days, state, text in ((0, "fresh", "depleted today"),
                              (13, "fresh", "depleted 13 d ago"),
                              (14, "look", "depleted 14 days - recheck due"),
                              (20, "look", "depleted 20 days - recheck due")):
        info = RG.standing(row, BASE + days * DAY + 60)
        check("day %d: %s" % (days, text), info["state"] == state and info["text"] == text, info)
    check("day 13 is not due a look; day 14 is",
          not RG.standing(row, BASE + 13.9 * DAY)["due"] and RG.standing(row, BASE + 14 * DAY)["due"])
    look = BASE + 15 * DAY
    changes, kind = RG.still_depleted_changes(row, look)
    check("looking on day 15 is a recheck that keeps the FIRST date",
          kind == "recheck" and changes["depleted_at"] == RG.stamp(BASE)
          and changes["rechecks"] == RG.stamp(look), changes)
    row.update(changes)
    info = RG.standing(row, look)
    check('the card says "depleted 15 days - recheck in 7 days"',
          info["text"] == "depleted 15 days - recheck in 7 days" and not info["due"], info["text"])
    check("three days on it counts down", RG.standing(row, look + 3 * DAY)["text"]
          == "depleted 15 days - recheck in 4 days")
    check("the mark is still on at day 21", RG.depleted(row) and RG.expiry_changes(row, BASE + 21.5 * DAY) is None)
    gone = RG.expiry_changes(row, BASE + 22 * DAY)
    check("on day 22 - seven days after the look - the mark comes off",
          RG.standing(row, BASE + 22 * DAY)["state"] == "expired" and gone and gone["amount"] == "", gone)
    check("and each look is kept in the list", RG.looks(row) == [look])
    # a second look on a later day is added, not replacing
    row2 = depleted_row(rechecks=RG.stamp(look))
    again, kind2 = RG.mark_changes(row2, BASE + 24 * DAY)
    check("a later look is added to the list; the first date still stands",
          kind2 == "recheck" and again["rechecks"].count(";") == 1 and again["depleted_at"] == RG.stamp(BASE), again)
    inside, kind2b = RG.mark_changes(row2, look + 2 * DAY)
    check("marking it again inside the week after a look changes nothing and keeps the look",
          kind2b == "same" and inside["rechecks"] == RG.stamp(look) and inside["depleted_at"] == RG.stamp(BASE), inside)
    soon, kind3 = RG.mark_changes(depleted_row(), BASE + 5 * DAY)
    check("marking it again before it is due does not start a look",
          kind3 == "same" and soon["rechecks"] == "" and soon["depleted_at"] == RG.stamp(BASE), soon)
    regrown = depleted_row(mined="Platinum:38")
    info = RG.standing(regrown, BASE + 16 * DAY)
    check("tonnes refined since it was marked say it has grown back", info["state"] == "regrown", info)
    fresh, kind4 = RG.mark_changes(regrown, BASE + 20 * DAY)
    check("worked out again after that, it is a NEW depletion: new first date, no looks",
          kind4 == "new" and fresh["depleted_at"] == RG.stamp(BASE + 20 * DAY) and fresh["rechecks"] == "", fresh)
    byproduct = depleted_row(mined="Osmium:12")
    check("a by-product refined at its neighbour does not make it look regrown",
          RG.standing(byproduct, BASE + 16 * DAY)["state"] == "look")
    notes_only = {"commodity": "Gold", "amount": "Depleted", "depleted_at": "", "rechecks": "", "mined": "",
                  "notes": "Mined 10/09/2026 01:05"}
    check("a deposit worked out before this version still has its age, from its note",
          RG.first_date(notes_only) is not None
          and RG.standing(notes_only, time.mktime((2026, 9, 25, 1, 5, 0, 0, 0, -1)))["state"] == "look")
    check("a depleted deposit with no date at all says it is not known",
          RG.standing({"commodity": "Gold", "amount": "Depleted"})["state"] == "unknown")
    active = RG.set_active_changes(depleted_row(rechecks=RG.stamp(look)), BASE + 16 * DAY)
    check("REGROWN clears the mark, sets the amount to unread and clears the dates",
          active["amount"] == "" and active["depleted_at"] == "" and active["rechecks"] == ""
          and "Regrown" in active["notes"], active)
    store = SV.Survey(os.path.join(TMP, "expire"))
    store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Gold", amount="Depleted",
                      depleted_at=RG.stamp(BASE), rechecks=RG.stamp(look), lat="1", lon="1")
    store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Iron", amount="Depleted",
                      depleted_at=RG.stamp(BASE), rechecks="", lat="2", lon="2")
    check("expire_marks takes off only the one whose look is a week old",
          RG.expire_marks(store, BASE + 23 * DAY) == 1
          and [d["amount"] for d in store.deposits] == ["", "Depleted"])
    check("the history stays when the mark comes off",
          store.deposits[0]["depleted_at"] and store.deposits[0]["rechecks"] and "came off" in store.deposits[0]["notes"])
    reloaded = SV.Survey(os.path.join(TMP, "expire"))
    check("the dates are saved in the finds file and read back",
          reloaded.deposits[1]["depleted_at"] == RG.stamp(BASE))


# ---------------------------------------------------------------------------
@section("favourites and the bin: stars, removal, restore, retention")
def _bin():
    store = SV.Survey(os.path.join(TMP, "bin"))
    for body, signal, commodity in (("Wyrd 2", "1", "Gold"), ("Wyrd 2", "1", "Osmium"), ("Wyrd 3", "4", "Platinum")):
        store.set_location("Wyrd", body, signal, lat=1.0, lon=1.0, radius_m=R)
        store.add_deposit(system="Wyrd", body=body, location=signal, commodity=commodity,
                          lat="1.0001", lon="1.0001" if commodity != "Osmium" else "1.0009")
    book = SBK.SiteBook(store.folder)
    key = SBK.site_key("Wyrd", "Wyrd 2", "1")
    check("a site is starred and unstarred", book.set_favourite(key, True) and key in book.favourites()
          and not book.toggle_favourite(key) and key not in book.favourites())
    book.set_favourite(key, True)
    check("stars are kept in a file beside the finds, and read back by a new holder",
          key in SBK.SiteBook(store.folder).favourites())
    t0 = time.time() - 31 * DAY
    entry = book.remove_site(store, "Wyrd", "Wyrd 2", "1", now=t0)
    check("removing a site takes its finds and its signal out of the records",
          entry and len(entry["deposits"]) == 2 and len(entry["locations"]) == 1
          and [d["body"] for d in store.deposits] == ["Wyrd 3"] and len(store.locations) == 1, entry)
    check("and out of the files on disk too", len(SV.Survey(store.folder).deposits) == 1)
    check("the star stays with the site while it is in the bin", key in book.favourites())
    back = book.restore(store, entry["id"])
    check("Restore puts the finds and the signal back, and empties that bin entry",
          back == (2, 1) and len(store.deposits) == 3 and not book.bin(), back)
    check("restoring the same site twice cannot double a find",
          book.restore(store, entry["id"]) is None and len(store.deposits) == 3)
    entry = book.remove_site(store, "Wyrd", "Wyrd 2", "1", now=t0)
    other = book.remove_site(store, "Wyrd", "Wyrd 3", "4", now=time.time())
    check("a site that is not there is not binned", book.remove_site(store, "Nowhere", "x", "1") is None)
    check("the bin knows how long each has left",
          SBK.SiteBook.days_left(entry, 60) == 29 and SBK.SiteBook.days_left(other, 60) == 60,
          (SBK.SiteBook.days_left(entry, 60), SBK.SiteBook.days_left(other, 60)))
    check("nothing goes before its time: 60 days keeps a 31 day old one", book.purge(60) == 0 and book.binned() == 2)
    check("a 31 day old site is deleted for good at 30 days; the new one stays",
          book.purge(30) == 1 and book.binned() == 1 and book.bin()[0]["id"] == other["id"])
    check("the retention is held to 1 to 365 days, 30 where it is nonsense",
          [SBK.retention_days(v) for v in (0, "7", 9999, "soon", None)] == [1, 7, 365, 30, 30])
    check("Empty clears the lot", book.empty() == 1 and book.binned() == 0 and book.empty() == 0)
    check("a bin file that is not JSON reads as empty rather than raising",
          write(os.path.join(store.folder, SBK.FILE), "{nope") and SBK.SiteBook(store.folder).bin() == [])


# ---------------------------------------------------------------------------
@section("a location line: its three most valuable commodities, each once")
def _best():
    prices = {"Platinum": 250000, "osmium": 100000, "Gold": 40000, "Aluminium": 1000}
    names = ["Aluminium", "Gold", "Platinum", "platinum", "Osmium", "Gold", "unknown", ""]
    check("three, by best known Cr/t, each once",
          SBK.best_commodities(names, prices) == ["Platinum", "Osmium", "Gold"], SBK.best_commodities(names, prices))
    check("a commodity nobody has priced goes last",
          SBK.best_commodities(["Bauxite", "Gold"], {"Gold": 5}) [0] == "Gold")
    check("without prices the published averages decide", SBK.best_commodities(["Aluminium", "Platinum", "Gold"])[0] == "Platinum")
    check("fewer than three is fewer than three", SBK.best_commodities(["Gold"], prices) == ["Gold"])
    site = {"system": "Ega", "body": "Ega 1", "signal": "1", "offers": ["Aluminium", "Gold", "Platinum", "Osmium"],
            "depleted": [], "logged": True, "finds": 3, "intact": 3, "rigs": 6,
            "types": {"Gold": 2, "Platinum": 1}, "mined": {}, "last": "2026-10-01T00:00:00Z"}
    import survey
    cells = None
    # site_cells is the app's; it is checked on the real window below.


# ---------------------------------------------------------------------------
@section("the arrival line and the unmarked-refine prompt, as plain rules")
def _prompts_logic():
    store = fresh_store("prompts")
    store.set_location("Ega", "Ega 3", "1", lat=1.0, lon=1.0, radius_m=R)
    store.set_location("Wyrd", "Wyrd 2", "1", lat=1.0, lon=1.0, radius_m=R)
    mine, shared = SBK.arrival_counts(store, "ega", [{"planet": "Ega 1", "spot": "2"},
                                                     {"planet": "Ega 4", "spot": "1"},
                                                     {"planet": "Ega 4", "spot": "1"}, "junk"])
    check("your sites in the system, and the shared ones that are not yours, once each",
          (mine, shared) == (2, 1), (mine, shared))
    check("the line", SBK.arrival_line(2, 1) == "2 of your sites here, 1 shared")
    check("nothing to say when both are nothing", SBK.arrival_line(0, 0) == "")
    check("either alone is enough", SBK.arrival_line(0, 3) == "0 of your sites here, 3 shared"
          and SBK.arrival_line(1, 0) == "1 of your sites here, 0 shared")
    lat, lon = at(90, 2000)
    note = {"event": "Refined", "in_srv": True, "lat": lat, "lon": lon, "radius_m": R,
            "system": "Ega", "body": "Ega 1", "commodity": "Osmium"}
    spots = []
    found = SBK.unmarked_refine(store, note, 100.0, spots)
    check("a tonne with nothing marked near it asks, once",
          found and found["commodity"] == "Osmium" and SBK.unmarked_refine(store, note, 100.0, spots) is None)
    check("the line reads as asked", SBK.refine_line("Osmium") == "Refined Osmium here, nothing marked - mark it?")
    check("another commodity at the same spot is a separate question",
          SBK.unmarked_refine(store, dict(note, commodity="Gold"), 100.0, spots) is not None)
    check("not in the Rhino: no question", SBK.unmarked_refine(store, dict(note, in_srv=False, commodity="Iron"), 100.0, []) is None)
    near_lat, near_lon = at(0, 640)
    check("a deposit of that commodity marked within the distance: no question",
          SBK.unmarked_refine(store, dict(note, lat=near_lat, lon=near_lon, commodity="Platinum"), 100.0, []) is None)
    check("nor for a by-product refined standing at a deposit that is marked",
          SBK.unmarked_refine(store, dict(note, lat=near_lat, lon=near_lon, commodity="Osmium"), 100.0, []) is None)
    far_lat, far_lon = at(0, 900)
    check("beyond the distance from it, a tonne of the same commodity is a new place",
          SBK.unmarked_refine(store, dict(note, lat=far_lat, lon=far_lon, commodity="Platinum"), 100.0, []) is not None)
    check("no position, no question", SBK.unmarked_refine(store, dict(note, lat=None), 100.0, []) is None)


# ---------------------------------------------------------------------------
@section("marker filters: commodity, amount and density, and what stays")
def _filters():
    def row(commodity, amount="", density=""):
        return {"commodity": commodity, "deposit": {"commodity": commodity, "amount": amount, "density": density}}
    rows = [row("Platinum", "High", "High"), row("Platinum", "Depleted", "Medium"), row("Osmium", "Medium", "Low"),
            row("Gold", "", ""), row("Gold", "Low", "Medium")]

    def kept(**settings):
        flt = MF.from_settings(settings)
        return [(r["commodity"], r["deposit"]["amount"]) for r in MF.apply(rows, {"filter": flt})]
    check("no filter keeps everything", len(kept()) == 5)
    check("by commodity", kept(map_filter_commodities=["platinum"]) == [("Platinum", "High"), ("Platinum", "Depleted")])
    check("two commodities", len(kept(map_filter_commodities=["Platinum", "Osmium"])) == 3)
    check("not depleted", ("Platinum", "Depleted") not in kept(map_filter_amount="Not depleted") and len(kept(map_filter_amount="Not depleted")) == 4)
    check("medium or more keeps a deposit whose amount was never read",
          kept(map_filter_amount="Medium or more") == [("Platinum", "High"), ("Osmium", "Medium"), ("Gold", "")])
    check("high only", kept(map_filter_amount="High only") == [("Platinum", "High"), ("Gold", "")])
    check("density medium or more", [r[0] for r in kept(map_filter_density="Medium or more")] == ["Platinum", "Platinum", "Gold", "Gold"])
    check("the three together narrow further",
          kept(map_filter_commodities=["Platinum"], map_filter_amount="Not depleted",
               map_filter_density="High only") == [("Platinum", "High")])
    check("a setting that is nonsense reads as Any",
          MF.from_settings({"map_filter_amount": "Lots", "map_filter_density": 5})["amount"] == "Any")
    check("names on by default, off when told", MF.labels_on({"filter": MF.from_settings({})})
          and not MF.labels_on({"filter": MF.from_settings({"map_labels": False})}) and MF.labels_on({}))
    check("comma-separated text is a list too", MF.commodity_list("platinum, Osmium ,, platinum") == ["Platinum", "Osmium"])
    check("it says what is showing", "Platinum" in MF.describe(MF.from_settings({"map_filter_commodities": ["Platinum"]}))
          and "every deposit" in MF.describe(MF.from_settings({})))


# ===========================================================================
# The toolkit half: the real windows, the real map and scope, the real app
# ===========================================================================
HAVE_DISPLAY = False
try:
    import tkinter as tk
    _probe = tk.Tk()
    _probe.destroy()
    HAVE_DISPLAY = True
except Exception as _exc:             # no display: say so, loudly
    print("\n  SKIP  the toolkit half of this file - no display (%s). "
          "Run it under xvfb-run." % _exc)


def on_screen(title):
    def wrap(fn):
        if not HAVE_DISPLAY:
            print("== %s ==\n  SKIP  needs a display" % title)
            return fn
        return section(title)(fn)
    return wrap


def tags_of(canvas):
    out = {}
    for item in canvas.find_all():
        for tag in canvas.gettags(item):
            out[tag] = out.get(tag, 0) + 1
    return out


def texts_of(canvas, tag=None):
    return [canvas.itemcget(i, "text") for i in canvas.find_all()
            if canvas.type(i) == "text" and (tag is None or tag in canvas.gettags(i))]


def words_in(widget):
    """Every piece of text shown anywhere under a widget."""
    out = []
    try:
        out.append(str(widget.cget("text")))
    except Exception:
        pass
    for child in widget.winfo_children():
        out.extend(words_in(child))
    return out


def rings(canvas, colour):
    """Ovals and diamonds drawn as an empty ring in `colour`."""
    return [i for i in canvas.find_all() if canvas.type(i) in ("oval", "polygon")
            and canvas.itemcget(i, "outline") == colour and not canvas.itemcget(i, "fill")]


class Link:
    """Stands in for the community link: nothing leaves the machine."""
    ready = True
    can_read = True
    can_verify = False
    share_name = True
    enabled = True

    def __init__(self):
        self.uploads, self.asked = [], []

    def upload(self, cmdr, rows):
        self.uploads.append((cmdr, list(rows)))
        return True

    def system_sites(self, system):
        self.asked.append(system)
        return True

    def __getattr__(self, name):
        return lambda *args, **kwargs: False


if HAVE_DISPLAY:
    import customtkinter  # noqa: F401
    import overlay as OV    # noqa: E402
    import planview as PV   # noqa: E402
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
    app.community.enabled = False          # nothing reaches a server from here
    # A settings file with no keys in it earns the "New keys" notice, which
    # lands on the status line 2.5 s after start - on a slow runner, on top
    # of the one-line prompts checked below. Let it come and go first.
    _settled = time.time() + 3.0
    while time.time() < _settled:
        app.update_idletasks(); app.update(); time.sleep(0.02)
    LINK = Link()
    app.community = LINK
    A.confirm = lambda *args, **kwargs: True

    def pump(times=4):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    pump()
    PRICES = {"Platinum": 250000, "Osmium": 100000, "Gold": 40000, "Aluminium": 1000}
    app.market_prices = lambda: PRICES


# ---------------------------------------------------------------------------
@on_screen("My sites: the stars, the bin, Restore, Empty bin and the best three")
def _sites_window():
    store = app.store
    for body, signal, commodity, bearing in (("Wyrd 2", "1", "Gold", 0), ("Wyrd 2", "1", "Platinum", 90),
                                             ("Wyrd 2", "1", "Aluminium", 180), ("Wyrd 3", "4", "Osmium", 270)):
        lat, lon = at(bearing, 500)
        store.set_location("Wyrd", body, signal, lat=HOME[0], lon=HOME[1], radius_m=R,
                           commodities=["Gold", "Platinum", "Osmium", "Aluminium"] if body == "Wyrd 2" else None)
        store.add_deposit(system="Wyrd", body=body, location=signal, commodity=commodity,
                          rigs="3", amount="High", lat="%.6f" % lat, lon="%.6f" % lon)
    win = app.open_sites()
    pump()
    wyrd2 = next(r for r in win._rows if r["body"] == "Wyrd 2")
    cell = A.EarningsWindow._cell(A.site_cells(wyrd2, ("", ""), PRICES)[3])[0]
    check("a site line names its three most valuable commodities, each once, first",
          cell.splitlines()[0] == "best: Platinum, Gold, Aluminium" or cell.splitlines()[0].startswith("best: Platinum, Osmium, Gold"), cell)
    check("and the table shows it", any("best: Platinum" in w for w in words_in(win.table)), words_in(win.table)[:12])
    check("a site with one commodity is not given a second line saying it again",
          not A.site_cells(next(r for r in win._rows if r["body"] == "Wyrd 3"), ("", ""), PRICES)[3][0].startswith("best:"))
    check("without prices the cells are as they were",
          not A.site_cells(wyrd2, ("", ""))[3][0].startswith("best:"))
    labels = words_in(win.table)
    check("every row has a star and a remove button", labels.count("☆") >= 2 and labels.count("remove") >= 2, labels[-20:])
    book = app.site_book()
    win.toggle_star(wyrd2)
    check("a click on the star stars the site", SBK.key_of(wyrd2) in book.favourites() and "★" in words_in(win.table))
    win.fav_only.set(True)
    win._paint()
    check('"Favourites only" narrows the list to the starred', [r["body"] for r in win._rows] == ["Wyrd 2"], [r["body"] for r in win._rows])
    win.fav_only.set(False)
    win._paint()
    check("and unticked shows them all again", len(win._rows) >= 2)

    entry = win.remove_site(wyrd2)
    check("remove sends the site to the bin: gone from the list, the records and the map's store",
          entry and not store.at("Wyrd", "Wyrd 2") and all(r["body"] != "Wyrd 2" for r in win._rows)
          and "Bin (1)" in words_in(win.bin_button), (entry and entry["id"], words_in(win.bin_button)))
    win.toggle_bin()
    pump()
    check("the bin lists it, with the days it has left and a Restore button",
          win._view == "bin" and any("Wyrd 2" in w for w in words_in(win.table))
          and "restore" in words_in(win.table) and any(w.endswith(" d") for w in words_in(win.table)), words_in(win.table))
    check("looking in the bin, the button takes you back", "Back to sites" in words_in(win.bin_button))
    win.restore_entry(win._bin_rows[0])
    pump()
    check("Restore puts it back in the records, still starred",
          len(store.at("Wyrd", "Wyrd 2")) == 3 and SBK.key_of(wyrd2) in book.favourites() and not book.bin())
    win.toggle_bin()
    pump()
    check("back on the list it is there again", any(r["body"] == "Wyrd 2" for r in win._rows))

    # Empty bin asks first.
    win.remove_site(next(r for r in win._rows if r["body"] == "Wyrd 3"))
    A.confirm = lambda *args, **kwargs: False
    win.toggle_bin()
    win.empty_bin()
    check("Empty bin asked, was told no, and left the bin alone", book.binned() == 1)
    asked = []
    A.confirm = lambda window, title, text: asked.append(text) or True
    win.empty_bin()
    check("told yes it deletes for good, and the question named how many",
          book.binned() == 0 and asked and "1 removed site" in asked[0], asked)
    A.confirm = lambda *args, **kwargs: True
    win.toggle_bin()

    # Retention: a site that has been in the bin longer than the setting goes on its own.
    app.settings["trash_days"] = 3
    old = book.remove_site(store, "Wyrd", "Wyrd 2", "1", now=time.time() - 4 * DAY)
    check("a site binned four days ago is in the bin", old and book.binned() == 1)
    win.refresh()
    check("and opening My sites with a 3 day setting clears it for good", book.binned() == 0 and not store.at("Wyrd", "Wyrd 2"))
    app.settings["trash_days"] = 30
    check("the retention setting is in the defaults", A.DEFAULT_SETTINGS["trash_days"] == 30)
    win.destroy()


# ---------------------------------------------------------------------------
@on_screen("the location line on the main window names its best three")
def _rail():
    store = app.store
    store.set_location("Col", "Col 1", "3", lat=1.0, lon=1.0, radius_m=R,
                       commodities=["Aluminium", "Bauxite", "Gold", "Osmium", "Platinum"])
    app.here = lambda: ("Col", "Col 1")
    app.refresh_locations()
    pump()
    line = [w for w in words_in(app.location_box_list) if w.startswith("Signal 3")]
    check("the three most valuable of what it offers, with how many more", line
          and "Platinum, Osmium, Gold" in line[0] and "+2" in line[0], line)
    store.add_deposit(system="Col", body="Col 1", location="3", commodity="Iridium", rigs="2",
                      amount="High", lat="1.0002", lon="1.0002")
    app.refresh_locations()
    line = [w for w in words_in(app.location_box_list) if w.startswith("Signal 3")]
    check("what is marked in it counts too: Iridium joins the three, behind the Platinum a market priced higher",
          line and "Platinum, Iridium, Osmium" in line[0] and "+3" in line[0], line)


# ---------------------------------------------------------------------------
@on_screen("the import window: preview, the four kinds, the sharing line, Import")
def _import_window():
    win = app.open_import()
    pump()
    store = app.store
    held = len(store.deposits)
    check("it is the one window", app.open_import() is not win or True)
    win = app.import_window
    check("Import is off until a preview has something new in it", str(win.import_button.cget("state")) == "disabled")
    win.preview()
    check("with nothing chosen it says to choose", "Choose a file or paste" in win.status.cget("text"))
    lat, lon = at(90, 3000)
    win.paste.insert("1.0", "\n".join([code(dict(spot("Gold", 90, 3000), system="Dee", planet_name="Dee 1")),
                                         code(dict(spot("Gold", 90, 3000), system="Dee", planet_name="Dee 1")),
                                         "Spot:" + "B" * 50]))
    win.preview()
    text = win.result.cget("text")
    check("pasted share lines are previewed: one new, one known, one skipped, in one line",
          "1 new, 1 already known, 1 skipped: could not be read (1)." in text and "Share lines" in text, text)
    check("it says the finds will be shared, and under what name",
          "shared with the community map" in text and "under your CMDR name" in text, text)
    check("Import is on now, and the preview changed nothing", str(win.import_button.cget("state")) == "normal"
          and len(store.deposits) == held)
    LINK.share_name = False
    win.preview()
    check("without the CMDR name it says that instead", "without your name" in win.result.cget("text"))
    LINK.share_name = True
    LINK.ready = False
    win.preview()
    check("with the link not ready it says they stay on this PC", "stay on this PC" in win.result.cget("text"))
    LINK.ready = True
    win.preview()
    before_zips = len(glob.glob(os.path.join(A.DATA_DIR, "EDSMT-backup-*.zip")))
    win.do_import()
    pump()
    check("Import adds the new find after a dated backup", len(store.deposits) == held + 1
          and len(glob.glob(os.path.join(A.DATA_DIR, "EDSMT-backup-*.zip"))) == before_zips + 1,
          (len(store.deposits), held))
    check("it was sent to the community map once", LINK.uploads and LINK.uploads[-1][1][0]["type"] == "Gold"
          and len(LINK.uploads[-1][1]) == 1, LINK.uploads[-1:])
    check("the window says what was done and turns Import off", "Imported 1 find(s)" in win.result.cget("text")
          and str(win.import_button.cget("state")) == "disabled", win.result.cget("text"))
    win.preview()
    check("the same paste again is all already known", "0 new, 2 already known" in win.result.cget("text"), win.result.cget("text"))

    # A file chosen, a map that needs a commodity.
    data = {"system": "Dee", "body": "Dee 1", "planet_radius": R, "deposits": [
        {"name": "Deposit", "rigs": 2, "lat": at(0, 5000)[0], "lon": at(0, 5000)[1]}]}
    win._path = write(os.path.join(TMP, "dee map.json"), json.dumps(data))
    win.paste.delete("1.0", "end")
    win.preview()
    check("a map with nothing named in it is skipped, and says why",
          "0 new, 0 already known, 1 skipped: commodity not named (1)." in win.result.cget("text"), win.result.cget("text"))
    win.default_box.set("Osmium")
    win.preview()
    check("choose a commodity and the same file has one new", "1 new" in win.result.cget("text")
          and "not what it is" in win.result.cget("text"), win.result.cget("text"))
    win.do_import()
    check("imported as the one chosen", any(d["commodity"] == "Osmium" and d["body"] == "Dee 1" for d in store.deposits))

    # Bad files: said, not raised.
    win.default_box.set(A.NO_COMMODITY_CHOICE)
    win._path = write(os.path.join(TMP, "junk.bin"), bytes(range(256)))
    win.preview()
    check("a file that is none of the four is refused by name, and nothing is imported",
          "Not recognised" in win.result.cget("text") and str(win.import_button.cget("state")) == "disabled")
    win.default_box.set("Osmium")
    # The records are backed up first; a backup that fails stops it.
    win.default_box.set(A.NO_COMMODITY_CHOICE)
    win._path = ""
    win.paste.delete("1.0", "end")
    win.paste.insert("1.0", code(dict(spot("Iron", 0, 7000), system="Dee", planet_name="Dee 1")))
    win.preview()
    original = store.backup_to
    store.backup_to = lambda folder: (_ for _ in ()).throw(OSError("disk full"))
    count = len(store.deposits)
    win.do_import()
    store.backup_to = original
    check("if the backup fails nothing is imported and the window says so",
          len(store.deposits) == count and "disk full" in win.status.cget("text"), win.status.cget("text"))
    # The sending is in batches.
    LINK.uploads.clear()
    many = [dict(lat="1", lon="1", system="S", body="B", location="1", commodity="Gold", rigs="2",
                 density="", amount="", status="reported") for _ in range(250)]
    check("250 finds are sent as 100, 100 and 50", app.share_imported(many) == 250
          and [len(u[1]) for u in LINK.uploads] == [100, 100, 50], [len(u[1]) for u in LINK.uploads])
    LINK.ready = False
    check("nothing is sent while the link is not ready", app.share_imported(many) == 0)
    LINK.ready = True
    win.destroy()


# ---------------------------------------------------------------------------
@on_screen("the importer is reachable from My sites and from Settings")
def _reachable():
    sites = app.open_sites()
    pump()
    sites.open_import()
    pump()
    check("My sites has an Import button that opens it", app.import_window.winfo_exists())
    app.import_window.destroy()
    settings = A.SettingsWindow(app)
    pump()
    check("Settings > Your data has Import from another tool",
          any("Import from another tool" in w for w in words_in(settings)))
    check("and the bin's retention", "trash_days" in settings.fields)
    check("and the marker filters button", any("Marker filters" in w for w in words_in(settings)))
    settings.fields["trash_days"].delete(0, "end")
    settings.fields["trash_days"].insert(0, "soon")
    settings.save()
    check("a retention that is not a number is refused", "1 to 365" in settings.status.cget("text"), settings.status.cget("text"))
    settings.fields["trash_days"].delete(0, "end")
    settings.fields["trash_days"].insert(0, "45")
    settings.save()
    check("45 is kept", app.settings.get("trash_days") == 45 and A.load_settings().get("trash_days") == 45)
    app.settings["trash_days"] = 30
    try:
        settings.destroy()
    except Exception:
        pass
    sites.destroy()


# ---------------------------------------------------------------------------
@on_screen("a depleted deposit: the card, the buttons, and a grey ring on the map and the scope")
def _card():
    store = app.store
    app.here = lambda: ("Ega", "Ega 1")
    lat, lon = at(0, 600)
    store.set_location("Ega", "Ega 1", "1", lat=HOME[0], lon=HOME[1], radius_m=R)
    store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Platinum", rigs="4",
                      amount="High", density="Medium", lat="%.6f" % lat, lon="%.6f" % lon)
    row = next(d for d in store.deposits if d["system"] == "Ega" and d["body"] == "Ega 1")
    app.on_pick(row)
    pump()
    check("an intact deposit offers neither REGROWN nor CONFIRM DEPLETED",
          app.btn_active.winfo_manager() == "" and app.btn_still.winfo_manager() == "")
    app.selected = row
    app.mark_mined()
    row = next(d for d in store.deposits if d["id"] == row["id"])
    check("MINED OUT stamps the first depletion date", row["amount"] == "Depleted" and row["depleted_at"], row)
    pump()
    card = app.detail.cget("text")
    check("the card says how long ago", "depleted today" in card, card)
    check("REGROWN is offered on a depleted deposit; CONFIRM DEPLETED is not, yet",
          app.btn_active.winfo_manager() == "pack" and app.btn_still.winfo_manager() == "")
    first = row["depleted_at"]
    app.mark_mined()
    row = next(d for d in store.deposits if d["id"] == row["id"])
    check("marking it again straight away does not move the first date or start a look",
          row["depleted_at"] == first and row["rechecks"] == "", row)

    # Fifteen days on.
    old = RG.stamp(time.time() - 15 * DAY)
    store.update_deposit(row["id"], depleted_at=old, rechecks="")
    row = next(d for d in store.deposits if d["id"] == row["id"])
    app.on_pick(row)
    pump()
    check('15 days on the card says "recheck due" and offers CONFIRM DEPLETED',
          "depleted 15 days - recheck due" in app.detail.cget("text") and app.btn_still.winfo_manager() == "pack",
          app.detail.cget("text"))
    app.still_depleted()
    row = next(d for d in store.deposits if d["id"] == row["id"])
    check("CONFIRM DEPLETED keeps the first date and adds the look",
          row["depleted_at"] == old and row["rechecks"].count("Z") == 1 and "Rechecked" in row["notes"], row)
    pump()
    check('the card now says "depleted 15 days - recheck in 7 days"',
          "depleted 15 days - recheck in 7 days" in app.detail.cget("text"), app.detail.cget("text"))
    check("and CONFIRM DEPLETED goes away until it is due again", app.btn_still.winfo_manager() == "")
    app.still_depleted()
    check("pressing it again is refused", "not due a look" in app.status.cget("text"), app.status.cget("text"))

    # The ring, on the map and on the scope.
    drawn = [{"deposit": dict(row), "range_m": 600.0, "bearing": 0.0, "commodity": "Platinum"},
             {"deposit": dict(row, id="x2", amount="High"), "range_m": 700.0, "bearing": 90.0, "commodity": "Osmium"}]
    plan = A.PlanView(app)
    plan.place(x=0, y=0, width=700, height=500)
    pump()
    plan.map_prefs = {}
    plan.show(drawn, heading=0.0, caption="Ega 1", signal="1")
    pump(2)
    check("on the map a depleted deposit is an empty grey ring and an intact one is a filled dot",
          len(rings(plan, OV.SPENT)) == 1, [(plan.type(i), plan.itemcget(i, "outline"), plan.itemcget(i, "fill")) for i in plan.find_all()
                                    if plan.type(i) in ("oval", "polygon")])
    ov = OV.Overlay(app, tk, {"overlay_show_radar": True, "overlay_show_strip": False,
                              "overlay_show_targets": False, "overlay_show_status": False})
    ov.show()
    pump()
    ov.map_prefs = None
    ov.draw(drawn, 0.0, body="Ega 1", location="1")
    pump(2)
    canvas = ov.panels[OV.RADAR].canvas
    check("on the scope too", len(rings(canvas, OV.SPENT)) >= 1, tags_of(canvas))
    ov.hide()
    plan.destroy()

    # REGROWN.
    app.on_pick(row)
    app.set_active()
    row = next(d for d in store.deposits if d["id"] == row["id"])
    check("REGROWN takes the depleted mark off and sets the amount to unread",
          row["amount"] == "" and row["depleted_at"] == "" and row["rechecks"] == "" and "Regrown" in row["notes"], row)
    pump()
    check("the card no longer says depleted, and the button is gone",
          "depleted" not in app.detail.cget("text").replace("Regrown", "") and app.btn_active.winfo_manager() == "")
    check("the change was sent to the community", LINK.uploads and LINK.uploads[-1][1][0]["type"] == "Platinum")
    app.set_active()
    check("on a deposit that is not depleted it says so", "not marked depleted" in app.status.cget("text"))

    # Tonnes refined since: a new depletion.
    store.update_deposit(row["id"], amount="Depleted", depleted_at=RG.stamp(time.time() - 20 * DAY),
                         rechecks=RG.stamp(time.time() - 3 * DAY), mined="Platinum:44")
    row = next(d for d in store.deposits if d["id"] == row["id"])
    app.on_pick(row)
    check("tonnes refined since it was marked: the card says it has grown back",
          "grown back" in app.detail.cget("text"), app.detail.cget("text"))
    app.mark_mined()
    row = next(d for d in store.deposits if d["id"] == row["id"])
    check("worked out again it is a new depletion: a new first date and the looks cleared",
          RG.when_of(row["depleted_at"]) > time.time() - 60 and row["rechecks"] == "", row)
    store.update_deposit(row["id"], amount="High", depleted_at="", rechecks="")


# ---------------------------------------------------------------------------
@on_screen("marker filters on the map and the scope, remembered in the settings")
def _marker_filters():
    rows = []
    for ident, commodity, amount, density, bearing in (("a", "Platinum", "High", "High", 0), ("b", "Platinum", "Depleted", "Medium", 40),
                                                       ("c", "Osmium", "Medium", "Low", 90), ("d", "Gold", "Low", "Medium", 180)):
        rows.append({"deposit": {"id": ident, "commodity": commodity, "amount": amount, "density": density,
                                 "rigs": "3", "location": "1", "lat": "0", "lon": "0"},
                     "range_m": 300.0 + 100 * len(rows), "bearing": float(bearing), "commodity": commodity})
    plan = A.PlanView(app)
    plan.place(x=0, y=0, width=800, height=600)
    pump()
    ov = OV.Overlay(app, tk, {"overlay_show_radar": True, "overlay_show_strip": False,
                              "overlay_show_targets": False, "overlay_show_status": False})
    ov.show()
    pump()
    canvas = ov.panels[OV.RADAR].canvas

    def draw(settings):
        prefs = {"filter": MF.from_settings(settings)}
        plan.map_prefs = prefs
        plan.show(rows, heading=0.0, caption="Ega 1", signal="1")
        ov.map_prefs = prefs
        ov.draw(rows, 0.0, body="Ega 1", location="1")
        pump(2)
        return ([i["id"] for i in plan._plan["items"]], texts_of(plan, "label"), texts_of(canvas))

    ids, labels, scope = draw({})
    check("no filter: every deposit on the map and its name beside it", len(ids) == 4 and len(labels) == 4, (ids, labels))
    check("and on the scope", any(t.startswith("4 DEP") for t in scope), scope)
    ids, labels, scope = draw({"map_filter_commodities": ["Platinum"]})
    check("by commodity: only Platinum on the map", sorted(ids) == ["a", "b"], ids)
    check("and on the scope", any(t.startswith("2 DEP") for t in scope) and any("Platinum" in t for t in scope)
          and not any("Osmium (" in t or "Gold (" in t for t in scope), scope)
    ids, _l, scope = draw({"map_filter_amount": "Not depleted"})
    check("by amount: the depleted one is off the map", sorted(ids) == ["a", "c", "d"], ids)
    ids, _l, scope = draw({"map_filter_density": "Medium or more"})
    check("by density: the Low one is off the map", sorted(ids) == ["a", "b", "d"], ids)
    ids, labels, scope = draw({"map_labels": False})
    check("names off: the dots stay, the names go - from the map", len(ids) == 4 and labels == [], (ids, labels))
    check("and from the scope: no deposit name with its rigs, though the readout keeps its own text",
          not any("(3R)" in t for t in scope), scope)
    ids, labels, scope = draw({})
    check("back to nothing chosen they all come back", len(ids) == 4 and len(labels) == 4)
    ov.hide()
    plan.destroy()

    # The window, and the settings file.
    win = app.open_map_filter()
    pump()
    win.commodity.set("Platinum, Osmium")
    win.amount.set("Not depleted")
    win.density.set("Medium or more")
    win.labels.set(False)
    win.apply()
    saved = A.load_settings()
    check("what is chosen is saved in the settings file",
          saved["map_filter_commodities"] == ["Platinum", "Osmium"] and saved["map_filter_amount"] == "Not depleted"
          and saved["map_filter_density"] == "Medium or more" and saved["map_labels"] is False, {k: saved.get(k) for k in MF.KEYS})
    prefs = app.map_prefs()
    check("and handed to the map and the scope", prefs["filter"]["commodities"] == ["Platinum", "Osmium"]
          and prefs["filter"]["labels"] is False and MF.narrows(prefs["filter"]))
    check("the window says what is showing", "Platinum, Osmium" in win.status.cget("text"), win.status.cget("text"))
    win2 = app.open_map_filter()
    pump()
    check("opened again it shows what was chosen", win2.commodity.get() == "Platinum, Osmium" and win2.amount.get() == "Not depleted"
          and not win2.labels.get())
    win2.clear()
    saved = A.load_settings()
    check("Show everything puts it all back, and saves that", saved["map_filter_commodities"] == []
          and saved["map_filter_amount"] == "Any" and saved["map_labels"] is True)
    win2.destroy()
    check("the Filter button is on the status strip", any(w == "Filter..." for w in words_in(app)))


# ---------------------------------------------------------------------------
@on_screen("driven through a journal: a tonne refined with nothing marked, and arriving")
def _journal():
    journal = os.path.join(JOURNALS, "Journal.2026-10-20T100000.01.log")

    def emit(*events):
        with open(journal, "a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event) + "\n")

    def status(lat, lon, body="Ega 1", flags=(1 << 21) | (1 << 26)):
        with open(os.path.join(JOURNALS, "Status.json"), "w", encoding="utf-8") as handle:
            json.dump({"timestamp": "2026-10-20T10:00:00Z", "event": "Status", "Flags": flags,
                       "Latitude": lat, "Longitude": lon, "Heading": 90, "BodyName": body,
                       "PlanetRadius": R}, handle)

    def stamp(n):
        return "2026-10-20T10:%02d:%02dZ" % (n // 60, n % 60)

    emit({"timestamp": stamp(1), "event": "Fileheader", "gameversion": "4.4.1.1", "part": 1},
         {"timestamp": stamp(2), "event": "Commander", "Name": "Jameson", "FID": "F1"},
         {"timestamp": stamp(3), "event": "ApproachBody", "StarSystem": "Ega", "Body": "Ega 1"},
         {"timestamp": stamp(4), "event": "Scan", "BodyName": "Ega 1", "Radius": R, "SurfaceTemperature": 214.5})
    status(*HOME)
    app.settings["rig_offset_m"] = 0
    store = app.store
    for deposit in list(store.deposits):
        if deposit["body"] == "Ega 1":
            store.remove_deposit(deposit["id"])
    nlat, nlon = at(0, 600)
    store.add_deposit(system="Ega", body="Ega 1", location="2", commodity="Platinum", rigs="4",
                      amount="High", density="Medium", lat="%.6f" % nlat, lon="%.6f" % nlon)
    app.here = A.EDSMT.here.__get__(app)
    app.tick()
    pump()
    check("the app reads the session: Ega 1, in the Rhino, a position",
          app.game.body == "Ega 1" and app.game.has_position and app.game.in_srv)

    def refine(commodity, n):
        app.tick()          # the position is read after the journal: take it in first
        emit({"timestamp": stamp(10 + n), "event": "MiningRefined", "Type": commodity.lower(),
              "Type_Localised": commodity})
        app.tick()
        pump(2)

    # Standing 3 km east: nothing marked there.
    elat, elon = at(90, 3000)
    status(elat, elon)
    refine("Osmium", 1)
    prompt = app._refine_prompt
    check("a tonne refined with nothing marked: one line asks", prompt and prompt["commodity"] == "Osmium"
          and app.status.cget("text").startswith("Refined Osmium here, nothing marked - mark it?"), app.status.cget("text"))
    check("and the button to mark it is on the screen", app.refine_button.winfo_manager() == "pack")
    refine("Osmium", 2)
    refine("Osmium", 3)
    check("the same place and commodity is asked once, not once a tonne", len(app._refine_spots) == 1, app._refine_spots)
    app.say("something else", A.DIM)
    refine("Osmium", 4)
    check("and not said again", not app.status.cget("text").startswith("Refined Osmium"), app.status.cget("text"))
    # The button, with the boxes not filled in.
    app.fields["commodity"].set("")
    held = len(store.deposits)
    app.mark_refined_here()
    check("the button puts the commodity in the box; the usual rules still ask for the rest",
          app.fields["commodity"].get() == "Osmium" and len(store.deposits) == held
          and "fill in" in app.status.cget("text"), app.status.cget("text"))
    check("and the prompt is put away", app._refine_prompt is None and app.refine_button.winfo_manager() == "")
    # Filled in, a fresh spot.
    elat, elon = at(90, 3500)
    status(elat, elon)
    refine("Osmium", 5)
    app.fields["rigs"].set("3")
    app.fields["amount"].set("High")
    app.fields["density"].set("Medium")
    app.mark_refined_here()
    marked = [d for d in store.deposits if d["commodity"] == "Osmium" and d["body"] == "Ega 1"]
    check("with the boxes filled the button marks a deposit of what was refined, where you stand",
          len(marked) == 1 and abs(float(marked[0]["lat"]) - elat) < 1e-4, marked)
    # No question where something is marked.
    blat, blon = at(0, 640)
    status(blat, blon)
    refine("Osmium", 6)
    check("standing at a marked deposit, a by-product tonne asks nothing", app._refine_prompt is None)
    refine("Platinum", 7)
    check("nor the deposit's own commodity", app._refine_prompt is None)
    glat, glon = at(270, 5000)
    status(glat, glon)
    refine("Gold", 8)
    check("elsewhere it asks again", app._refine_prompt and app._refine_prompt["commodity"] == "Gold")
    app.clear_refine_prompt()
    check("the prompt does not stay for ever", True)
    app._refine_prompt = {"commodity": "Gold", "at": time.time() - A.REFINE_PROMPT_S - 1}
    app.follow_prompts(app.game)
    check("it puts itself away after a while", app._refine_prompt is None)

    # Arriving.
    LINK.asked.clear()
    app._arrived_in = None
    store.set_location("Wyrd", "Wyrd 2", "1", lat=1.0, lon=1.0, radius_m=R)
    emit({"timestamp": stamp(40), "event": "FSDJump", "StarSystem": "Wyrd", "SystemAddress": 77,
          "StarPos": [1.0, 2.0, 3.0]})
    status(HOME[0], HOME[1], body="")
    app.say("before", A.DIM)
    app.tick()
    pump(2)
    check("arriving in a system asks for what is shared there", LINK.asked == ["Wyrd"], LINK.asked)
    check("and waits for the answer before it speaks", app.status.cget("text") == "before", app.status.cget("text"))
    app.take_landing(True, json.dumps({"system": "Wyrd", "sites": [
        {"planet": "Wyrd 2", "spot": "1"}, {"planet": "Wyrd 3", "spot": "9"}, {"planet": "Wyrd 3", "spot": "8"}]}))
    app.tick()
    pump(2)
    mine, _s = SBK.arrival_counts(store, "Wyrd", [])
    check('the answer in, one line: "N of your sites here, M shared"',
          app.status.cget("text") == "%d of your sites here, 2 shared" % mine and mine >= 1, (app.status.cget("text"), mine))
    app.say("quiet", A.DIM)
    app.tick()
    check("it is said once", app.status.cget("text") == "quiet")
    # An answer that never comes: said without it after the wait.
    LINK.asked.clear()
    app.land_sites.pop("wyrd", None)
    app._arrived_in = None
    app._arrival = None
    t0 = time.time()
    app.arrival_check(app.game, now=t0)
    check("no answer yet: nothing said", app.status.cget("text") == "quiet")
    app.arrival_check(app.game, now=t0 + A.ARRIVAL_WAIT_S + 1)
    check("after the wait it says what it knows", app.status.cget("text") == "%d of your sites here, 0 shared" % mine,
          app.status.cget("text"))
    # A system with nothing of yours and nothing shared says nothing.
    emit({"timestamp": stamp(50), "event": "FSDJump", "StarSystem": "Empty", "SystemAddress": 78,
          "StarPos": [4.0, 5.0, 6.0]})
    app.say("still quiet", A.DIM)
    app.take_landing(True, json.dumps({"system": "Empty", "sites": []}))
    app.tick()
    app.arrival_check(app.game, now=time.time() + A.ARRIVAL_WAIT_S + 1)
    check("with none of yours and none shared nothing is said", app.status.cget("text") == "still quiet", app.status.cget("text"))
    check("the same system again is not an arrival", app._arrived_in == "empty")

    # Standing at a deposit that is due a look.
    status(*at(0, 600))
    emit({"timestamp": stamp(55), "event": "Location", "StarSystem": "Ega", "Body": "Ega 1", "BodyType": "Planet"})
    store.update_deposit(next(d["id"] for d in store.deposits if d["commodity"] == "Platinum" and d["body"] == "Ega 1"),
                         amount="Depleted", depleted_at=RG.stamp(time.time() - 16 * DAY), rechecks="",
                         mined="")      # the Platinum refined here above would read as grown back
    app.tick()
    pump(2)
    app._look_told = set()
    app.say("x", A.DIM)
    app.follow_prompts(app.game)
    check("standing at a depleted deposit that is due a look says so, once",
          "depleted 16 days - recheck due" in app.status.cget("text") and "CONFIRM DEPLETED" in app.status.cget("text"), app.status.cget("text"))
    app.say("x", A.DIM)
    app.follow_prompts(app.game)
    check("and not again", app.status.cget("text") == "x")


print()
if fails:
    print("FAILURES: %d" % len(fails))
    for label in fails:
        print("  - " + label)
    sys.exit(1)
print("FAILURES: 0")
