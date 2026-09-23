# Surface mining in the Player Journal

**Status of this document:** working specification, offered to EDCD.
**Game version:** Elite Dangerous 4.4.1.0 (2 September 2026) and 4.4.1.1
(3 September 2026).
**Last revised:** 17 September 2026.
**Source:** EDSMT (Radio Raxxla Surface Mining Survey), GPL-3.0. CMDR
TheAnnouncer.

Frontier shipped surface mining and the Rhino SRV in 4.4.1.0 and has not
published a journal schema for any of it. This document is what one tool has
been able to establish, written so that the next tool does not have to
establish it again.

**Read the headline before the detail: as of 17 September 2026 no
surface-mining-specific journal event has been observed at all.** Not a rig
event, not a deposit event, not a prospecting event. What follows is
therefore three things — the in-game structure any eventual schema will have
to describe, the fields on *existing* events that already carry
surface-mining data today, and a capture method that does not depend on
knowing the event names in advance.

Nothing here is padded out with what is merely likely. Where something is a
guess it is labelled as one, including guesses this project has written into
its own code.

---

## How to read the labels

Every claim below carries one of these.

| Label | Means |
|---|---|
| **OBSERVED** | Seen in the running game or in a file the game wrote. First-hand. |
| **DERIVED** | Not seen directly, but follows from something that was, or from a primary document, by a calculation anyone can repeat. |
| **INFERRED** | A guess. Usually a guess this project has acted on, which is exactly why it is flagged. |
| **REPORTED** | Somebody else's finding, named, not verified here. |
| **UNKNOWN** | Named because the gap matters, not because there is an answer. |

---

## 1. What the game presents

**OBSERVED.** Surface mining is three levels deep, and the levels are
distinct things rather than three views of one thing.

```
body                    fly to it, run the Detailed Surface Scanner
  location signal       "PLANETARY MINING LOCATION SIGNAL (3)"
                        several per body, numbered, scattered over the surface
    deposit             "PLANETARY MINING DEPOSIT (HAEMATITE)"
                        what the SRV's mineral scanner pings inside one
```

1. **The DSS reports planetary mining location signals on a body**, numbered.
   They appear alongside the biological and geological signals the DSS has
   always reported.
2. **Driving into a signal, the game lists what may be inside it** — a set of
   commodity names, with anything already worked out marked `(DEPLETED)`.
3. **Pinging with the mineral scanner inside the signal returns individual
   deposits**, each naming exactly one commodity.

The distinction that matters to any data model: **a location signal is a
promise, not an inventory.** It says haematite is somewhere in this circle;
finding it is still a driving job. A tool that collapses the two loses the
ability to say "this site offers X and nobody has found the X yet".

**OBSERVED.** A single location signal was seen offering copper, haematite,
lithium, palladium, uranium and sapphire. Only sapphire is in the 4.4.1.0
update notes. **The yield set is not limited to the commodities the update
introduced** — see §4.

**OBSERVED.** The Rhino deploys a maximum of **six** mining rigs. Frontier
has not published this number anywhere: the update notes and the store pages
say "deployable Mining Rigs" with no figure. Six is confirmed in game.

**OBSERVED.** 4.4.1.1 (3 September 2026) raised the maximum chunks a rig
extracts from 9 to 12. A balance change, not a schema change.

**REPORTED** by a community member: there is no rig deploy or collect event, and
a commander must touch down to get the nearest signal. Consistent with
everything observed here, but not verified by this project.

---

## 2. What the journal already carries

These are existing, EDCD-documented events that now carry surface-mining
data. The events are not new; what they contain is.

### 2.1 `SAASignalsFound` — the location signals

**INFERRED, and this is the biggest open question in the document.**

The DSS reports planetary mining locations in the game's UI. Whether
`SAASignalsFound` gains a corresponding entry in its `Signals` array has
**not been confirmed from a captured journal**, and if it does, **the `Type`
string is unknown.**

EDSMT therefore does not match a literal. It matches the *shape* of the
string, case-insensitively, against each signal's `Type` (or
`Type_Localised`), and stores every signal it sees regardless of whether it
matched:

```
mining|deposit|resource
```

> **Do not copy the following into a parser.** EDSMT's own test fixture uses
> `"$SAA_SignalType_PlanetaryMining;"` with `Type_Localised` of
> `"Planetary Mining Locations"`. **That string was invented to have
> something to test against. It has never been observed.** It is recorded
> here only so that nobody finds it in this project's source and mistakes it
> for evidence.

What *is* settled: the container. `SAASignalsFound` and `FSSBodySignals`
carry `Signals` as an array of `{ "Type", "Type_Localised", "Count" }`
against a `BodyName` / `BodyID` / `SystemAddress`, and that is already
documented by EDCD. A mining entry, if it exists, will be one more element in
that array.

**The single most valuable contribution anyone can make to this document is
one real `SAASignalsFound` line from a body with mining locations on it.**

### 2.2 `Scan` — which worlds hold what

**OBSERVED.** No new fields. The point is which existing fields matter, and
this is not documented anywhere because nobody has been collecting both
halves at once: nobody has published which surface deposits favour which
body types.

| Field | Why it matters here |
|---|---|
| `PlanetClass` | The strongest correlate found so far. EDSMT indexes commodity availability against this string directly, untranslated — `High metal content body`, `Metal rich body`, `Rocky body`, `Rocky ice world`, `Icy body`. |
| `SurfaceTemperature` | 4.4.1.0 makes rig efficiency depend on conditions; temperature is the one of them the journal states outright. |
| `SurfaceGravity` | Drives whether the SRV can work the site at all. |
| `Radius` | Required — see §2.3. |
| `AtmosphereType`, `Volcanism` | Collected on suspicion, not yet correlated with anything. Say so rather than implying a finding. |

**DERIVED — units.** These are the journal's own units, not the ones the game
UI shows, and the difference bites.

- `Radius` is metres.
- `SurfaceTemperature` is kelvin.
- **`SurfaceGravity` is m/s², not g.** The journal reference's own worked
  example carries `Radius` 2011975 and `SurfaceGravity` 2.495225. For a rocky
  body of that size, `g = GM/r²` lands at roughly 2 m/s², and the game
  displays such a body as 0.25 g. So the journal figure is m/s² and dividing
  by 9.80665 gives the number a commander will recognise. Reading it as g
  yields 250 g, which is obviously wrong the moment anyone looks — and is
  exactly the sort of thing worth pinning down in writing.

**DERIVED — a `Volcanism` trap.** The journal writes `"No volcanism"` as an
*empty string* on some bodies and omits the key entirely on others. Both mean
the same thing. "Key absent" and "no volcanism" are different answers to the
question "does volcanism correlate with deposits", so a reader should
normalise the empty string to an explicit `None` rather than leaving it
indistinguishable from unknown.

### 2.3 `Status.json` — position, and the radius the maths needs

**OBSERVED.** No new flags. Bits 1 (Landed), 21 (Has Lat Long) and 26 (In
SRV) are already documented by EDCD and are all that surface mining needs.

The surface-mining-specific points:

- **`Latitude` / `Longitude` are the deposit's identity.** The game hands
  them over directly, so a deposit records *where it is* — not a bearing and
  a range from a centre the commander had to stop and place first. §5 of the
  appendix explains why this is not a style choice.
- **Read them only when bit 21 is set**, or a stale position from before the
  last landing is silently attributed to a new find.
- **`PlanetRadius` is metres** and is what great-circle distance between two
  surface positions must be computed against. It is not always present. When
  it is missing, a prior `Scan` event's `Radius` for the same body is the
  fallback — the same number from a different place.

### 2.4 `Touchdown` — and one thing it is good for

**OBSERVED.** `Touchdown` carries `Latitude` / `Longitude`. Inara's
`addCommanderTravelLand` accepts those as `stellarBodyCoords`, so a landing
at a mining site can be reported without the commander typing anything. Of
interest to anyone writing an Inara integration; not a schema finding.

### 2.5 `Market.json` and the commodity IDs — **corrected**

**This section previously said the opposite and was wrong.**

**DERIVED, verified 17 September 2026** against
`raw.githubusercontent.com/EDCD/FDevIDs/master/commodity.csv`:
**all thirteen 4.4.1.0 commodities are present**, in one contiguous block of
IDs, `129046165`–`129046177`:

| id | symbol | name |
|---|---|---|
| 129046165 | `Iridium` | Iridium |
| 129046166 | `Helium` | Helium |
| 129046167 | `Helium3` | Helium-3 |
| 129046168 | `Bastnasite` | Bastnasite |
| 129046169 | `Deuterium` | Deuterium |
| 129046170 | `Thortveitite` | Thortveitite |
| 129046171 | `QuartzPyroxenite` | Quartz Pyroxenite |
| 129046172 | `Olivine` | Olivine |
| 129046173 | `PericlaseDunite` | Periclase Dunite |
| 129046174 | `Sapphire` | Sapphire |
| 129046175 | `Diamond` | Diamond |
| 129046176 | `Ruby` | Ruby |
| 129046177 | `Magnesite` | Magnesite |

EDSMT's notes claimed these were *missing* from the community commodity-ID
list, and built a rationale for reading `Market.json` on that basis. They are
there now. **UNKNOWN:** when they were added — this project has not
established that, only the present state.

What that changes: the ID mapping is solved and belongs to EDCD, not to any
individual tool. What it does not change: whether the market and pricing
services have *data* for these commodities, and whether any of them expose a
search by commodity, are separate questions this project has not verified.
Do not read this table as evidence that prices are available anywhere.

**DERIVED — a spelling trap worth writing down.** FDevIDs gives the name as
**`Bastnasite`**, unaccented. Frontier's own 4.4.1.0 notes spell it
**Bastnäsite** with the umlaut. The journal may write `$bastnasite_name;`,
the market may localise it, and a commander typing it by hand will not reach
for the umlaut. Any tool comparing these must fold first — strip accents,
drop non-alphanumerics, lowercase — or one commodity files under two names
and no search finds half of it.

The same problem exists in the other direction and already has a victim:
FDevIDs carries `Methanol Monohydrate Crystals`; the shorter form
`Methanol Crystals` is in circulation. Folding does not close that gap. An
explicit alias table does.

---

## 3. What is not established

Named individually, because a gap somebody can see is worth more than a gap
they have to discover.

| # | Question | Status |
|---|---|---|
| 3.1 | Does any surface-mining-specific journal event exist? | **UNKNOWN.** None observed to 17 Sep 2026. |
| 3.2 | The `Type` string for a mining location signal | **UNKNOWN.** See §2.1. |
| 3.3 | Does the journal record an individual deposit at all — position, commodity, size? | **UNKNOWN.** Currently only the commander sees it, on screen. |
| 3.4 | Rig deployment, extraction and collection | **UNKNOWN.** No event observed. **REPORTED** as absent by a community member. |
| 3.5 | Deposit density: the field name | **UNKNOWN.** See §5.2. |
| 3.6 | Deposit density: the tier vocabulary | **UNKNOWN.** The game shows tiers; nothing says what the journal would call them. |
| 3.7 | Whether extracted material arrives as `MiningRefined`, as a direct `Cargo.json` change, or otherwise | **UNKNOWN.** |
| 3.8 | Whether `$commodity_name;` symbol forms appear for the new commodities | **INFERRED** that they might; handled defensively, never observed. |

**REPORTED** by a community member: surface deposit sites are deterministic, generated
by a PRNG seeded on the body address, with latitude, longitude, radius and
the boundary geometry all derivable offline. Not verified by this project,
and flagged here because if it holds it changes what is worth recording:
positions become free, and only *depletion state* — which is server-side and
not derivable — stays valuable.

**Precedent worth knowing**, REPORTED: Frontier shipped journal events for
colonisation roughly five to six weeks after that feature went live. On that
pattern, surface-mining events would land early-to-mid October 2026. This
document is written to be updated, not to be final.

---

## 4. The commodity set

**OBSERVED.** The thirteen commodities in the 4.4.1.0 notes are what was
**new**, not what surface mining yields. Long-standing commodities come out
of the ground too — copper, haematite, lithium, palladium, uranium and others
have all been seen offered by a location signal.

**The consequence for anyone writing a parser: do not treat any list as a
whitelist.** Refusing to record a commodity because it is absent from a list
written by somebody who had not yet seen the feature is how the first
sighting of something uncatalogued gets thrown away. Accept whatever the game
names, tidy the spelling, and keep it.

The thirteen from the update notes, for reference — these are the *new* ones,
and are the set matching the FDevIDs ID block in §2.5:

Bastnäsite, Deuterium, Diamond, Helium, Helium-3, Iridium, Magnesite,
Olivine, Periclase dunite, Quartz pyroxenite, Ruby, Sapphire, Thortveitite.

---

## 5. Capturing the schema without knowing its names

The method, since it is reusable and is the only part of this that works
before Frontier publishes anything.

### 5.1 Capture by shape, log the first of each

Match the **event name** against a deliberately loose pattern, and write the
first raw line of each distinct event name to a file:

```
rig|deposit|mining|mineral|refin|extract|prospect
```

Case-insensitive, matched against `event`. One example per name, never a
running log — the point is a specimen, not a transcript. EDSMT writes these
to `journal-mining-events.log`, which is what a commander is asked to attach
to a report.

Then walk the captured event for a commodity name, at any depth, under any
of these keys: `Name`, `Type`, `Commodity`, `Material`, `Resource`,
`Mineral`, `Name_Localised`, `Type_Localised`. Accept all of `Magnesite`,
`magnesite`, `$magnesite_name;`, a name nested under a `Deposit` object, and
a name inside a `Materials` array.

This costs nothing when the event does not exist, and the day it does, the
tool names it instead of guessing.

### 5.2 Density: look for the idea, not the key

4.4.1.0 balances "deposit capacity per density level" and rig "efficiency
based on deposit density", so density is worth as much as the commodity name
— and **UNKNOWN** is the honest status of every part of how it is written
down.

EDSMT searches for any of these keys, at any depth: `density`, `richness`,
`quality`, `grade`, `concentration`, `abundance`, `size`. A string value is
matched against a tier ladder; a bare number is treated as a 0–1 or 0–100
scale and bucketed onto the same ladder.

Every one of those key names is a guess. They are listed so that the guess is
visible and so that a single confirmed sighting collapses the list to one
entry.

---

## 6. Why depletion is the part that cannot be generated

**Primary, quoted.** Frontier's August 2026 dev log, on surface deposits:

> once collected these deposits will regenerate at a very slow rate

This is the single most consequential sentence for anyone building against
this feature, and it is a schema concern rather than a design opinion.

Ring hotspots are permanent, so a hotspot database is written once and stays
true. Surface deposits are not. A shared database of them **decays**, and a
tool that presents a six-month-old find the same way it presents yesterday's
is actively sending commanders on wasted trips.

What follows for a data format: every record needs a timestamp that is part
of the ranking rather than a column the reader is left to interpret, sites
need a "last confirmed by anybody" separate from "first found", and a
stripped site must be reportable without being deleted — it recovers, because
that is what the game does.

*This quotation is reproduced from this project's notes. The
elitedangerous.com update notes returned HTTP 403 to automated fetching on
17 September 2026, so it has not been re-verified against the published page
in preparing this document. Check it before citing it.*

---

## Appendix A — implementation notes for a journal reader

Not surface-mining-specific, and mostly not in EDCD's documentation either.
Four of these cost this project a release each, and any reader that works has
had to arrive at all of them.

**1. The sticky EOF flag.** Once a Python file object reaches the end of a
file, `read()` keeps returning empty **even as the game appends**. Open a
journal, read to the end, and you never see another event — the tool reads
once and goes blind for the rest of the session, silently, with no error.

The fix: track the offset yourself, and **seek to the end and back to your
offset before every read**, on an unbuffered binary handle.

```python
handle = open(path, "rb", 0)
...
handle.seek(0, os.SEEK_END)      # clears the flag
handle.seek(offset, os.SEEK_SET) # back to where we were
chunk = handle.read()
offset = handle.tell()
```

Language-specific in its details, universal in its shape.

**2. Never gate a `Status.json` read on mtime or size.** Windows does not
reliably refresh a file's directory entry while another process is rewriting
it, so both can look unchanged when the contents have moved on. `Status.json`
is a few hundred bytes and the game rewrites it several times a second: read
it whole, every tick, and accept that a torn read either comes back empty or
fails to parse. Both just mean waiting for the next tick.

The same applies to `Cargo.json` and `Market.json`. For `Market.json`, decide
freshness on the `timestamp` **inside** the file plus `MarketID`. For
`Cargo.json`, decide on the contents — the file can be rewritten twice inside
one second, which is the resolution its own timestamp has.

**3. Journal first, `Status.json` second.** `Status.json` carries the current
`BodyName` and is the fresher of the two, so it must get the last word. The
other way round, an `FSDJump` replayed out of the journal wipes a body the
game has already said you are back at.

**4. Hold back torn lines.** The game can be caught mid-write. An incomplete
trailing line must be held and glued to the front of the next read. Parse it
as it stands and half an event is consumed and the rest is lost when it
arrives — which produces a bug that appears only under load and never
reproduces on demand.

**5. Sort journals by modification time, not by filename.** Two filename
formats are in circulation — `Journal.220315123456.01.log` and
`Journal.2026-09-08T120000.01.log` — and sorting by name puts the newer style
last. Modification time is the only ordering that survives both.

**6. React to `Continued` immediately.** The game closes a journal and opens
the next part at around 500,000 lines. Switch on the event rather than
waiting for a timestamp or an mtime to change, or the events either side of
the split are lost. Expect a short window where the event has arrived and the
new file does not yet exist; wait for it rather than re-reading the old file
from the top.

**7. Ask Windows where Saved Games is.** Use `SHGetKnownFolderPath` with
`{4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4}` rather than assuming
`%USERPROFILE%\Saved Games`. The folder can be redirected, and it is
*localised in Explorer* while staying "Saved Games" on disk. Check the
OneDrive path and the Steam Play prefix
(`steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games`) too.

**8. Positions, not bearings — a data-format warning paid for in lost
records.** Store a deposit as latitude and longitude, and compute ranges and
bearings against wherever the commander is standing, on demand.

An earlier version of EDSMT stored a bearing and a range from a centre the
commander set by hand. When that centre was removed, uploads kept sending
`direction: 0.0, distance: 0.0` as filler because the server still required
both fields — and the server hashed those two numbers into each deposit's
identity. Every deposit of the same commodity at one site therefore arrived
with an identical fingerprint and everything after the first was discarded as
a duplicate, silently. The response read `{"accepted": 1, "duplicates": 4}`,
which is indistinguishable from a commander leaning on the key.

Two rules came out of it, and both generalise past this project:

- **The coordinates are the identity.** Bucket latitude and longitude to
  three decimal places — roughly 35 m on a small rocky body. Real deposits
  sit hundreds of metres apart, so that absorbs two commanders parking
  differently without ever merging two genuine finds.
- **When a field stops being computed, delete it from the contract.** A
  required field filled with a constant is worse than a missing one, because
  everything downstream carries on trusting it.

---

## Appendix B — checked against EDCD, and already documented

Verified 17 September 2026 against the Elite Dangerous Player Journal
documentation EDCD maintains and against EDCD's own
repositories, so that this document claims only what is not already covered.

**Already documented — not restated above except where surface mining adds
something:**

- `SAASignalsFound` and `FSSBodySignals`, including the `Signals` array of
  `Type` / `Count` and the `Genuses` array. *(Exploration)*
- `Scan`, including `Radius`, `SurfaceGravity`, `SurfaceTemperature`,
  `PlanetClass`, `AtmosphereType` and `Volcanism` as field names. *(The
  units are not stated there — see §2.2.)* *(Exploration)*
- The complete `Status.json` `Flags` and `Flags2` bit tables, and the
  `Latitude`, `Longitude`, `Heading`, `BodyName`, `PlanetRadius` fields.
  *(Status File)*
- `MarketSell`, `MarketBuy`, `MiningRefined`, `AsteroidCracked`,
  `CollectCargo`, `EjectCargo`. *(Trade)*
- `ProspectedAsteroid`, `Continued`, `CargoTransfer`, `LaunchSRV`, `DockSRV`,
  `SRVDestroyed` — and `SRVType` on the SRV events, added for Odyssey.
  *(Other events)*
- `Touchdown`, `Liftoff`, `Location`, `FSDJump`, `CarrierJump`,
  `SupercruiseExit`, `ApproachBody`. *(Travel)*
- `Fileheader`, `Commander`, `LoadGame`, `Cargo`. *(Startup)*
- The journal file format and naming. *(File Format)*
- **All thirteen 4.4.1.0 commodities, with IDs**, in `EDCD/FDevIDs`
  `commodity.csv`. *(See §2.5 — this corrects an earlier claim of ours.)*

**Not documented anywhere found:**

- Any planetary mining location signal `Type` value.
- Any event, field or file relating to mining rigs, surface deposits, or
  deposit density.
- Any Rhino-specific `SRVType` value.
- The units on `Scan`'s `SurfaceGravity` (§2.2).
- The `Volcanism` empty-string convention (§2.2).

**Not checked:** whether an EDDN schema exists or is proposed for surface
mining. The EDDN repository's schema list could not be enumerated from this
environment.

---

## Provenance, and how to correct it

Everything labelled **OBSERVED** was seen by CMDR TheAnnouncer in 4.4.1.0 /
4.4.1.1 between 2 and 17 September 2026. Everything labelled **DERIVED** can
be reproduced from the sources named beside it. Everything labelled
**INFERRED** is a guess and should be treated as one, including the guesses
this project has shipped.

EDSMT is GPL-3.0 and its journal reader is `journal.py`; the reasoning behind
the defensive parsing is in `JOURNAL-NOTES.md`. Corrections, and especially a
single real captured event, are more welcome than agreement.
