# EDSMT — patch notes

The version is in the app's title bar. Quote it on a bug report.

---

## 1.10030

### Fixed — Alt+1 to Alt+6 work in the game

Two faults, both found by the testers. After **Save** in Settings every key
went dead: the old key thread still held the keys when the new one asked for
them, so Windows refused them and they were never registered. Saving now
waits for the old thread to let go. And with **Num Lock on**, Settings read
every key pressed as **Alt+** that key — so nothing could be bound without
Alt, and Alt+F1 went to an NVIDIA screenshot. Settings now reads Alt properly
and takes **any key**, with or without Ctrl, Alt or Shift. The keys are also
read ten times a second on their own, and a fault anywhere else in the app can
no longer stop them being heard.

### New — EDSMT names keys other programs own

Pick a key NVIDIA, AMD, Windows, Steam, Discord or the game uses by default —
Alt+F1, Alt+F9, Alt+Z, Alt+R, Win+ keys, Shift+Tab, F10, F12 — and Settings
says who owns it the moment you press it. You can still keep it.

### Fixed — the compass and scope keep up with the Rhino

They redraw ten times a second from Status.json instead of every 0.7 s. Out
setting the border the scope keeps you in the picture out to 8 km, instead of
freezing at 1.5 km round the centre with you pinned to the rim — and pinned to
the rim or not, your chevron turns with the Rhino. The swept ground is no
longer a solid teal plate before there is a border; inside a border it is a
see-through mesh.

### Fixed — changing the overlay theme no longer moves the boxes

The boxes were measured while Windows had them hidden — whenever EDSMT's own
window was in front — and that was saved. They are now saved only when you
drop one. **The default layout is new**: compass across the top, scope and
guide down the left, targets on the right, status along the bottom. Layouts
from 1.10029 are put on it once, because that build could have scrambled them.

### Changed — Earnings is Rhino sessions only

A session starts when the Rhino leaves the ship and ends when it comes back
aboard. Every tonne it refines counts, every transfer to the ship counts, and
when you sell what it dug up the credits go against it. Trading, exploration
and asteroid mining no longer appear. **Multi-session** keeps one session
going across trips to a station and back; **End session** closes one by hand.
After every transfer the overlay flashes what is in the ship and the room
left, and STATUS shows the ship and Rhino holds for the whole session.

### Changed — logging a signal

No commodities needed: they come with the deposits. The signal number is
picked for you — the one the game has targeted, or the number in the box, or
the one you are standing in, or the next free number — so a new signal never
lands on top of one logged elsewhere. Pressing the key again at the same
signal keeps its centre. The message says to **hold the mineral scanner** out
to the location's edge line, press Alt+2 there, and keep holding it while you
map the area.

### Changed — the guide starts at the jump

Jump in and honk, click Where to land, map the body, pick a signal, land,
deploy the Rhino. **Deploy** only shows once you are out of glide and under
30 m; until then it says you are gliding, or how high you are.

### New — a big warning on high-gravity bodies

Arrive at a body at or over 2 g (Settings) and a warning triangle takes the
middle of the screen, once; the GUIDE and STATUS boxes carry a red bar for as
long as you are there. Where to land marks those bodies in red.

### New — the last rig warning at 4.8 km

The game warns at 4 km and destroys a rig at 5 km. At 4.8 km a big warning
triangle goes up in the middle of the screen and the warning sounds again.
Past 5 km the rig is gone: EDSMT drops it and clears the warnings. **Alt+5**
(ALL UP) clears every rig warning by hand.

### Changed — MARK on a spot already marked with another commodity

It asks: **Alt+6** renames the deposit already there — position, history and
tonnes kept — and **Alt+3** again adds the new commodity as a deposit of its
own. No more second find at 0 m.

### New — finds filed under the wrong signal number show at the signal

Anything within 5 km of the signal you are on, filed under another number, is
listed under it with a button that puts the number right.

### Changed

- The top bar: Find, My sites, Where to land and Earnings on the left;
  Overlay, Unlock and Settings on the right.
- A commodity picked from its list with the mouse closes the list.
- Beta testers: welcome **CMDR Rumphrend**.

---

## 1.10029

### Changed — the keys are Left Alt and the number row, in the order you work

Alt+1 logs the signal and sets the centre, Alt+2 the border, Alt+3 marks a
deposit, Alt+4 puts a rig down, Alt+5 brings the rigs up and Alt+6 updates the
deposit you are on — the number is the step. Keys you set yourself are kept;
keys still on the old defaults move, once, and EDSMT says so when it starts.
Every one can be changed in Settings → Hotkeys, and Reset puts it back.

### New — the Inara key and the token are hidden on screen

Both boxes in Settings show dots. **Show** beside each reveals it, and it goes
back to dots by itself after 20 seconds — safe to open Settings on stream.

### New — a guide over the game

A GUIDE box shows the step you are on, the key for it and what comes next:
map the body, pick the signal, land, launch the Rhino, log the centre, set the
border, mark a deposit, place the rigs, next deposit. It moves on by itself as
each step is done, and never asks for one you have already done.

### New — rigs say what they are mining

Each rig goes on the map, the scope and the compass tape in the colour of the
deposit it is on, with that deposit's name beside it, so you can see which
rig is on which deposit. Red when you are too far from it.

### New — the map opens on the signal you are working

The map and the scope open on the signal, sized to it, instead of on every
find on the body. Finds elsewhere on the body are counted, not drawn, until
you scroll out. Range rings are labelled once and nothing prints over
anything else — on the map or on the scope. When a patch is too crowded to
name every find, the nearest are named and the rest counted. The ground you
have swept is shaded only inside the border, on the map and the scope.

### New — the scope and the map are the signal you are AT

Drive into a signal you have logged and EDSMT picks it, once, and says so. A
signal still left in the box from before — 40 km back — no longer stretches
the scope to hold it: the scope shows the ground round the SRV and its header
says where that signal is. The scope never zooms past 15 km, and while you are
at the signal it holds the patch, its border, its rigs and you; further out
you are a chevron on the rim with the range. "N unlabelled" now counts finds
only, not ring distances.

### New — the deposit you are on, and the one you are going to

- **In the SRV, the deposit of yours you drive onto is picked** — once — so
  MINED OUT, UPDATE and Copy to share are one click. A deposit you pick by
  hand while standing there stays picked.
- **Pick a deposit on the map or in the list and the overlay guides you to
  it**: the scope and STATUS say **GO** instead of NEXT, and TARGETS lists it
  first. Arriving there ends it.
- **Tonnes are the deposit's own commodity.** By-products are listed beside
  them, no longer added in. **MINED OUT files what it gave**, and from then on
  its details say what it **holds** and about how much is **left** while you
  work it again. A worked-out deposit says how long ago — nothing assumes how
  fast it grows back. New tonnes show a few seconds after the laser stops.
- **Border before centre is kept**: press BORDER at the edge first and it
  becomes the border the moment you log the signal in the middle.
- **Where to land → Carrying**: only the bodies that carry one commodity.
- **My sites** opens on the body you are on.
- **Copies stay on the clipboard after EDSMT closes**, and a copy made while
  another program holds the clipboard waits for it instead of being lost.
- A pasted find a few metres from one of yours is recognised as yours.

### New — share a find as a line of text

**Copy to share** on a deposit puts it on the clipboard as one readable line —
system, body, signal, what it is, rigs, amount and where — for Discord or a
friend. Anyone running EDSMT adds it with **Settings → Your finds → Paste
shared finds**; chat around the lines is ignored and a find already there is
not added twice. A deposit's details also say where it is from the middle of
its signal: *from the signal centre: 1.24 km NE 045*.

### New — the signal you target is the signal picked

When the game names the number of the mining location you have targeted,
EDSMT picks the same signal. Pick another by hand and it stays picked until
you target something new.

### New — My sites

**My sites** in the title bar lists every signal you have logged and every
find you have marked, on every body and in every system: what is there, what
the signal offers that you have not found yet, rigs still to be had, tonnes
mined and when you were last there. Filter by system, body or commodity; copy
a system name and paste it into the galaxy map to go back.

### New — cargo already aboard, and where to sell it

Ore already in the ship or the SRV when EDSMT starts is counted in its own
column, *aboard at start* — never as mined. Logging in already on the ground
starts a run. The hold line names the SRV and the ship separately.

Earnings now shows **where to sell what is aboard**: for each commodity, the
best price within the distance you choose of the system you are in, with
that system's own price beside it. The main window's strip quotes the total.
**Best sell prices** in Find now asks from the system you are in too.

### New — tonnes mined per deposit

The game writes one journal line per tonne refined. EDSMT puts each one
against the marked deposit it came off, and the selected deposit shows what
it has given, by-products included.

### New — fourteen themes, for the app and the overlay

A **Basic settings** section at the top of Settings has the app theme, the
overlay theme and the switches most people want, and says that everything
can be changed. Fourteen palettes, every one held to readable contrast. The
overlay changes as soon as you Save; **Save and restart now** puts a new app
theme on straight away.

### New — rigs, sounds and the overlay only over the game

The rig warning defaults to 3,500 m (the game warns at about 4 km and a rig
drops off Contacts at about 2.9 km), a distance saves however you type it —
3950, 3,950, 3950 m or 3.95 km — and there is a profane warning sound if you
want it. The overlay boxes show only while the game is in front, and each key
says over the game what it did.

### Fixed

- Tables no longer show an empty sideways scrollbar with nothing to scroll.
- Restarting EDSMT in the middle of a session no longer counts a sale twice,
  or brings a banked run back as a second one.
- A game in another language no longer files Water as *Eau*, or leaves its
  markets unpriced. Commodities are named from the game's own symbols.
- A by-product refined in the SRV no longer changes the Commodity box, so the
  next deposit marked is not filed under it.
- The Find window loads individual deposits a page at a time, and has a
  **Last seen** column.
- Pick from a box with the mouse and Tab goes on to the next one.

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
