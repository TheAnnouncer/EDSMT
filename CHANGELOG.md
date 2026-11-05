# EDSMT — patch notes

The version is in the app's title bar. Quote it on a bug report.

---

## 1.10040

### New — a welcome window

- **A welcome window** on the first start of each new version: **CHECK THE
  SETTINGS** with a button straight to them, what is new in this version,
  **Join the Discord**, radioraxxla.com and **Sign in to the site** (a
  member page for any commander, in the squadron or not), a picture of how
  it works, the community map, the useful links (user guide, report a bug,
  changelog, the tour) and a **Donate with PayPal** button to support Radio
  Raxxla. *Don't show this again* keeps it shut until the next version;
  **Help** on the top bar and **Welcome again** in Settings → About open it
  any time. It replaces the first-run notice and says the same thing about
  the community map.
### New — the wing link: linked from your in-game wing, one shared survey, pins split

- **Linked with your wing in the game, no code to type.** Settings → Rigs →
  Wing link, **Link with my in-game wing by itself** (on to begin with):
  in a wing in the game, you are linked with each wingmate who runs EDSMT
  and has you in their wing too — never with anyone who does not. Leaving
  the wing in the game ends it at once. A typed wing code still works as
  before, beside it.
- **One shared survey.** Over the wing link go the ground your scanner has
  swept on the body, the finds you have marked there and your rig plan's
  pins. The map and the scope show each wingmate's Rhino, rigs, swept
  ground and finds in a colour of their own, a find a wingmate marks is
  said as it comes in, with how far and which way, and the swept figure and
  the gaps count the ground the wing has swept with yours. Nothing is
  stored: you drop out two minutes after your last update.
- **Rig plan pins split between the wing.** On a deposit with a rig plan,
  the pins are divided between the wingmates working it, in turn by name:
  yours are as always and you are guided to your own, theirs are dashed, in
  their colour, with their initial. With no plan of your own the wing's is
  followed — the one with the most pins. **Split the rig plan's pins between
  the wing** turns it off.

### New — the session on a stream

- **An OBS browser source**, Settings → Overlay → Streaming: switch on
  *Serve an OBS browser source on this PC* and EDSMT serves your Rhino
  session as a page for an OBS Browser Source — body and system, tonnes by
  commodity, Cr/hr, merits, rigs down, the nearest deposit with its distance
  and bearing, and the session clock, in the app theme's colours on a clear
  background. It is served on this PC only (127.0.0.1, port 8765 unless you
  pick another) and loads nothing from anywhere else. **Copy overlay
  address** puts the address on the clipboard to paste into OBS. Off until
  you turn it on.
- **A viewer card** on the same page server, for a corner of the stream or a
  Twitch panel picture: your CMDR name, what you are mining and where, the
  session's tonnes, Cr/hr and your last find. **Copy viewer card address**
  copies it. No Twitch account or key is needed.
- **Streamer mode covers both**: while it hides the system and body names on
  screen, the overlay page and the viewer card read "a system N Ly from Sol"
  and "a body" too. Neither ever shows a position on the body or anything
  about you beyond your CMDR name.
- **A session card**: **Session card** on Earnings → This session, or
  **card** on any row of Sessions, makes one picture of the session — CMDR,
  body, system, date, tonnes by commodity, credits, Cr/hr, merits and time
  mined, with the session's map beside them — in the pictures folder. The
  OBS page shows the latest as /card.png.
- **The card on Discord**: each of your webhooks has a new **Session card**
  switch, off to start with, that sends the card with the session summary.
  Webhooks you already have keep posting what they posted.
- **The Streamer layout reads on a stream**: applying it now takes its boxes'
  text to at least 130%, so nothing on a 1080p capture is smaller than
  10 pt. A size you set bigger is kept.
- **Text shadow for streaming**, Settings → Overlay → Streaming: a dark
  outline behind every word on the overlay boxes, so they read over bright
  ground on a stream. Off to start with.
- **Settings → Sharing → Discord**: each webhook's Test and Remove buttons
  are on a line of their own under its switches.

### New — Voice Mode, spoken directions, the proximity sonar and a VoiceAttack profile

- **Voice Mode.** Settings → Basics → Voice, **Voice Mode** (off to begin
  with): EDSMT says what it just did — signal logged, border set, deposit
  recorded or not, rig three down, all rigs recovered, the rig range
  warning, update ready, backup complete, the session starting, pausing,
  resuming and ending, a rig plan traced, ready and on the pin, half the
  survey area swept and all of it, a high-gravity world, the wing link up,
  a wingmate joining, leaving or crowding your rig, a chat command not
  understood. The words are the **Basic voice line pack**, in
  one of three voices — **Ship computer**, **Flight controller** or **Radio
  Raxxla on-air** — with a **Speaking rate** and a **Test voice** button.
  **Ship computer comes recorded** — every line, made for EDSMT and shipped
  with it. The other two voices are read by Windows' own speech, through
  one process for the whole run that closes with EDSMT, until their
  recordings follow. A recording (`voice\<voice>\<line>.wav` beside
  EDSMT or in the data folder) is always played in place of the spoken
  line. Windows only.
- **Spoken directions, for a headset.** **Spoken directions** says how far
  and which way, on a clock face — "Platinum, 340 metres, two o'clock" — to
  the rig plan's next pin, the guided survey's waypoint, the deposit the
  scope points at, or the nearest rig: at once when it changes, every 10
  seconds while you drive (5 to 60 in Settings), never more than one line
  every 3 seconds. Windows only.
- **Proximity sonar.** **Proximity sonar**: in the Rhino, a short tone that
  repeats faster and higher as the deposit the scope points at gets nearer —
  every 2 seconds at 1,500 m, five a second inside 25 m, nothing past 2 km.
  Tones only, no words. Windows only.
- **A VoiceAttack profile.** Settings → Keys, **Make a VoiceAttack
  profile** writes *Radio Raxxla EDSMT.vap* into the data folder and says
  where: "mark signal", "set border", "mark deposit", "rig one down" to
  "rig six down", "rigs up", "update deposit", "next waypoint", "overlay"
  and "lock overlay", each pressing the key bound to it on the Keys page.
  In VoiceAttack, Import Profile and pick it. See docs/VOICEATTACK.md.

### New — faster tables, a journal read off the window's thread, the journal's own checks

- **The big tables are a tree view.** Find, Sessions (and System prices), My sites (and its bin) and Where to land hold every row at once and draw only the rows on screen: 2,000 rows draw in 0.06 s, where the old label grid took 3.1 s for 300. No more "Show more". Headings sort, rows are coloured by their cells (green good, amber caution), a short cell such as Why shows its whole sentence when the mouse rests on it, and Copy takes it whole. Click a row to pick it - its buttons are on the line under the table; Ctrl or Shift picks several, Ctrl+C copies them, a double-click does the first thing on the line and a right-click lists them all. The small fixed tables (Where to sell, Powerplay, the leaderboard) are as they were.
- **The first read of a long journal no longer stops the window.** A journal of 8 MB or more is read from the top 4 MB at a time on a thread of its own, with progress on the status line; the window is never still for more than a few hundredths of a second meanwhile. A 500,000-line journal reads in about 2.5 s instead of 4 s, with 26 MB of memory instead of 304 MB.
- **Faster reading all round.** Commodity names are remembered rather than tidied afresh each time, and journal lines nothing reads (chat, music, signals) are skipped unparsed. The older journals are read a chunk at a time instead of whole. Loading and listing your own sites is about twice as fast. Before and after figures are in docs/PERFORMANCE.md.
- **A session's tonnes are what crossed to the ship.** The Sessions table's t/hr is from the tonnes moved across to the ship; the tonnes refined stay the live count while the Rhino is out.
- **The ship's hold checks the transfers.** Once the Rhino is back aboard, To ship says "hold agrees" when the ship's own hold rose by exactly what was moved across.
- **Cargo thrown out is counted.** Ore of the session's own thrown out while it is open shows under Mined as tonnes thrown out.
- **The game's own count at each login.** The line under the Sessions table puts the game's mining figures between your last two logins beside the sessions EDSMT has for that time.
- **What is in the Rhino now.** This session says what the Rhino holds, from the count the game writes with every tonne.
- **The price after your sale.** Sold at gives how the price had moved by your next read of that market, with the price before the sale and the next one in the cell's note and in Copy.
- **Trace mode, for support.** A setting, off by default: during a Rhino session, a line for each change the game writes to Status.json and Cargo.json - the time, the flags and the cargo counts, nothing else - goes into the support bundle.

### New — streamer mode, several Discord channels, a backdrop for bright planets, the main window

- **Streamer mode**, Settings → Sharing: system and body names on the
  overlay, the map's title, the status line and the readouts read "a system
  N Ly from Sol" and "a body" until you have been in a system for the delay
  you pick (0 to 30 minutes), and your own Discord posts wait the same
  delay. A STREAMER badge shows while it is on, and *Bigger text* takes the
  overlay's text two sizes up. Finds still reach the community map at once.
- **Several Discord channels of your own** — up to five, each with a name
  and its own switches for finds, session summaries and the session map,
  with Test and Remove on each. The one webhook you had becomes the first,
  named *My Discord*. Every find also appears on the Radio Raxxla Discord
  through the community map, with nothing to set up.
- **A dark backdrop behind the overlay** for white and icy ground: Off,
  Light, Medium, Strong or Solid, in Settings → Overlay. *Darker by itself
  on icy and rocky-ice bodies* (on for everyone) takes it to at least
  Medium on those bodies and leaves every other one as you set it.
- **The EDSMT logo** on the welcome window, in Settings → About, and as the
  window's icon on the title bar and the taskbar.
- **A status strip** under the top bar: CMDR, ship, system, body, whether
  you are docked, landed, in the SRV, on foot or in flight, and whether the
  overlay is up.
- **The tools are a strip of tabs** under it — Map, Find, My sites, Where to
  land, Earnings, Powerplay, Leaderboard — with **F2** to **F8** to open
  them from the keyboard. The top bar keeps the room for where you are.
- **Four figures over the map**: the session's tonnes, Cr/hr, the rigs down
  and how much of the survey area is swept.
- **Along the bottom**: the keys, **SPACING** — *Comfortable* or *Compact*,
  changed at once — and the **THEME** with **<** and **>** to step through
  every theme.
- **Overlay uses the app theme**, a switch on Settings → Theme: the overlay
  wears whatever the app wears and changes as soon as it is saved, with its
  own picker greyed out while it is on. On for a new install; an older
  settings file keeps the overlay it had.
- **A launcher can see EDSMT is running**: a small file in the Radio Raxxla
  folder of your user data says which version is open, and goes when
  EDSMT closes. Nothing about you is in it.

### Changed

- **A site can take twelve rigs.** The rig count recorded against a
  deposit now goes to 12 - two Rhinos' worth - on the rail, in the deposit
  editor, in chat tags and in imports (asked on the Discord). The Rhino
  itself is unchanged: six rigs, the rig keys 1 to 6, "rigs full" at the
  sixth; a wing's second Rhino still takes 7 to 12.
- **Signed updates**: each release's version.json is signed on the build
  machine, and EDSMT checks the signature before it downloads a build - a
  checksum proves the file matches the list, the signature proves who wrote
  the list. An update not signed with Radio Raxxla's key is refused and the
  download page is offered instead.
- **EDSMT has its own address**: the community map, the leaderboard, the
  live map and the weekly report are at **edsmt.radioraxxla.com**. The
  first address still works, and EDSMT falls back to it by itself if a
  network cannot reach the new one yet.
- **A new install starts ready to use**: the overlay on, with its
  step-by-step guide and the deposit card; the notes on every control; chat
  tags and the long press for a rig on; the map's trail off; Imperial gold
  for the app and the overlay. An existing settings file keeps every choice
  it has.

### Fixed

- **The scope comes back once every rig is down.** The rig planner's
  close-up stayed on while any pin was within 600 m, done or not, so with
  the last rig placed the scope sat zoomed on the finished pins (reported
  on the Discord). The close-up is for pins still to drive to.

### New — Share my week

- **Share my week** on the Leaderboard tab: your week on the surface as a
  card — finds, sites, bodies, systems, best patch, furthest from Sol, your
  place on the week's board, merits and the ribbons earned — drawn by the
  community map from what you shared, saved in the pictures folder and
  opened, ready to post. The weekly page has it too, under *Your week*,
  and so does your member page on radioraxxla.com.
- **Pairing sends your commander name** (the journal's, never typed) with
  the code, so the member page can show your EDSMT figures under your
  account without a name box.

### New — squadron share, off by default

- **Share my squadron stats with my squadron's site**, a switch of its own
  on Settings → Sharing, off until you turn it on and only at work once the
  journal has named your squadron. It fills your squadron's site from the
  game with four things and nothing else: your carrier's location and
  scheduled jumps, its buy and sell orders, your Powerplay rank and merits,
  and the hauling tonnage you deliver to builds. Never credits, carrier
  finance, what a carrier cost, your FID or anything anyone said in chat —
  those are never read. Sent in batches, at most once a minute.

### New — mining locations to EDDN

- **Send mining locations to EDDN**, Settings → Sharing, on to begin with.
  When the FSS reports Planetary Mining Locations on a body, that body's
  signal counts go to EDDN, the network other Elite tools read, with your
  CMDR name as the uploader. Nothing else goes: no finds, no position on
  the body, no credits. Only what the game reports as you play — never an
  old journal read back — and only when the system it names is the one
  the game last said you were in.

### New — best to mine, good and bad marks, your own marker colour, the materials the lists offer

- **Best to mine** in Where to land, above the body table: the five
  commodities worth most in the system, each with the best price known near
  here, the bodies with an intact shared site carrying it, and the ground
  odds.
- **A Value column** on Find's Sites table: what each site is worth at the
  best prices known. One click sorts the most valuable first.
- **By ground** in Where to land, shut to begin with: each kind of ground in
  the system with the share of shared sites on it that carried each
  commodity. One ground open at a time.
- **Good and bad marks** on a shared site — in My sites, on Find's Sites and
  Still there rows, and under the shared finds of the location you are in.
  One mark per commander per site, changed whenever you like; yours shows
  lit, with the community's counts beside it. Marks count towards how far
  the community map trusts a site. Made with no connection, a mark is kept
  and sent when there is one.
- **The location line** names the finds in the location you are in most
  valuable first, and so does the overlay's STATUS box.
- **You on the map and the scope** — in the Rhino or the ship — are drawn in
  a colour of your own: a cyan on every theme, or any colour picked on
  Settings → Theme.
- **The ship minimap**: below 10 km over a body with finds on the map, the
  scope comes up by itself in the ship, the body's sites round you, you
  drawn as a ship and the range widened to suit the height. It goes as you
  climb away or land. **Ship minimap** on Settings → Overlay turns it off.
- **A site card**: **card** on a site in Find and on a body in Where to land
  draws the body's shared finds where they are, with the site in the middle
  and what the map knows under it - rigs, commodities, who found it first -
  saved in the pictures folder and opened. The top sites on the community
  map come with the same cards on radioraxxla.com and in the weekly report,
  without positions: where on the body each one is stays in EDSMT.
- **Find's Powerplay search**: a sixth search for a Powerplay goal —
  Reinforce, Acquire or Undermine, for your Power (read from the journal)
  or one you pick. One row per place to mine and place to sell: the site,
  its system's Power and state, the station with its pad, demand and price
  age, how far apart they are, and an estimate an hour. Merits an hour show
  as "-" until the community map has measured enough to say. A line says
  how fresh the Powerplay state is.
- **Choose the materials the lists offer**: a tick list of the thirteen and
  the extras decides what the commodity type-ahead and the commodity filters
  offer. On Settings → Basics, and on the gear beside Find's commodity
  filter. All of them to begin with; what the body under you carries is
  offered either way.

## 1.10039

### New — Linux, a Theme tab with Powerplay and in-game colours, overlay boxes that change shape

- **Linux.** EDSMT runs on Linux from the same code, for Elite played
  through Proton, Lutris, Heroic or Bottles: `bash RUN.sh` from source, or
  the `EDSMT-linux-x86_64.tar.gz` file on each release. The game's Saved
  Games folder is found inside whichever Wine prefix was played in most
  recently; your data lives in `~/.local/share/RadioRaxxla/EDSMT`.
  Joystick and HOTAS buttons work from /dev/input, and hotkeys work on an
  X11 session (off on Wayland, and Settings says so). The overlay keeps its
  boxes, locking and opacity but cannot be clicked through on Linux, and
  the long press of the fire button stays Windows only — both said in
  Settings. The update button on Linux opens the download page rather than
  fetching a Windows file.
- **A Theme tab.** Settings has a **Theme** tab, second from the left: the
  app and overlay theme pickers, a strip of each theme's colours under
  them, and **Save and restart now** beside the app theme.
- **Twelve Powerplay themes**, one in each Power's colours. Pick a Power
  and the app and the overlay both take it.
- **Match my in-game HUD colours** reads the colours your game is using —
  the HUD colour matrix in GraphicsConfigurationOverride.xml, or the main
  text colour of a HUD mod when one is installed — and makes a theme of
  them for both. It says what it found, and reads it again at every start.
  Every new theme is held to the same contrast rules as the existing
  fourteen, which are all still there.
- **Fit a box to the cockpit.** Unlock the overlay and press **SHAPE** in a
  box's bar: four corner handles let it lean the way the canopy frame does,
  and a **BEND** slider curves it for a helmet visor. **Flat again** undoes
  it. The shape is kept as a share of the box, so it follows the box when it
  is moved or resized and fits any screen. A box with no shape set is drawn
  exactly as before.

### Fixed

- The website's FAQ said your CMDR name on a find was your choice. It is
  not and has not been since the leaderboard: every find carries the
  finder's name. The page now says so.

---

## 1.10038

### New — one search at a time, the location you are at, the leaderboard's three views

- **Find shows one search at a time.** A switch at the top picks Sites,
  Still there, Deposits, Sell prices or Mining bodies; only that search's
  filters are on screen, and one Search button (or Enter) runs it. Saved
  searches are a Saved menu beside Reset and keep their search.
- **Earnings is four pages** — This session, Where to sell, Sessions, System
  prices — each with only its own controls. The session you are on is shown
  as cards, with Start, Pause, End and Multi-session beside it.
- **Pop out and Dock.** Every tool tab has Pop out at the right of its
  header; Dock on that window brings it back. The tabs-or-windows switch is
  first in Settings → Basics.
- **The mining location you are at.** From the glide down, EDSMT works out
  which location you are over from your own signals and the finds others
  have shared, sets the Signal box and says what is in it — no need to
  target it in the game. The overlay's STATUS box names it too.
- **Leaderboard.** Three views: by points, Powerplay overall (your rank and
  total merits as the game reports them) and merits from mining; a Powers
  table for each. Finds far from Sol earn more: +5 beyond 500 Ly, +10 beyond
  2,000, +20 beyond 10,000, +30 beyond 25,000.
- **Where to land** counts a body's mining locations from the FSS as well
  as the DSS (4.4.2 journals).

### Changed

- Where to land and Powerplay say *Why* in a few words; rest the mouse on
  the cell for the whole sentence.
- Powerplay's filters stay on Where it counts only.

### Fixed

- Showing a tab called itself a few hundred times a press before settling.
- The update download refuses a redirect off HTTPS.

---

## 1.10037

### Fixed — Find could hang and close at some window sizes

- At some window sizes and display scalings the results box kept showing
  and hiding its scrollbar, flashed, stopped answering and closed. It now
  settles at once, and a scrollbar that cannot decide stays shown.

---

## 1.10036

### New — tabs, leaderboard, mining bodies galaxy-wide

- **Tools as tabs.** Find, My sites, Where to land, Earnings, Powerplay and
  the new Leaderboard open as tabs of the main window, with Map to come
  back. Settings → Basics puts them back in windows of their own.
- **Leaderboard.** This week (from the Powerplay tick), this month, last
  month and all time: points for finds, first finds on a body, confirmed
  sites, old sites seen again, worked-out reports, regrowth and shared rig
  layouts. Powerplay merits from selling what you mined sit beside the
  points, with a merits ranking and totals per Power. Leave takes you off.
- **Mining bodies galaxy-wide.** Find → Mining bodies lists bodies near you
  with mining locations from what commanders' tools publish, not only
  deposits marked in EDSMT, with the ground, the odds and the sample size.
- **What the community measured.** How long worked-out deposits take to
  come back, and how close rigs have gone, from everyone's reports.
- **At the dock.** Open the commodities market with mined cargo aboard and
  EDSMT says what selling here pays, after crew wages, and the merits when
  it counts for your Power.
- **Rig count from the fire button.** Hold the SRV's Primary or Secondary
  fire to count a rig; EDSMT reads the binding from the game's controls.

### Changed

- Find lists every match, not the first 500.
- Every find is shared with your commander name; the sharing section in
  Settings is gone.
- Powerplay merits earned are on Earnings, per session.

### Fixed

- Mining signals are recognised in every game language.
- A price the game gives several unrelated commodities is ignored.
- A session written twice is counted once.
- The top bar keeps every button whole on narrow windows.

---

## 1.10035

### New — one stop for the whole hold, Powerplay, guided survey

- **Where to sell: one stop for the whole hold.** The three stations that pay
  most for everything aboard (ship and SRV together), with what each takes,
  how old its prices are and how many jumps away it is. Sell within 1, 2, 4
  or 8 jumps, and see which way a station's price and demand are moving.
- **Powerplay window.** Expand, Reinforce or Undermine for every system you
  have visited, judged by where each tonne was mined, with a merit estimate
  learnt from your own sales.
- **Search.** Find filters (distance window, pad, station type, carriers,
  price age, demand, minimum price, Powerplay), body and signal search in
  Where to land and My sites, and saved searches.
- **Guided survey.** Numbered waypoints that skip ground already swept, on the
  compass, scope and map; resumes after a restart.
- **Rigs.** Spacing rings and NEXT RIG to the nearest legal spot, top patches
  with Cr/h, the rig planner out of beta, and how many rigs fit per deposit.
- **On the map.** Your trail, lines to the nearest deposits, scope zoom, map
  and scope filters, mark a deposit from range, and pointers back to the Rhino
  or the ship and from orbit to your deposit.
- **My sites.** Depletion dates and rechecks, favourites, a bin, and import
  from other mining tools.
- **Controls.** Joystick and HOTAS buttons for every action, chat commands
  (off by default), and an optional long press to count a rig.
- **After the session.** The ship's hold while you are in the Rhino, map
  pictures, one Discord post per session updated after the sale, and a
  support bundle for bug reports.

### Changed

- Session earnings leads with the current session, with estimated Cr/hr and
  merits/hr.
- The commodity picker shows a tick for each selected commodity.

### Fixed

- Where to sell could show an old or out-of-range price as current, and
  Aboard could under-count the hold. Every price now shows its age and
  source, prices older than a day are marked stale, and markets with no
  demand are left out.
- System prices are listed most expensive first.
- Merits from support missions are no longer counted as merits earned by a
  sale.

---

## 1.10034

### Fixed — settings lost when you built or updated

Every time the build was made on a PC with EDSMT's data on it, one of the
checks wrote its test settings over the real ones: overlay placement,
layout, theme and keys went back to the defaults. Every check now runs in a
folder of its own, and settings can no longer be lost for good:

- **Earlier settings** (Settings → Your data): EDSMT keeps a dated copy of
  your settings whenever something that matters changes - the last thirty.
  Pick one and press **Put these back**: overlay placement, layout, theme,
  keys, the lot, at once.
- **Restore from a backup** now puts the settings in the zip back as well,
  straight away, instead of leaving the old ones in charge until a restart.
- A backup now carries the ground you have swept and the survey border of
  every body, and the dated settings copies, as well as your finds.

### New — Where to land remembers every system

A system honked in an earlier session showed "0 bodies scanned". EDSMT now
reads all your older journals once, in the background, and remembers every
body they describe; asks the public body database, through the community
server, for systems your own journals have not covered; and keeps every new
scan as it happens. Where to land says how many came from the public
database, and while it is still reading your older journals. Your own
journal always wins over the public database.

### New — your own Discord channel

Settings → Sharing → **Discord**: paste a channel's webhook and every find
you mark, and a summary of every Rhino session - tonnes, time, credits,
Cr/hr, t/hr, where you sold - is posted there as you play. **Send a test
message** checks it. The webhook stays behind dots, and nobody in the
channel is ever pinged by anything typed.

### New — rigs

- **Rigs survive a restart.** They used to be held in memory: close EDSMT
  and every rig was gone. They are written down as they change.
- **TOO CLOSE TO RIG n** on the boxes inside the rig spacing of one of your
  own rigs, so you know before you drop the next one; dropping one there
  anyway is marked and warned about. **COLLECT RIG n**, in cyan, when you
  are back at a rig that has been working.
- **A rig is marked where it lands**: 7 m behind the cockpit (a setting),
  not where you are sitting.
- A Rhino **docking in the ship takes its own rigs off the scope** (a
  setting); the other Rhino's stay.
- **Double-click a rig on the map** to put right what it is mining, or to
  pick it up on its own.
- **A rig dropped on somebody else's shared find** - or on the one you
  picked - is on their commodity, not on whatever the box last said.
- **Past 6 km the rigs are forgotten**, and every warning with them. Out of
  the Rhino - in the ship, on foot - no rig warning goes up at all: the
  distance from there is not the Rhino's.
- **Shared rig layouts**: when your rigs come up, how they were laid out on
  the deposit - and the edge and pins, if you used the rig planner - goes
  on the community map. On a deposit with no plan of your own, the best
  layout other commanders used shows as **SHARED PIN** pins on the scope.

### New — and the rest

- **Find has a Distance column**: how many light years each site and
  deposit is from where you are, whether or not you picked a radius.
- **A note on every control**: rest the mouse on anything for what it does.
  Settings → Basics turns them off.
- **A first-run tour** of the main window, once; Settings → Basics runs it
  again. Never over the game.
- **Settings in tabs**: Basics, Overlay, Keys, Rigs, Sharing, Your data,
  About.
- **SRV FUEL LOW** on the boxes when the game says the SRV is low.
- **t/hr** in Earnings: tonnes an hour, beside Cr/hr.
- **In the Rhino with the overlay off**, EDSMT says how to turn it on - on
  your first three sessions only.
- **Installed to C:\EDTools\RadioRaxxla\EDSMT**, with a Radio Raxxla folder
  in the Start menu. An older install is moved there by the update: only
  its own program files are taken out of the old folder, and your finds
  and settings, which live elsewhere, are not touched.

### Fixed

- Finishing the guide left its box on the overlay, frozen on the last card.
  It goes as the guide does.
- A box's suggestion list stayed open after a click on the map or a panel.
  A click anywhere else, or a second click in the box, shuts it.
- Radio Raxxla staff can take a wrong find, or a wrong site, off the
  community map from Find. What is removed is kept, with who removed it.

---

## 1.10033

### New — look up any system's prices, and tick several commodities

**Earnings → Prices in a system**: type a system, or leave it blank for the
one you are in, and get the last known sell price of each commodity at every
market there — station, pad, demand, when it was seen, and whether it came
from another commander's market read or the market index, whichever is newer.
**Best market only** shows the best station for each commodity; untick it
for all of them.

Every commodity box in a search — Find, Where to land, My sites and Prices in
a system — now ticks several at once. Click to tick, click again to untick,
**Any** clears them; or type `Monazite, bast` and press Enter. Best sell
prices answers for each one you ticked, in one table.

### New — a key for the overlay, and the overlay only in the Rhino

**Alt+0** turns the overlay on and off (rebind it in Settings). By default it
shows only while you are driving a Rhino; switch that off in Settings if you
want it in the ship too.

### Changed — every find goes on the community map

Sharing is no longer a switch: every deposit you mark and every market you
open goes on the one community map, and **Find** is open to everybody from
the start. The first start asks only whether to put your CMDR name on your
finds — Settings has it after. Your notes, sessions and settings never leave
your PC.

### New — a backup before every update

**INSTALL UPDATE** now saves a dated backup of your finds and settings to
Documents → EDSMT backups first, and keeps the last ten.

### New — two Rhinos, and the overlay at any size

- Two Rhinos on one ship: six rigs each, twelve in all, and the rig keys act
  on the Rhino you are driving. Earnings splits a session per Rhino.
- Overlay text size now moves the rows instead of stacking them, on every
  screen from 1024×768 to 7680×2160, ultrawide and 4K included. Layout
  presets (Standard, Map focus, Minimal, Streamer) and a stronger look for
  the ground you have swept (Faint, Clear, Solid) are in Settings → Overlay.

### Fixed

- The survey centre and border are kept through a trip back to the ship.
- The guide no longer sticks on 2/11 when you drop out of supercruise
  straight at the body.
- Touching down by a mining location fills in its signal number on a body
  you have not logged yet.
- Rigs lost to a disconnect: after a relog EDSMT offers to clear them.
- The compass letters are no longer cut off at the top of the strip.
- The top bar no longer squeezes its buttons when the readouts are long.
- On 768-line and 1080p screens the DEPOSIT box no longer wrote its rows over
  SIGNAL POINT.

### Also

EDSMT connects to the Radio Raxxla community map only — there is no server
address to set. The Rhino is on the first-run window and in the new
**Settings → About EDSMT**. Thanks to CMDR Todd Jenkins for testing.

---

## 1.10032

### New — an estimate of what a deposit holds, before you work it

A deposit you have not worked out yet shows **est. holds** and **est. left**,
from the deposits you have worked out with the same rig count and density —
the tonnes the game itself counted off them, never a formula. It says how
many it rests on, and it shows nothing when there is nothing like it to go
on. A deposit you have worked out still shows its own measure.

### New — the next rig pin on the compass tape

The rig planner's next pin is an amber diamond on the compass with its
distance, pinned to the end with an arrow when it is behind you.

### Changed — a rig counts on a pin within half the spacing

39 m at the default 78 m, instead of 20 m: a rig dropped a car's length off
the pin now ticks it off and moves you on to the next.

### New — delete a session from Earnings

Every row on the Earnings tab has a **delete** button: press it, then press
it again on the same row within six seconds. The file before is kept as
`sessions.csv.bak`.

### Fixed — Community Goal prices are no longer "the best price"

A station reading demand 999,999 is a Community Goal's placeholder, not a
market, and the Ega CG's 1,038,104 Cr showed as the top price for Iridium,
Periclase Dunite and Thortveitite under it. Such rows are left out, in the
app and on the server. The commodity table's average and top prices are
refreshed to the community list's 21 September figures, after the CG, and
Methanol Crystals are listed on rocky ice worlds as well as icy bodies.

### Changed — shared finds come in through a box you can see

**Settings → Your finds** has a box: paste the shared lines, press **Import**
or Enter. EDSMT no longer reads whatever is on the clipboard.

---

## 1.10031

### New — a key for every rig

**Alt+4 to Alt+9** put rigs 1 to 6 down, and the **same number with AltGr**
picks that rig up — AltGr+4 is rig 1 up. **AltGr+3** updates the deposit you
are on, **AltGr+0** is every rig up. On a keyboard without AltGr it is
Ctrl+Alt, and EDSMT names the keys that way. Alt+1 to Alt+3 are unchanged,
and none of the keys is used by any of the game's own control schemes. Keys
you set yourself are kept; the rest move once, and EDSMT says so.

### Changed — a deposit needs all four boxes

Commodity, rigs, amount and density, or it is not marked — finds were reaching
the shared map without the amount and density. The scanner's density counts
when the game names one. After a mark, rigs, amount and density clear
themselves for the next deposit.

### Changed — Find opens once you have shared a find of your own

Reading the shared map starts with adding to it: switch sharing on and mark
one deposit, and Find is open from then on.

### Changed — Earnings is mining, not hauling

A session starts with your **first rig down**, the first tonne the Rhino
refines, or **Start session** — not the Rhino going out, which it also does
to haul and to look. It ends when **every rig is back up**, when the Rhino
comes aboard, or on **End session**. **Pause** stops the clock for a break or
the drive to a station, and credits per hour leaves it out. The hold on the
Earnings tab is only what the Rhino dug up: bought and hauled cargo is left
out. A crewmate taking the ship's other Rhino out no longer counts as your
trip.

### New — three prices for what you mined

**Galactic average** (the game's own figure, read off any commodity market
you open — an estimate until you do), the best price **in the system you are
in**, and the **best within** the distance you pick. The price in your own
system is no longer cut off when twenty better ones are in range.

### New — the rig planner (beta, off until switched on)

Press **AltGr+2** and drive round the deposit's edge: EDSMT works out where up
to six rigs fit, 78 m apart by default (the community's working figure — a
setting), and puts a numbered pin on the scope for each, in driving order.
STATUS says which pin is next and how far; each goes green as a rig goes
down on it.

### New — the wing link (beta, off until switched on)

Friends on one body, or crew off one ship with more than one Rhino: type the
same six-character code and see each other's Rhinos and rigs on the scope. A
rig dropped too close to a wingmate's says so. Nothing is stored — the server
forgets you two minutes after your last beat.

### New — text size per overlay box

Each box has its own text size in Settings, 80% to 200%, without making the
box bigger. Asked for by the testers.

### Changed — the guide steps aside after your first full run

It switches itself off once you have followed it through signal, deposit
and rigs, and says so. Settings turns it back on.

### Fixed — finds load fast

Result pages drew a toolkit button two or three times a row, and a search
waited for the next slow tick to be picked up. Rows are plain now, results
are collected ten times a second, and My sites draws a page at a time.

### Also

- Keys pressed with AltGr are captured properly in Settings.
- A questions section on the download page.
- The GitHub build finds the Inno Setup compiler wherever it is installed.

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
