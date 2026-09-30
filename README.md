# EDSMT — Surface Mining Survey

Maps surface mining for the Rhino. It reads your journal, so you never type a
coordinate, a system name or a distance.

Original work. Not affiliated with Frontier Developments, and not derived
from any other tool. GPL-3.0.

Built for Elite Dangerous 4.4.1.1.

---

## Get it

**[radioraxxla.com/EDSMT](https://www.radioraxxla.com/EDSMT/) → `EDSMT-Setup.exe`**

Download it, run it, done. A normal installer wizard, a Start menu entry, a
desktop shortcut if you want one, and a proper entry in Add/Remove Programs.
**It installs for you only, so it never asks for admin.**

If you would rather not install anything, `EDSMT.exe` on the same page is the
same program as one portable file — save it anywhere and double-click it.

Windows SmartScreen will warn you the first time, because the build is not
code-signed — a certificate costs a few hundred a year and this is free.
**More info → Run anyway.**

Your finds live in `%LOCALAPPDATA%\RadioRaxxla\EDSMT`, not the program
folder, so updating never touches them.

**Updates fetch themselves.** When a new version is out, EDSMT downloads it
in the background — from radioraxxla.com only, and only if it matches the
checksum published beside it, byte for byte. The button in the title bar
then reads **INSTALL UPDATE**. Nothing is installed until you press it, so it
never closes on you mid-run; press it when you are done and EDSMT closes,
updates, and opens again with your finds and settings as they were. Settings
→ *This build* has the switch if you would rather it asked first.

---

## How it actually works

The keys are **Left Alt and the number row, in the order you work a
signal** — step 3 is Alt+3. The number row, not the number pad.

1. **Jump in and honk.** Fire the discovery scanner so every body shows.
2. **Click Where to land.** It ranks the system's bodies for the Rhino —
   pick one and fly to it. A body at or over 2 g gets a big warning.
3. **Map the body with the DSS.** It reports *Planetary Mining Locations*,
   numbered, scattered across the surface.
4. **Target the one you want, glide down and land by it.** When the game
   names the number, EDSMT picks the same signal for you.
5. **Deploy the Rhino** — out of glide and under 30 m. The guide waits for
   both before it says so.
6. **Drive to the middle and press Alt+1.** That logs the signal and sets
   the centre of the survey area. No commodities needed — they come with the
   deposits. The number is picked for you: the one the game has targeted,
   the one in the box if it is free, the one you are standing in, or the
   next free number, so a new signal never lands on an old one.
7. **Hold the mineral scanner down and keep holding it.** Drive out to the
   location's edge line and press **Alt+2** there — that is the border — then
   keep it held while you map the area. The scope keeps you in the picture
   the whole way out, and shades what you have swept inside the border.
8. **Drive to a deposit, fill in the boxes, press Alt+3.** Commodity, rigs,
   Amount, Density — pick with the mouse or type, and Tab moves on. All four
   are needed: a deposit is not marked with any of them blank (the scanner's
   density counts when the game names one), and the rigs, amount and density
   boxes clear themselves for the next one.
9. **Alt+4 to Alt+9 as each rig goes down** — rig 1 is Alt+4, rig 6 is
   Alt+9. Each rig is drawn on the scope and the compass in the colour of
   what it is mining, with its name beside it. Drive too far from one and the
   overlay says so. The first rig down starts your earnings session.
10. **The same number with AltGr picks that rig up** — AltGr+4 is rig 1 up.
    The last one up ends the session. **AltGr+0** is every rig up at once,
    and **AltGr+3** updates the deposit you are standing on.

| Key | Does |
|---|---|
| Alt+1 | Log the signal and set the centre |
| Alt+2 | Survey border here |
| Alt+3 | Mark the deposit |
| Alt+4 to Alt+9 | Rig 1 to rig 6 down |
| AltGr+4 to AltGr+9 | Rig 1 to rig 6 up |
| AltGr+3 | Update the deposit I am on |
| AltGr+0 | Every rig up |
| AltGr+2 | Rig planner: trace the deposit's edge (beta, off until switched on) |

**AltGr** is what UK and European keyboards call the right-hand Alt key.
Windows sees it as Ctrl+Alt, so on a keyboard without one — a US layout —
the same keys are **Ctrl+Alt+4** and so on, and EDSMT names them that way.
None of these keys is bound by any of the game's own control schemes.

Every one can be changed in **Settings → Hotkeys** — click it and press the
key you want, with or without Ctrl, Alt or Shift — and **Reset** puts it
back. Windows hands out a key like this without telling the two Alt keys
apart, so either Alt works. The game's own number-row keys (the panels, on
most layouts) are plain 1 to 4, without Alt; if your layout puts something on
Alt and a number, or another program of yours does, move one of the two.

**Keys other programs own.** Whoever registers a key first gets it, and
EDSMT never hears it. Settings names the owner the moment you press one of
these: NVIDIA's Alt+F1 (screenshot), Alt+F3, Alt+F9 (record), Alt+Shift+F10,
Alt+Z and Alt+R; AMD's Alt+R, Alt+Z and Ctrl+Shift keys; any Win+ key
(Windows and the Xbox Game Bar); Steam's Shift+Tab and F12; Discord's
Shift+\` and Ctrl+Shift+M/D; the game's F10 and Alt+F10. You can still keep
one if that program is off on your machine.

**The guide.** A GUIDE box over the game shows the step you are on, the key
for it, and what comes next, and moves on by itself as each step is done. It
is on for a first run and switches itself off once you have followed it all
the way through; Settings → Basic settings turns it back on.

**There is no centre to set and no bearing to work out.** The game hands over
your latitude and longitude, so a deposit records where it *is*. Distances
and directions are worked out live from wherever you happen to be standing —
which is the number you want while driving, and it means nothing has to be
pressed before a find can be recorded.

**Every box, every time.** A deposit goes on the map with its commodity,
rigs, amount and density, or not at all — finds were reaching the shared map
without the two things a commander deciding whether to fly there needs most.
Anything that changes later, **UPDATE** puts right.

**Amount and Density are different things.** Density is how rich the deposit
is — Low, Medium, High — and does not change. Amount is how much is left, and
walks down to Depleted as you work it. A site can be High density and
Depleted at the same time: rich, empty today, worth coming back to.

**UPDATE** sits beside MARK DEPOSIT. Standing on a deposit you have already
marked, it writes what the boxes say — the Amount going down as you work
it, a rig count you now know — onto that deposit instead of adding a second
copy. A blank box changes nothing, and the note is stamped with when. If
you share, the shared copy is updated too. MARK asks first if you already
have that commodity marked within 100 m — press MARK again within a few
seconds to add it as a separate deposit anyway. And if a **different**
commodity is already marked on the spot you are standing on — the box said
Monazite, it was Alexandrite — MARK asks too: **AltGr+3** renames the one
there, keeping its position, history and tonnes, and **Alt+3** again adds
the new one as a deposit of its own.

**Filed under the wrong number?** A find within 5 km of the signal you are
on, filed under another number, is listed under it with a **file under**
button that puts the number right.

**MINED OUT** sets a deposit to Depleted and stamps the note with the date
and time — `Mined 10/09/2026 01:05`. Press it again next month and it adds
another line, so the site keeps its history. It is not a delete: the deposit
stays on the map, because "empty as of the tenth" is worth more to the next
commander than nothing at all.

**The commodity box filters as you type** and is sorted roughly by worth.
Typing `bastna` finds Bastnäsite without the umlaut. The ordering is what the
surface-mining tables say a commodity averages, with a coarse band standing in
for anything outside them — a rough guide, not a quote. Real prices move with
every balance pass and with whatever community goal is running, so live
community prices override it entirely.

**Best patch** finds the tightest group with the most rigs and the most
different commodities in it, and points the map at it — the surface
equivalent of overlapping hotspots.

**Worked out** tells everyone a signal is stripped. It is not a delete: the
site drops out of results and climbs back as it regenerates.

**Got one wrong?** Every deposit in the selected signal is listed in the
left panel with an **edit** button beside it, and you can still double-click
it on the map. Signal number, commodity,
rigs, density and notes are all editable, and Delete is in the same window
behind a second press. Marking a deposit is one keypress with the game in
front of you, so the commodity or the signal number can easily be whatever
the boxes happened to say at that moment — that is what this is for.

**Signals can be corrected too.** Every row in the mining locations list has
an **edit** button: change the number, change what it offers, or remove it.
Renumbering a signal takes its deposits with it — otherwise they would be
stranded under a number that no longer exists, which is worse than the wrong
number you started with. Deleting a signal does *not* delete its deposits.
They were real places you drove to, so they stay on the map, and the window
tells you how many before you commit.

The position and the timestamp are shown but not editable. They came from
the game, and if a deposit really is in the wrong place, delete it and mark
it again. Editing is local: a correction to something already shared does
not rewrite the copy on the server.

The map works with Elite shut. It falls back to the last body you recorded
on and centres on the finds themselves, because tidying up is something you
do at the desk, not in the SRV.

**Drag the map** to move around it, scroll to zoom, right-click to snap back
to you in the middle.

**Back up your finds** from Settings — one dated zip with everything in it.
Restore puts it back and keeps whatever was already there alongside, renamed
rather than overwritten. Anyone restoring a backup is already having a bad
day; taking their last session away as the price would make it worse.

---

## Earnings, and where to sell

**Earnings** is your Rhino mining and nothing else. A session starts with
your **first rig down**, or the first tonne the Rhino refines if you do not
use the rig keys, or **Start session**. It ends when **every rig is back
up**, when the Rhino comes back aboard, or on **End session**. The Rhino
going out on its own is not a session — it goes out to look and to fetch
cargo too. Rigs going down again on the same body within ten minutes carry
the same session on. Every tonne it refines is counted, every transfer to
the ship is counted, and when you sell what it dug up the credits go against
the session that dug it — trading, hauling, exploration and asteroid mining
never appear. Restarting EDSMT in the middle of one does not count anything
twice.

**Delete** on a row takes a session out — a test run, one opened by mistake.
Press it twice on the same row; the file before is kept as
`sessions.csv.bak`.

**Pause** stops the clock — a break, the drive to a station — and credits
per hour leaves paused time out. A rig down, a tonne refined or the Rhino
going out starts it again by itself. **Multi-session** keeps one session
going across trips — fill the ship, fly to a station, sell, come back, go
again — until you untick it.

**More than one SRV on the ship.** A crewmate taking the ship's other Rhino
out is not your trip, and it coming back aboard does not end your session:
the journal says whose SRV each one is, and EDSMT follows yours.

After every transfer to the ship the overlay flashes what is in the ship and
the room left, and the STATUS box shows the ship's and the Rhino's holds for
the whole session.

The hold line names the **SRV** and the **ship** separately, and counts
only what a Rhino session dug up and has not sold — cargo you bought or
hauled is left out. It gives an estimate at the **galactic average**: the
game's own figure, read off any commodity market you open, or EDSMT's table
until you have (marked *). **Where to sell what is aboard** asks, for each
commodity mined, where it sells best within the distance you choose **of the
system you are in**, and shows three prices side by side: the galactic
average, the best in **this system**, and the **best within** the distance —
so you can see that the station two jumps away pays more before you fly
there. The strip in the main window quotes the total too.

**Tonnes mined per deposit.** The game writes one line in the journal for
every tonne refined. EDSMT puts each one against the marked deposit it came
off — the one of the same commodity first, then the nearest — and the
selected deposit shows what it has given, by-products and all. Once you have
worked a deposit out it says what it holds; before that, **est. holds** and
**est. left** come from the deposits you have worked out with the same rigs
and density, and say how many they rest on.

## Themes

Fourteen, for the app and for the overlay separately, all on a dark ground:
the Radio Raxxla cockpit, Elite orange, Signal teal, Ice blue, Green
phosphor, Amber terminal, Crimson alert, Deep space violet, Imperial gold,
Fleet blue, Xeno green, Nebula pink, High contrast, and a colour-safe blue
and orange. Every one is held to readable contrast. The overlay changes the
moment you Save; the app wears a new theme from the next start, and **Save
and restart now** does that straight away.

---

## The map

A top-down plan view with **you in the middle**, north up. Deposits are pins
with their range in metres and their commodity. Anything beyond the edge gets
an arrowhead pointing its way, with the distance. Scroll to zoom. Click a pin
and it tells you how far, which way, and whether to go left or right from
your current heading.

No plotting library aboard, which is why it opens in about a second.

**It is the signal you are at.** Drive into a signal you have logged and
EDSMT picks it for you, once — a number you then pick by hand stays picked
until you drive into another. The map and the scope are sized to that signal:
its finds, its border and its rigs. If the Signal box still names a signal
somewhere else on the body, the views show the ground round the SRV instead,
and say where that signal is.

**Other commanders' finds are on it too.** Arrive on a body and EDSMT asks
the community map for everything already shared there. Those finds are drawn
as diamonds — on the map, the scope and the mineral deposit card — so you
can tell at a glance what is yours and what somebody else logged. Click one
and it says who shared it and when. A shared find sitting on top of one of
your own is shown once, as yours. Settings has the switch.

---

## Surveying an area

So you know you have covered the whole of a mining area, not just the bits
you happened to drive through.

1. Drive to the middle of the area and press **Alt+1** — logging the signal
   sets the centre.
2. Hold the mineral scanner down and keep holding it. Drive out to the
   location's edge line and press **Alt+2** (BORDER) there. That sets the
   radius. Pressed at the edge first, before the centre, the point is kept
   and becomes the border as soon as the centre is set. The scope keeps you
   in the picture out to 8 km, and the guide says how far from the centre
   you are.
3. Drive the circles drawn on the map. Everywhere your scanner has swept is
   shaded; what is left is not.

The Survey area panel and the STATUS box say how much is swept — **AREA
SWEPT 83%**. It only reads 100% when all of it is, never rounded up. Each
circle is spaced so that the scanner's 2 km sweeps overlap a little, which is
what makes "drive the circles" leave no gaps. The map is kept per body and
saved as you go, so you can come back tomorrow and carry on where you
stopped. **CLEAR** starts the area again, and **MOVE CENTRE HERE** moves the
centre without logging the signal again.

---

## Rigs down

Press the rig's own key as you drop it — **Alt+4** for rig 1 up to **Alt+9**
for rig 6 — and the same number with **AltGr** as you pick it up. **RIG
DOWN** in the window, or a spare key you bind in Settings, puts down the
next free one instead. A rig already down somewhere else under that number
moves to where you are, and a double press on the same spot is not counted
twice. Each rig is a numbered square on the map, the scope and
the compass tape, in the colour of the deposit it is on, with that deposit's
commodity beside it. The STATUS box shows how many are down and how far the
farthest one is.

Drive further than your limit from any rig (Settings → Rigs, 3,500 m unless
you change it — the game warns at 4 km and destroys a rig at 5 km) and every
overlay box you have open shows **TOO FAR FROM RIG**
and its number in red, with a warning sound if you want one — or the profane one, if you tick it. It
sounds once per trip out, not every second you are over the line, and is
ready again once you are back well inside it. Picking each one up forgets
it, **AltGr+0** (every rig up) forgets the lot, and leaving the body does too.
0 turns the warning off.

**The last warning.** At 4.8 km from a rig a big warning triangle takes the
middle of the screen and the warning sounds again — whatever the first
warning is set to, because 200 m later the rig is gone. Past 5 km in the
Rhino it is gone: EDSMT drops it, says so, and clears every warning for it.
**AltGr+0** clears the lot by hand at any time.

### The rig planner (beta)

Off until you switch it on in **Settings → Rigs**. Drive to the deposit's
edge, press **AltGr+2**, and drive round the edge back to where you pressed
it: the loop closes by itself, or press the key again to close it where you
are. EDSMT works out where up to six rigs fit inside what you drove, each at
least the spacing apart — **78 m** by default, the community's working
figure, which you can change — and puts a numbered pin on the scope for each
one, in driving order. The scope closes in on the pins while you are near
them, STATUS says which pin is next and how far, the compass tape points at
it, and each pin goes green as a rig goes down within half the spacing of
it.

### The wing link (beta)

Mining one body with friends, or crew off one ship with more than one Rhino?
Switch on **Settings → Wing link**, and everyone types the same
six-character code (**Make a new code** makes one up to read out). Each of
you sees the others' Rhinos and rigs on the scope in a colour of their own,
and dropping a rig closer than the rig spacing to a wingmate's says so. Your
commander name goes with it only if name sharing is on. The server keeps
nothing: it forgets you two minutes after your last beat.

---

## My sites

**My sites** in the title bar lists everywhere you have logged a signal or
marked a find — every body, every system, not just the one you are on.

| Column | What it says |
|---|---|
| **What is there** | your finds still there, what the signal offers that you have not found yet, and what the game says is worked out |
| **Finds** | how many you marked, and how many of those are depleted |
| **Rigs** | the rigs still to be had, at deposits not marked Depleted |
| **Mined** | the tonnes refined there |
| **Last there** | when you last logged or marked something there |

Type in **Filter** to narrow it by system, body or commodity. **system** copies
the system name — paste it into the galaxy map to plot a route back. Where you
are now is in green.

### The deposit you are on, and the one you are going to

In the SRV, drive onto a deposit you marked and EDSMT picks it — **MINED OUT**,
**UPDATE** and **Copy to share** then act on it with one click. Pick a deposit
on the map or in the list and the overlay **guides you to it**: the scope and
STATUS say **GO** with the turn and the range, and TARGETS lists it first,
until you arrive.

A deposit's details say what it has given: **its own commodity's tonnes**,
with by-products beside them (not added in). Press **MINED OUT** when it is
empty and that figure is filed as what it **holds**; work it again after it
has grown back and the details say about how much is **left**. A worked-out
deposit says how long ago it was worked out. How fast deposits grow back is
not known, so EDSMT does not guess.

### Sharing one find

Click a deposit and press **Copy to share**. It goes on the clipboard as one
line anyone can read:

```
EDSMT find | HR 7280 | HR 7280 A 3 | signal 5 | Haematite | rigs 4 | amount High | density ? | 10.00100, 20.00100
```

Paste it in Discord. Anyone running EDSMT copies it, pastes it into the box in
**Settings → Your finds** and presses **Import** (or Enter) — chat around it is
ignored, and a find they already have is not added twice. EDSMT never reads
the clipboard by itself: only what you paste into that box. A deposit's details also say where it is from
the middle of its signal, so a friend can drive straight to it.

---

## Where to land

The **Where to land** button lists every landable body in the system you are
in, best first, and fills itself in as you scan — honk, resolve bodies in the
FSS, map one with the DSS, and it keeps up without a click.

| Column | Where it comes from |
|---|---|
| **Est. value** | the known sites still intact at what they carry, plus each location nobody has shared yet at what a site on that kind of ground usually carries |
| **Why** | one line: known sites intact, locations nobody has shared, not mapped yet, or nothing found |
| **Locations** | the DSS count. *not mapped* until you map it — zero is only zero once the DSS says so |
| **Best bets** | what sites on this kind of ground have carried, from everyone's shared finds once there are enough of them, from the commodity tables until then — the line under it says which |
| **Known sites** | what has already been shared on that body, intact and worked out |
| **Yours** | your own locations and finds there |
| **Swept** | how much of your survey area there you have covered |
| **Ground** | body class, volcanism and gravity |

The value is an estimate and says so. Click a heading to sort by it;
**Copy all** puts the list on the clipboard for Discord. **Carrying** narrows
it to the bodies that carry one commodity — what their ground is known or
expected to carry, and what has been found on them.

---

## The overlay

Turn it on with the **Overlay** button, or in Settings. It is **six separate
boxes**, each its own window, each switched on or off on its own — any
combination at once. They show only while the game is in front, and each key
you press says what it did over the game for a few seconds — RIG 2 DOWN
RHODPLUMSITE, SIGNAL 5 LOGGED.

| Box | What it shows |
|---|---|
| **COMPASS** | the tape across the top: which way to turn for every deposit, its range and its rig count. Anything behind you pins to the near edge with a turn arrow rather than vanishing |
| **SCOPE** | the patch from above — deposits coloured by commodity, sized by rigs, the 2 km scanner ring round your SRV, the drive order numbered on the dots |
| **TARGETS** | the nearest finds in order, and a bar per commodity sized by what it is worth |
| **STATUS** | body, deposit count, rig total, what is next, the estimated value of the patch and how far driving the lot is — and during a Rhino session, the ship's hold against its capacity and the Rhino's |
| **MINERAL DEPOSIT** | one card: a labelled readout of the deposit you are nearest, telemetry for the whole signal, and a signal radar with range rings and a contact per find |
| **GUIDE** | the step you are on, the key for it and what comes next — moves on by itself as each step is done |

**Text size, box by box.** Settings → In-game overlay has a text size for
each box, 80% to 200%, on its own — bigger words without a bigger scope.

The compass and the scope redraw ten times a second, so they turn with the
Rhino. On a body at or over the gravity set in Settings (2 g to start with) a
warning triangle takes the middle of the screen when you arrive, once, and
GUIDE and STATUS carry a red **HIGH GRAVITY** bar for as long as you are
there. At 4.8 km from a rig the same triangle comes up for the rig.

**The default layout** is the compass across the top, the scope and the guide
down the left edge, the targets on the right and the status along the bottom
— all clear of the middle of the screen.

Every word on the scope is placed where it touches nothing else. When a
patch is too crowded to name every find, the nearest are named and the rest
are counted — scroll the map in the main window for the full picture.

### Putting them where you want them

Press **Unlock** in the title bar — or bind a key to it in Settings, so you can
do it without leaving the game. While unlocked, every box grows a bar you drag
it by, a corner you resize it by, and its own name so you know which is which.
Press **LOCK** and they go back to being scenery: clicks pass straight through
to the game.

**Positions are stored as a share of the screen, not as pixels.** A box you
put 80% of the way across a 4K monitor is 80% of the way across a 1080p one,
scaled to match — so the layout follows you between a desk and a laptop. A box
left on a monitor you have since unplugged comes back onto one you still have,
with enough of it showing to grab. If a drag goes wrong, **Reset box
positions** in Settings puts everything back.

### Themes and borders

Fourteen themes (see **Themes** above). They change the whole palette,
background included, and apply to the overlay the moment you Save.
You can still type any `#rrggbb` to override the instrument colour on top of a
theme.

**Draw a border** decides where the frame goes: round the cards only (the
default), round everything, or nothing at all. The scope gets none by default
and its dish is not filled in — it is something you look through at the
ground, and a bright box round it sits in your cockpit whether you are looking
at it or not.

It **cannot** draw over the game in exclusive fullscreen. That is how DirectX
works, and no tool gets around it. Set Elite to **borderless** or windowed and
it appears.

---

## What a patch is worth

Six rigs of a cheap metal and six rigs of a gemstone draw the same picture
and are not the same trip. EDSMT prices it: rig count times what the commodity sells for, using the
community's live prices where the server has them and the published table
where it does not. The estimate is on the SCOPE, on the STATUS box, and as a
bar per commodity on TARGETS.

**BEST PATCH and BEST VALUE are bracketed separately.** One is where the most
rigs are; the other is where the most money is. On a body with one commodity
they are the same bracket. They part company exactly when it matters.

Anything nobody has priced yet is counted and said out loud — *"4.18M Cr, +3
unpriced"* — rather than quietly left out of the total.

### The drive route

The order to drive them in is numbered on the dots, nearest-next from where
you are standing, with the total distance on the STATUS box. It is not the
shortest possible route — nobody needs the travelling salesman solved to two
metres in an SRV — but it is the order you would drive anyway, and having it
on the map means not stopping at every dot to work out which is closest.

Worked-out deposits come off the route and stay on the map. The route is what
to drive; the map is what is there.

---

## What a session was worth

EDSMT reads the journal's `LaunchSRV`, `MiningRefined`, `CargoTransfer`,
`DockSRV` and `MarketSell`, and your own rig keys, and keeps a history of each Rhino session in
`sessions.csv` next to your finds — so it is already inside the backup.

While you are playing, the telemetry strip shows the session in progress —
how long, how many tonnes mined, how many moved to the ship — and what the
hold is worth at the last market you saw. The **Earnings** button opens the
history: when, where, what was mined, what went to the ship, what sold,
credits, and credits per hour of mining.

Four things it deliberately gets right, because they are the four ways of
getting it wrong:

- **Only the Rhino counts.** A tonne refined by the ship mining asteroids is
  the same journal event; it is not booked, because the Rhino was aboard.
- **Moving ore to the ship does not mine it twice.** Transfers are counted in
  their own column.
- **A sale is put against the session that dug it up,** newest first, and
  never more than it dug. A sale of anything no session dug up — trade
  goods, exploration data — is not booked at all.
- **The drive to the station is not mining time.** A finished session keeps
  the time it was mined in, so credits per hour means credits per hour of
  mining. In Multi-session the whole haul is the session, by design — and
  Pause takes the drive back out.

A session's row on disk is complete the whole way through, not written when
it ends. A crash, a kill or a power cut costs the closing flag and nothing
else. Runs written by builds before 1.10030 stay in the file but are not
shown.

---

## Coming from another tool

Settings → **Import another tool's CSV** reads a `surfaceminingmap.csv` in
either of the two layouts other surface-mining tools write. Both use the same
file name, so the header row decides which it is — you are never asked.

It never imports the same file twice — keyed on the contents, so a renamed
copy is caught too — never overwrites a find you already have, takes a backup
before the first row goes in, and refuses a file it does not recognise by
naming exactly what it expected to see.

---

## Commodities

The thirteen from the 4.4.1.0 notes, plus the ones that actually come out of
the ground — copper, haematite, lithium, palladium, uranium and the rest.

**The list is suggestions, not a rulebook.** Anything the game names is
accepted and remembered, because the alternative is refusing to record a real
find on the grounds that it was not in a list written by somebody who had not
seen it yet.

---

## Sharing

EDSMT asks you once, the first time it starts, and takes no for an answer.
Nothing leaves your machine unless you say yes, and Settings has the switch
either way.

Please say yes. One commander cannot cover a galaxy; a few thousand can.

With it on, what you map is shared and everyone else's turns up under
**Find**, which opens once the server has taken one deposit of your own —
reading the shared map starts with adding to it. Find is filtered by commodity, minimum rigs, how many different
commodities sit in one patch, and how recently anybody confirmed it.

Age is part of the ranking, not a column you are left to interpret. Ring
hotspots are permanent; surface deposits are not. Frontier were explicit that
they "regenerate at a very slow rate", so a site nobody has touched in three
months sinks below a smaller one confirmed last week.

### Best sell prices

**Find → Sell** answers *where does this actually sell*, nearest first, with
the distance in light years on every row. It combines live market data with
what other commanders' games have read at markets, and says which is which.
A station in a system nobody has placed reads "-" rather than sorting to the
top as the closest thing in the galaxy.

With price sharing on, your own game fills the gap: every time you open a
commodity market EDSMT reads the surface-mining prices out of it and adds
them to the community's.

---

## Where your finds live

Everything EDSMT records is in one folder, and nothing else touches it:

`%LOCALAPPDATA%\RadioRaxxla\EDSMT`

    deposits.csv               your finds
    locations.csv              the mining location signals you have logged
    sessions.csv               what each Rhino session mined and earned
    imported.json              which files you have already imported
    settings.json              written by the Settings window
    settings.json.bak          the last good copy, kept automatically
    coverage\                  the survey areas you have swept, per body
    updates\                   a downloaded update, until it is installed
    journal-mining-events.log  new game events as they are discovered
    crash.log                  only if something goes wrong

**Settings are written safely.** Every save goes to a temporary file first
and replaces the old one only once it is complete, and the last good copy is
kept as `settings.json.bak`. A settings file that cannot be read is set
aside and the backup used — never overwritten with defaults — and EDSMT
tells you on the status line when that has happened.

Plain CSV on purpose — open them in a spreadsheet, back them up, or take them
with you. **Updating EDSMT never touches this folder.** Settings has
**Back up now**, **Restore from a backup** and **Open my data folder**.

**Running it off a USB stick?** Put an empty file called `portable.txt` next
to `EDSMT.exe` and it keeps everything in a `data` folder beside itself
instead, so the stick carries your finds with it. Copy your existing files
across first if you have any — it does not move them for you.

---

## Something wrong?

**The version is in the title bar. Quote it.** It is the first thing anyone
will ask.

If the app does something unexpected it writes `crash.log` next to your finds
in `%LOCALAPPDATA%\RadioRaxxla\EDSMT`. Attach it.

| What you see | What it usually is |
|---|---|
| The overlay does not appear over the game | Elite is in exclusive fullscreen. Set it to borderless or windowed — that is DirectX, not this app |
| An overlay box is off-screen | Settings → **Reset box positions** |
| Find returns nothing at all | Check the Community URL in Settings, and that sharing is switched on |
| Find says the server is unreachable | It will say why. Usually the server is down or the network is blocking it |
| System and body do not fill in | The app needs the game's journal folder. Settings → Journal folder |
| **NO ACCESS** in red at the top | Windows is refusing to let EDSMT read the journal folder — usually a hidden or protected Saved Games folder, or security software. Allow EDSMT, or point Settings → Journal folder at a copy it can read |
| "EDSMT is already running" | Only one copy runs at a time, so two cannot fight over your finds. Look on the taskbar |
| An update did not download | It says why on the status line. A download that does not match its checksum is thrown away and tried again later; Settings → **Check for updates** tries now |
| SmartScreen blocks the installer | Expected — the build is not code signed. **More info → Run anyway.** See SECURITY.md |

Bug reports and ideas: open an issue on the repository, or post in the Radio
Raxxla Discord.

EDSMT is free and GPL-3.0. See LICENSE.

