# What EDSMT reads from the journal

Written down because most of it is not obvious, and two of these cost me a
release each.

## The files

    %USERPROFILE%\Saved Games\Frontier Developments\Elite Dangerous\

Windows is asked where Saved Games actually is via `SHGetKnownFolderPath`
rather than assuming `%USERPROFILE%` — the folder can be redirected, and it is
localised in Explorer while staying "Saved Games" on disk. OneDrive and the
Steam Play prefix are checked too.

    Status.json      rewritten several times a second while playing
    Journal.*.log    one JSON object per line, appended as events happen
    Cargo.json       what is in the hold, rewritten whenever it changes
    Market.json      the commodity market at the station you are docked at

**Cargo.json and Market.json are read WHOLE, not tailed.** The game rewrites
them from scratch, so there is no offset to track and nothing to seek to —
but for exactly that reason they can be caught half-written, and a partial
read raises `JSONDecodeError` rather than returning half a hold. Every read
is wrapped and a failed one keeps the last good value instead of reporting an
empty ship. A torn read is an ordinary event, not an error worth telling the
commander about.

## Two deposits are not the same deposit because you removed the centre

Not a journal lesson, but it cost a release of shared data, so it lives here.

The app used to record a bearing and a range from a spot centre you set by
hand. When the centre went, the upload kept sending `direction: 0.0,
distance: 0.0` as filler, because the server still demanded both fields. The
server hashed those two numbers into a deposit's identity. Every deposit of
the same commodity at the same site therefore arrived with an identical
fingerprint, and everything after the first was discarded as a duplicate -
silently, with `{"accepted": 1, "duplicates": 4}` looking exactly like a
commander who pressed the key twice.

The fix is that the coordinates ARE the identity: latitude and longitude
bucketed to three decimal places, roughly 35 m on a small rocky body. Real
deposits sit hundreds of metres apart, so that absorbs two commanders parking
differently without ever merging two genuine finds. Bearing and range are
still accepted, still stored, and never used to decide sameness.

The general rule: when a field stops being computed, delete it from the
contract. A required field filled with a constant is worse than a missing one,
because everything downstream keeps trusting it.


## Reading them without going blind

**The sticky EOF flag.** Once a Python file object reaches the end of a file,
`read()` keeps returning empty even as the file grows. Open a journal, read to
the end, and you never see another event. The fix is to track the offset
yourself and seek to the end and back before every read, unbuffered binary.
Every journal reader that works has arrived at this; it is not optional.

**Torn lines.** The game can be caught mid-write. An incomplete trailing line
is held back and glued to the next read, otherwise half an event is parsed and
the rest is lost when it arrives.

**Never skip Status.json on a timestamp.** Windows does not reliably refresh a
file's directory entry while another process is rewriting it, so mtime and
size can look unchanged when the contents have moved on. It is a few hundred
bytes; read it every tick.

**Journal first, Status.json second.** Status.json carries the current
`BodyName` and is the fresher source, so it gets the last word. The other way
round, an `FSDJump` replayed from the journal wipes a body the game has
already said you are back at.

**Newest journal by modification time, not filename.** Filenames come in two
formats — `Journal.220315123456.01.log` and
`Journal.2026-09-08T120000.01.log` — and sorting by name puts the new style
last. Sorting by modification time is the only ordering that survives both.

## Events used

| Event | For |
| --- | --- |
| `Fileheader` | game version, journal part number |
| `Continued` | at 500k lines the game starts a new part — switch immediately rather than waiting for a timestamp |
| `Commander`, `LoadGame` | CMDR name and Frontier ID. Inara requires these to come from the journal, not be typed, so they match in-game exactly |
| `Location`, `FSDJump`, `CarrierJump`, `SupercruiseExit`, `ApproachBody` | where you are |
| `Touchdown` | carries `Latitude`/`Longitude`. Inara's `addCommanderTravelLand` accepts these as `stellarBodyCoords` |
| `Scan` | `Radius`, `SurfaceTemperature`, `SurfaceGravity`. Units are the journal's own: metres and kelvin, not what the game UI shows. Temperature matters because rig efficiency depends on it |
| `SAASignalsFound`, `FSSBodySignals` | what the DSS found on a body, as a `Signals` array of `Type`/`Count` |
| `MarketSell` | the sale. `Type`, `Count`, `SellPrice`, `TotalSale`, `AvgPricePaid`. `Type_Localised` is **not** in EDCD's reference but the game does send it, so it is preferred when present |
| `Docked`, `Undocked` | `StationName`, `MarketID`. Undocking is what banks a run, but only once something has been sold — undocking with nothing sold is a stop on the way |
| `CargoTransfer` | `Transfers[]` of `Type`, `Count`, `Direction` ∈ `tocarrier` / `toship` / `tosrv`. `Type_Localised` is **not** documented inside the Transfers array |
| `Liftoff` | ends the surface part of a run |
| `LaunchSRV`, `DockSRV`, `SRVDestroyed` | a Rhino session starts and ends. `SRVType` `mev_rhino` is the Rhino |
| `Loadout` | `CargoCapacity` - the ship's hold, shown against what is in it |
| `FSSDiscoveryScan`, `FSSAllBodiesFound` | the honk - the guide's first step |

## What a run is worth, and the three ways of getting it wrong

(Since 1.10030 the books count Rhino sessions from `MiningRefined`,
`CargoTransfer` and `DockSRV` - see "A Rhino session" below. The reader still
works out hold gains as described here, and still holds both holds.)

**Cargo.json describes ONE VESSEL at a time.** It carries a `Vessel` field of
`"Ship"` or `"SRV"`. Move forty tonnes of ore from the SRV into the ship and
the ship's hold rises by forty — which reads exactly like mining forty more
tonnes. `CargoTransfer` credits are banked per vessel and spent against the
next rise on the receiving side, so the transfer cannot pay twice.
`tocarrier` credits nothing: it leaves the run.

**First sight of a vessel's hold is a baseline, not a haul.** Start the app
halfway through a run with thirty tonnes already aboard and a naive reader
books thirty tonnes of mining that happened before it was looking.

**Gross is not profit.** `AvgPricePaid` is 0 on mined cargo, so for a real
haul gross and profit are the same number. The subtraction exists so that a
hold of *bought* goods going over the same counter cannot report its purchase
price as mining profit.

Cargo taken on while docked is not counted as ore for the same reason.

## Two spellings of the same commodity, in the same game

The journal writes `lowtemperaturediamond`. Everything else — the market, the
update notes, the commander — writes **Low Temperature Diamonds**. Folding
cannot close that gap, because one is singular and the other is plural, and
no amount of accent-stripping makes `diamond` equal `diamonds`.

That needs an explicit map, not a smarter fold. Without it the same commodity
files under two names and a session's `sold` column stops matching its
`mined` column.

## Status.json

`Flags` bit 21 says whether `Latitude`/`Longitude` are currently valid — they
are read only when it is set, so a stale position is never used. Bit 1 is
landed, bit 26 is in the SRV. `PlanetRadius` is in metres and is what the
bearing and distance maths uses; a `Scan` event fills it in when Status.json
has not.

## Market.json

    %USERPROFILE%\Saved Games\...\Market.json

Rewritten every time you open a commodity market. Read for the same reason
the journal is: the thirteen 4.4.1.0 commodities are **missing from the
community commodity-ID list** that the third-party market services key off,
and none of those services expose a commodity search. So nothing out there can
price them. Every player's own journal can.

Freshness is decided by the `timestamp` inside the file plus `MarketID`, not
by mtime — same reason as Status.json. Only the surface-mining rows are kept;
everything else at the station is somebody else's problem.

Parsing is deliberately defensive. Every field is optional, a row with no
price is dropped, and an unrecognised commodity is skipped rather than
guessed at.

## Density

4.4.1.0 balances "deposit capacity per density level" and rig "efficiency
based on deposit density", so density is worth as much as the commodity name.
The field it arrives in is undocumented, so the app looks for the idea rather
than a key: `density`, `richness`, `quality`, `grade`, `concentration`,
`abundance`. A string is matched against the tier ladder
(Depleted / Low / Medium / High / Pristine, plus the obvious synonyms); a bare
number is treated as a 0-1 or 0-100 scale and bucketed onto it.

If the game turns out to use different words, they land in
`journal-mining-events.log` and the ladder is one list to update.

## The three levels

The DSS reports **Planetary Mining Location Signals** on a body, numbered.
Drive into one and the game lists what might be inside, with anything already
worked out marked `(DEPLETED)`. Ping with the mineral scanner and you get
**Planetary Mining Deposits**, each naming one commodity.

EDSMT stores locations and deposits separately, because a location is a
promise rather than an inventory: it says haematite is somewhere in this
circle and you still have to go and find it.

## Positions, not bearings

Status.json gives latitude and longitude directly, so a deposit records where
it is. Ranges and bearings are worked out against wherever the commander is
standing, on demand. The alternative - storing a bearing and a distance from
a centre the commander had to stop and place first - makes the data useless
the moment you approach from a different direction, and adds a step before
anything can be recorded at all.

## The commodity list is not a whitelist

The 4.4.1.0 notes listed thirteen commodities, but they only listed what was
NEW. Surface mining also yields long-standing ones: a single location signal
was seen offering copper, haematite, lithium, palladium, uranium and
sapphire, and only sapphire is in the update notes.

So the list is suggestions. Anything the game names is accepted, tidied to a
consistent spelling and remembered. Refusing an unknown commodity would mean
throwing away the first sighting of something nobody has catalogued - which
is exactly the data worth having.

## Spelling

Frontier write **Bastnäsite** with an umlaut in the update notes. The journal
may write `$bastnasite_name;`, the market may localise it, and a commander
typing it by hand will not reach for the umlaut. All of them are folded —
accents stripped, non-alphanumerics dropped, lowercased — before comparison,
so one commodity stays one commodity. This is not cosmetic: without it half
the shared database files under a second name and no search finds it.

## Surface mining, September 2026

Frontier has not published the journal schema for surface mining. Rather than
guess event names, anything matching `rig|deposit|mining|mineral|refin|
extract|prospect` is captured to `journal-mining-events.log` and scanned for a
commodity name, in whatever form it appears — `Magnesite`, `magnesite`,
`$magnesite_name;`, nested under `Deposit`, or inside a `Materials` array.

The DSS now detects Planetary Mining Locations. The signal `Type` string for
them is undocumented, so mining sites are counted by matching
`mining|deposit|resource` against the signal types, and every signal seen is
kept regardless.

That log file is worth sharing. It is exactly what the community needs to
document the schema properly.

## What Frontier said that changes the design

From the August 2026 dev log, on surface deposits:

> once collected these deposits will regenerate at a very slow rate

This is the single most important sentence for anyone building a tool around
this. Ring hotspots are permanent, so a hotspot database is written once and
is true forever. Surface deposits are not: a shared database of them decays,
and a tool that presents a six-month-old find the same way it presents
yesterday's is actively sending people on wasted trips.

So every deposit carries when it was logged, every site carries when anybody
last confirmed it, ranking is decayed by that age, and a commander can report
a site as worked out. A stripped site is not deleted — it recovers over time,
because that is what the game does.

Frontier also framed the community question themselves in the same dev log:
whether players would share their finds or hide them. This tool is a bet on
sharing.

## Checked against a commander's real journals, September 2026

Twelve journals, read for shapes and counts only. What they settle:

- **One `MiningRefined` per tonne, in the SRV too.** It carries `Type`
  (`$rhodplumsite_name;`) and `Type_Localised`, and nothing else - no
  position, no body. The SRV's `Cargo` count rises with it, up to a second
  late: 47 refined against 46 in the hold, 67 against 67, 3 against 3. The
  tonne is placed by where the SRV is at that moment, and by-products arrive
  under their own names (Rhodplumsite 56 with Iridium 11 off one site).
- **`MiningRefined` must not name the deposit.** It is what came out, and a
  by-product would re-file the next deposit marked. It goes to the books only.
- **The journal's `Cargo` event lists an `Inventory` only in the first one of
  a file** (17 of 2,301 for the ship, 2 of 425 for the SRV). The rest say
  Cargo.json was rewritten. That first one is the only record of the ship's
  hold while the commander is out in the SRV.
- **Mining locations**: `"Type": "$PlanetaryMiningLocation_Name;"` in
  `FSSBodySignals` and `SAASignalsFound`, with a `Count`.
- **No rig event of any kind.** Deploying a rig writes nothing, so RIG DOWN
  stays a key.
- **`Touchdown` and `Liftoff` carried no `NearestDestination`** in any of 36.
- **`LaunchSRV`** names the Rhino as `"SRVType": "mev_rhino"`.
- **`CargoTransfer`**: `Transfers[]` of `Type`, `Count`, `Direction`, exactly
  as documented; seen `toship`.

Not settled by the journals, because Status.json is not journaled: a targeted
mining location in `Status.json` → `Destination.Name` has been reported as
`$SAA_Unknown_Signal:#index=15;`. EDSMT reads the number when it is there and
writes every distinct destination name of that kind to the event log, so the
real shape can be checked.

## A Rhino session, checked against 135 more journals on 4.4.x, 25 Sep 2026

Read-only, for shapes and counts only, never a commander's identity. What
they settle, and what Earnings is now built on:

- **A session is `LaunchSRV` to `DockSRV`.** Both carry `"SRVType":
  "mev_rhino"` and `"SRVType_Localised": "SRV Rhino"`; `LaunchSRV` adds
  `Loadout`, `ID` and `PlayerControlled`.
- **The Rhino empties into the ship without boarding.** `CargoTransfer` with
  `Direction: "toship"` - 72 t at a time in the sessions read, several per
  session - and the Rhino goes straight back to mining. `DockSRV` comes once,
  at the end, and a `Cargo` for `Vessel: "Ship"` follows it with the ship's
  total.
- **A relog in the Rhino** starts a new journal with `Location` carrying
  `"InSRV": true` and no `LaunchSRV` before it - so a login in the Rhino
  carries the session on.
- **`MiningRefined` is also the ship mining asteroids** - thousands of them in
  the same journals - so a tonne only counts while the Rhino is out.
- **Several tonnes share one second.** Three `MiningRefined` for the same
  commodity inside one second is normal, so each is numbered by the reader
  and a restart can tell a third tonne from the same tonne read again.
- **What a mining location holds is not in any journal event.**
  `SAASignalsFound` and `FSSBodySignals` give a count of
  `Planetary Mining Location` and nothing else; no 4.4 event lists the
  commodities the game shows when one is targeted. EDSMT logs every distinct
  `Status.json` `Destination` to the event log, in case a later build puts
  them there.
- **New in 4.4 journals, never seen before them:** nothing mining-related.

## Versions

4.4.1.0 (2 Sep 2026) shipped surface mining. 4.4.1.1 (3 Sep 2026) raised the
maximum chunks a rig extracts from 9 to 12 — a balance change, not a schema
one. As of 8 September 2026, 4.4.1.1 is still the latest.

**Six rigs.** Worth writing down because Frontier never published the number —
their update notes and the Rhino store pages all say "deployable Mining Rigs"
with no figure. Six is confirmed in game. The app offers 1-6 and the API
rejects anything above it, which also catches a typo before it becomes a
permanent row in everyone's database.
