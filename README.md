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

The game gives you three levels, and EDSMT follows them:

1. **Run the DSS on a body.** It reports *Planetary Mining Location Signals*,
   numbered, scattered across the surface.
2. **Drive into one.** The game lists what might be inside — for example
   copper, haematite, lithium, palladium, uranium, and sapphire already
   marked depleted. Press **F9** and EDSMT records the signal and its offer.
3. **Drive around pinging with the mineral scanner.** Each hit is a
   *Planetary Mining Deposit*. Press **F10** where it pinged.

That is the whole workflow. Two keys, and one of them is optional.

Everything else — **UPDATE**, the survey area's **CENTRE** and **BORDER**,
**RIG DOWN**, and locking the overlay — has a button, and can have a key of
its own in **Settings → Hotkeys** so you never leave the game to press it.

**There is no centre to set and no bearing to work out.** The game hands over
your latitude and longitude, so a deposit records where it *is*. Distances
and directions are worked out live from wherever you happen to be standing —
which is the number you want while driving, and it means nothing has to be
pressed before a find can be recorded.

**Rigs can be left blank.** You do not know how many a deposit takes until
you get there. Mark it, come back, and set the count when you know.

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
seconds to add it as a separate deposit anyway. Bind a key to UPDATE in
Settings if you want it in-game.

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

## The map

A top-down plan view with **you in the middle**, north up. Deposits are pins
with their range in metres and their commodity. Anything beyond the edge gets
an arrowhead pointing its way, with the distance. Scroll to zoom. Click a pin
and it tells you how far, which way, and whether to go left or right from
your current heading.

No plotting library aboard, which is why it opens in about a second.

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

1. Drive to the middle of the area and press **CENTRE**.
2. Drive to its edge and press **BORDER**. That sets the radius.
3. Drive the circles drawn on the map. Everywhere your scanner has swept is
   shaded; what is left is not.

The Survey area panel and the STATUS box say how much is swept — **AREA
SWEPT 83%**. It only reads 100% when all of it is, never rounded up. Each
circle is spaced so that the scanner's 2 km sweeps overlap a little, which is
what makes "drive the circles" leave no gaps. The map is kept per body and
saved as you go, so you can come back tomorrow and carry on where you
stopped. **CLEAR** starts the area again. Both CENTRE and BORDER can be bound
to keys in Settings.

---

## Rigs down

Press **RIG DOWN** — or bind it to a key in Settings — as you drop each rig.
One key for all of them: they are numbered 1 to 6 for you, and a double
press on the same spot is not counted twice. Each rig is a numbered square
on the map and on the scope, and the STATUS box shows how many are down and
how far the farthest one is.

Drive further than your limit from any rig (Settings → Rigs, 1,000 m unless
you change it) and every overlay box you have open shows **TOO FAR FROM RIG**
and its number in red, with a Windows warning sound if you want one. It
sounds once per trip out, not every second you are over the line, and is
ready again once you are back well inside it. **ALL UP** forgets them when
you have collected them; leaving the body does too. 0 turns the warning off.

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
**Copy all** puts the list on the clipboard for Discord.

---

## The overlay

Turn it on with the **Overlay** button, or in Settings. It is **five separate
boxes**, each its own window, each switched on or off on its own — any
combination at once:

| Box | What it shows |
|---|---|
| **COMPASS** | the tape across the top: which way to turn for every deposit, its range and its rig count. Anything behind you pins to the near edge with a turn arrow rather than vanishing |
| **SCOPE** | the patch from above — deposits coloured by commodity, sized by rigs, the 2 km scanner ring round your SRV, the drive order numbered on the dots |
| **TARGETS** | the nearest finds in order, and a bar per commodity sized by what it is worth |
| **STATUS** | body, deposit count, rig total, what is next, the estimated value of the patch and how far driving the lot is |
| **MINERAL DEPOSIT** | one card: a labelled readout of the deposit you are nearest, telemetry for the whole signal, and a signal radar with range rings and a contact per find |

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

Five themes — **Radio Raxxla cockpit**, **Signal**, **Elite orange**, **Ice
blue**, **Green phosphor**. They change the whole palette, background
included, and apply on the next redraw rather than the next launch.
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

## What a run was worth

EDSMT reads `Cargo.json`, `Market.json` and your `MarketSell` events and keeps
a history of what each run earned, in `sessions.csv` next to your finds — so
it is already inside the backup.

While you are playing, the telemetry strip shows what is in the hold and what
it is worth at the last market you saw. The **Earnings** button opens the
history: when, where, what you sold, credits, and credits per hour.

Three things it deliberately gets right, because they are the three ways of
getting it wrong:

- **Moving ore from the SRV to the ship does not mine it twice.** `Cargo.json`
  describes one vessel at a time, so the rise on the receiving side is
  credited against the transfer that caused it.
- **Starting the app halfway through a run does not invent a haul.** The first
  sight of a hold is a baseline, not forty tonnes of mining.
- **It reports profit, not gross.** A hold of bought goods going over the same
  counter cannot report its purchase price as mining profit.

A run's row on disk is complete the whole way through, not written when it
ends. A crash, a kill or a power cut costs the closing flag and nothing else —
the credits, the hours and the rate are already right.

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
**Find** — filtered by commodity, minimum rigs, how many different
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
    sessions.csv               what each mining run earned
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

