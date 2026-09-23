# EDSMT — patch notes

The version is in the app's title bar. Quote it on a bug report.

---

## 1.10028

### Fixed — an update could wipe your settings

Updating to the last build reset some commanders' overlay layout, hotkeys
and switches to the defaults. The cause was two things together: settings
were written straight over the old file, and a settings file that could not
be read at that moment was replaced with the defaults.

Both are gone. Every save now goes to a temporary file and replaces the old
one only once it is complete, the last good copy is kept beside it as
`settings.json.bak`, and a file that cannot be read is set aside and the
backup used instead — never overwritten. If that ever happens, the status
line says so. Only one copy of EDSMT can run at a time now, and the installer
waits for it to close rather than updating it underneath itself.

### New — updates fetch themselves

When a new version is out, EDSMT downloads it in the background from
radioraxxla.com, and keeps it only if it matches the checksum published
beside it, byte for byte. The button in the title bar then reads **INSTALL
UPDATE**. Nothing is installed until you press it, so it never closes on you
mid-run. Press it and EDSMT closes, updates, and opens again with everything
as it was. Settings → *This build* has the switch if you would rather it
asked first.

This build is the last one you fetch from the website by hand.

### New — Where to land

A **Where to land** button in the title bar lists every landable body in the
system, best first, and fills itself in as you scan: honk, resolve bodies in
the FSS, map one with the DSS, and it keeps up without a click. Each body
shows an estimated value and one line saying why — known sites still intact,
mining locations nobody has shared yet, not mapped, or nothing found — with
the DSS count, what that kind of ground usually carries, what has already been
shared there, your own finds, and how much you have surveyed.

What a kind of ground usually carries comes from everyone's shared finds once
there are enough of them, and from the commodity tables until then. The list
says which, every time.

### New — Survey area: know you have covered all of it

Press **CENTRE** in the middle of an area and **BORDER** at its edge. The map
draws the circles to drive, spaced so the scanner's reach overlaps, and
shades everywhere your SRV has covered. The Survey area panel and the STATUS
box show **AREA SWEPT** as a percentage, and it reads 100% only when all of
it is. Kept per body, saved as you go, so you can finish tomorrow.

### New — Rig down, and TOO FAR FROM RIG

Press **RIG DOWN** — or its key — as you drop each rig. One key for all six:
they are numbered for you and drawn on the map and the scope. STATUS shows
how many are down and how far the farthest is. Drive past your limit from any
of them (1,000 m unless you change it in Settings) and every overlay box you
have open says **TOO FAR FROM RIG** with its number, in red, with a warning
sound if you want one. It sounds once per trip out, not every second you are
over the line. **ALL UP** when you have collected them.

### New — everyone's finds on your map and overlay

Arrive on a body and the finds other commanders have shared there appear on
the map, the scope and the deposit card as diamonds, so yours and theirs are
never confused. Click one to see who shared it and when. A shared find
sitting on one of your own is shown once, as yours.

### New — UPDATE a deposit instead of marking it twice

**UPDATE** sits beside MARK DEPOSIT. On a deposit you have already marked, it
writes what the boxes say onto that deposit — the Amount going down as you
work it, the rig count once you know it — and stamps the note with when. If
you share, the shared copy is updated too. MARK now asks first if you already
have that commodity marked within 100 m; press it again to add a separate one.

### Fixed — the lists open as you click and type, and Tab works

Every box with a list — commodity, rigs, amount, density, and the ones in the
edit windows — now opens it as soon as you click in or start typing, narrows
it as you type, and takes the highlighted choice on Enter or Tab. Tab moves
down the boxes in order. Tabbing through a box without typing leaves it as
it was.

### Fixed — windows that cut information off

The Find table dropped its last columns — **Found by** included — on anything
but a very wide screen, and cut long commodity lists after 34 letters. The
table now scrolls sideways when it has to and wraps long cells instead. The
edit windows size themselves to what is in them, so Save is never off the
bottom, and a long body name is shown whole. On a narrow window the title bar
buttons move under the readouts rather than squashing the system name and
your commander name.

### Fixed — an overlay box could crash the app

A box closed out from under the overlay took the app down on the next redraw.
It is now put back where it was instead. Reported by **Raizo/Drakain [IHCF]**
with a crash log — thank you.

### Fixed — a protected Saved Games folder

When Windows refuses to let EDSMT read the journal folder, the title bar now
says **NO ACCESS** in red, instead of the app sitting there waiting for a
game it cannot see.

### Also

- Staff: with your token set, the finds you share are verified in your name
  as they go up. Settings has the switch.
- The installer puts only the program, this README and the licence on your
  PC.
- Thanks to everyone who sent in feedback on the last build — most of this
  release is your list.

---

## 1.10027

### Fixed — it now sees you on the surface wherever you are standing

EDSMT worked out where you were from a single flag the game sets, and two
real situations on a planet do not set it: **on foot**, and the first moments
**after you board the SRV**. In both, the system and the body still filled in
at the top of the window, so the app looked perfectly alive — while quietly
refusing to mark anything, because as far as it was concerned you had no
position at all.

It now takes your position from the coordinates the game writes, which are
there in every one of those cases. Landed, in the SRV, on foot, or gliding
in: **F10 marks a deposit wherever you are standing.**

Reported by **Raizo/Drakain [IHCF]** — thank you.

### Fixed — errors that were about nothing

Some replies from Inara and from the community server arrived on the status
line as `Expecting value: line 1 column 1 (char 0)`. That is a sentence about
a parser. It appeared under **Inara key**, so it read exactly like a rejected
key when there was nothing wrong with the key at all.

Every message now says what actually happened and whose end it is at — the
server is down, the server sent a web page, the server sent nothing, the key
was refused and here is what it said. Nothing that arrives from a server can
reach you as a parser error again.

### New — Settings → Test says what it can see

The test button used to report the journal folder and stop. It now reports
the whole picture in one line: the folder, whether `Status.json` is readable,
what the game says you are doing, which body you are on, and your position.

If something is not being detected, press it and paste the line. It is
written to be the answer to "it isn't picking me up".

### Also

- **Running from a USB stick?** Put an empty file called `portable.txt` next
  to `EDSMT.exe` and it keeps your finds in a `data` folder beside itself.
- Coordinates that are not numbers are refused rather than turned into a pin
  somewhere near the equator.

---

## 1.10026

### New — the overlay is five boxes

The in-game overlay is no longer one window you take or leave. It is five
independent boxes, each switched on or off on its own, in any combination.

| Box | What it shows |
|---|---|
| **COMPASS** | The tape across the top: which way to turn for every deposit, its range and its rig count. Anything behind you pins to the near edge with a turn arrow. |
| **SCOPE** | The patch from above. Deposits coloured by commodity and sized by rigs, the 2 km scanner ring drawn round your SRV, the drive order numbered on the dots. |
| **TARGETS** | The nearest finds in order, and a bar per commodity sized by what it is worth. |
| **STATUS** | Body, deposit count, rig total, what is next, the estimated value of the patch and how far driving the lot is. |
| **MINERAL DEPOSIT** | One card: a labelled readout of the deposit you are nearest, telemetry for the whole signal, and a signal radar with range rings and a contact per find. |

The scope **and** the tape at the same time is now two tick boxes.

### New — put them where you want them

Press **Unlock** in the title bar, or bind a key to it so you can do it
without leaving the game. Every box grows a bar you drag it by, a corner you
resize it by, and its own name. Press **LOCK** and they go back to being
scenery — clicks pass straight through to the game.

**Positions are stored as a share of the screen, not as pixels.** A box 80% of
the way across a 4K monitor is 80% of the way across a 1080p one, scaled to
match, so the layout follows you between a desk and a laptop. A box left on a
monitor you have since unplugged comes back onto one you still have. **Reset
box positions** in Settings undoes a bad drag.

### New — five themes

Radio Raxxla cockpit, Signal, Elite orange, Ice blue, Green phosphor. They
change the whole palette and apply while you watch, no restart.

**Draw a border** decides where the frame goes: round the cards only, round
everything, or nothing. The scope gets none by default and you can see the
ground through it.

### New — what a patch is worth

Rig count times what the commodity sells for, using live community prices
where we have them and the published table where we do not. On the scope, on
the STATUS box, and as a bar per commodity on TARGETS.

**BEST PATCH and BEST VALUE are bracketed separately.** One is where the most
rigs are; the other is where the most money is. On a single-commodity body
they are the same bracket. They part company exactly when it matters.

Anything nobody has priced yet is counted and said out loud — *"4.18M Cr, +3
unpriced"* — rather than quietly left out.

### New — the drive route

The order to drive them in, numbered on the dots, nearest-next from where you
are standing, with the total distance on the STATUS box. Worked-out deposits
come off the route and stay on the map: the route is what to drive, the map is
what is there.

### New — what a run was worth

EDSMT reads your cargo, the station market and your sales, and keeps a history
of what each run earned. The telemetry strip shows what is in the hold and
what it is worth at the last market you saw. **Earnings** opens the history —
when, where, what you sold, credits, and credits per hour.

Three things it deliberately gets right:

- Moving ore from the SRV to the ship does not count it twice.
- Starting the app halfway through a run does not invent a haul.
- It reports profit, not gross, so a hold of bought goods going over the same
  counter cannot report its purchase price as mining profit.

A run is written to disk as it happens, not when it ends. A crash costs the
closing flag and nothing else.

### New — coming from another tool

Settings → **Import another tool's CSV** reads a `surfaceminingmap.csv` in
either of the two layouts other surface-mining tools write. Both use the same
file name, so the header decides and you are never asked which it is.

It never imports the same file twice, never overwrites a find you already
have, takes a backup first, and refuses a file it does not recognise by naming
what it expected.

### New — Still there

A search that ranks by whether the patch is probably **still there** rather
than by how big it was. Where a patch is can be worked out; whether the last
commander through took the lot cannot.

### Improved — Find

- **Every filter now searches the whole database**, not the page you were
  already looking at. Tick "Verified only" and it asks the server, rather than
  sifting the last 500 rows.
- **The System / body box accepts a body.** Typing `Ega 1` used to come back
  empty.
- **Individual deposits returns 500 results**, not 50.
- **Copy buttons are the first column** on every table, plus lat/lon as one
  pasteable pair and Copy All for Discord.
- **Sortable columns** — click a header, click again to reverse.
- **Found by** — the commander who first mapped a site, on every table that
  lists one.

### Fixed

- **Best sell prices returned nothing, for everyone, every time.** It matched
  the station's system name exactly against the system you were standing in,
  and on a planet surface nobody has ever sold there. It is a proximity search
  now, with the distance in light years on every row, nearest first.
- **The commodity list was not re-ordered when the body scan arrived late.**
  The scan very often lands after you have touched down, and nothing re-ran
  the ordering when it did — so the list was almost never sorted for the world
  you were on.
- **The scanner filled the commodity box once per session and then stopped.**
  Every deposit after the first was filed under the first one's commodity, and
  shared that way, with nothing on screen saying so.
- **"Verified only" could never match anything**, because nothing in the app
  was able to mark a find verified.
- **MARK DEPOSIT could be pushed off the bottom** of a small window. It is
  pinned now.
- **Rail buttons were clipped.** The rail is wider and scrolls.
- **Hotkeys are rebindable by clicking and pressing the key**, the way the
  game does it, and it says so when a key is already taken by something else.
  F-keys that send media keys on some keyboards were binding nothing,
  silently.
- **Settings no longer resets your hotkeys** when you open it.
- **One far-off deposit no longer blanks the whole overlay.**
- **A distance reads the same on the overlay as on the map.**
- **The app tells you when the community server is unreachable** and why,
  instead of showing a bare error code.

### Notes

- The overlay **cannot** draw over the game in exclusive fullscreen. That is
  how DirectX works and no tool gets around it. Set Elite to borderless or
  windowed.
- The build is not code signed, so SmartScreen warns on first run. **More
  info → Run anyway.** See SECURITY.md.
- Beta testers are credited in Settings: **CMDR MJH430, CMDR StarTopaz,
  CMDR Flossy, CMDR Gamer Joe.**

---
