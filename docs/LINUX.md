# EDSMT on Linux — what was looked up, and what it decided

Working notes behind the Linux side of EDSMT (1.10039). The user guide says
how to run it; this says why it is built the way it is, with the sources
each decision rests on. Read it before changing anything platform-specific.

## The shape of it

One codebase. Every Windows-only call already went through an object a
check can replace (`inputdev.WinmmReader`, `inputdev.WinMouse`, the
`ctypes` calls in `overlay.py`, `Hotkeys` in `edsmt.py`); the Linux side
sits behind the same seams:

| Seam | Windows | Linux |
|---|---|---|
| `journal.find_journal_dir` | Saved Games, as Windows reports it | every launcher's Wine prefix; the newest journal wins |
| `edsmt.data_dir` | `%LOCALAPPDATA%\RadioRaxxla\EDSMT` | `$XDG_DATA_HOME/RadioRaxxla/EDSMT` |
| `overlay.PLATFORM` (`WindowPlatform`) | colour key, click-through by window style | opacity only; no click-through, said in Settings |
| `inputdev.default_reader` | `WinmmReader` (winmm) | `JsReader` (`/dev/input/js*`) |
| `edsmt.Hotkeys` | RegisterHotKey message loop | `x11keys.X11Hotkeys` (XGrabKey), off without python-xlib or on Wayland |
| `inputdev.WinMouse` (long press) | user32 | not available; said in Settings |
| `edsmt.build_kind` (updater) | installed / portable | `""`: the button opens the download page |

Nothing in the Windows path changed. Every Linux branch has a check in
`tests/test_110039_linux.py` with a stand-in for the device or server.

## Where the game keeps its journal

Elite Dangerous is a Windows program on Linux, run through Wine or Valve's
Proton. The game writes `Saved Games\Frontier Developments\Elite Dangerous`
inside the Windows user profile of whatever Wine prefix it runs in, so the
question is where each launcher keeps that prefix.

| Launcher | Prefix | Windows user | Source |
|---|---|---|---|
| Steam (Proton) | `<library>/steamapps/compatdata/359320/pfx` | `steamuser` | Proton's own launcher script: `self.prefix_dir = self.path("pfx/")` on the compatdata folder, and paths under `drive_c/users/steamuser` ([ValveSoftware/Proton, `proton`](https://github.com/ValveSoftware/Proton/blob/proton_9.0/proton)). 359320 is the game's Steam app id. |
| Steam, where it lives | `~/.steam/steam`, `~/.steam/root`, `~/.steam/debian-installation`, `~/.local/share/Steam` | | The Proton README gives `~/.steam/steam/steamapps` as the usual library ([README](https://github.com/ValveSoftware/Proton/blob/proton_9.0/README.md)); the others are the symlink and the Debian package's folder. |
| Steam, other drives | each `"path"` in `steamapps/libraryfolders.vdf` | | Read by `journal.steam_libraries`. The Flatpak wiki (below) tells people to add a library on another drive from inside Steam, which writes that file. |
| Flatpak Steam | `~/.var/app/com.valvesoftware.Steam/.local/share/Steam` | `steamuser` | "installs Steam including its runtime under a sandbox in `~/.var/app/com.valvesoftware.Steam`", and the library is at `.local/share/Steam` inside it ([Flathub wiki](https://github.com/flathub/com.valvesoftware.Steam/wiki)). |
| Lutris | `~/Games/<game>` — the prefix is the game folder | the Linux user | Installer reference: "`prefix`: Path to the Wine prefix. For Wine games, it should be set to `$GAMEDIR`" ([lutris/docs/installers.rst](https://github.com/lutris/lutris/blob/master/docs/installers.rst)); `~/Games` is Lutris's default game folder, changeable in its preferences. |
| Heroic | `~/Games/Heroic/Prefixes/default` (shared) or `.../default/<game>`; with Proton, `pfx/` inside | the Linux user, or `steamuser` with Proton | The default prefix paths as Heroic users and maintainers report them ([Heroic issue 3274](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/issues/3274)). |
| Bottles | `~/.local/share/bottles/bottles/<bottle>`; Flatpak `~/.var/app/com.usebottles.bottles/data/bottles/bottles/<bottle>` | the Linux user | "`cd ~/.var/app/com.usebottles.bottles/data/bottles/bottles`", each bottle a folder ([Bottles documentation](https://github.com/bottlesdevs/documentation/blob/master/flatpak/expose-directories/use-system-home.md)). |
| Plain Wine | `~/.wine`, or `$WINEPREFIX` | the Linux user | Wine's defaults. |
| Proton, from inside | `$STEAM_COMPAT_DATA_PATH/pfx` | `steamuser` | The variable Steam hands Proton, which Proton's script turns into the prefix (first row). Only set when EDSMT itself is started from Steam. |

Two consequences:

- The Windows user folder is a wildcard (`drive_c/users/*`) everywhere but
  Proton, because plain Wine names it after the Linux user.
- A commander can have two prefixes with the folder in them — a Steam one
  and a Lutris one, say. The folder holding the newest `Journal*.log` is
  the one being played in (`journal.newest_journal_dir`); a folder with any
  journal beats one that has never seen the game; with none anywhere the
  first listed is taken. The folder set in Settings still beats all of it.

Extra globs that cost nothing and were not verified against a source:
Heroic's Flatpak id (`com.heroicgameslauncher.hgl`) and Lutris's
(`net.lutris.Lutris`) under `~/.var/app`. Settings carries a hint naming
the places looked in, Linux only (`journal.journal_hint`).

## Where EDSMT keeps its own data

`$XDG_DATA_HOME/RadioRaxxla/EDSMT`. The XDG Base Directory Specification:
"`$XDG_DATA_HOME` defines the base directory relative to which user-specific
data files should be stored. If `$XDG_DATA_HOME` is either not set or empty,
a default equal to `$HOME/.local/share` should be used"
([specifications.freedesktop.org](https://specifications.freedesktop.org/basedir-spec/latest/)).
Before 1.10039 the app used `~/.local/share` outright and ignored the
variable. `tests/run_all.py` points `XDG_DATA_HOME` at a sandbox for every
check, as it does `LOCALAPPDATA`.

## The overlay

Tk's `wm attributes`, from the Tk manual
([wm(n)](https://manpages.ubuntu.com/manpages/noble/man3/wm.3tk.html)):

- On all platforms: `-alpha`, `-fullscreen`, `-topmost`. "Where not
  supported, the `-alpha` value remains at 1.0" — on X11 that means a
  desktop without a compositing window manager shows the boxes opaque.
- Windows only: `-disabled`, `-toolwindow`, `-transparentcolor`. On X11 Tk
  answers `bad attribute "-transparentcolor"`; the old code caught the
  exception, the new code does not ask (`WindowPlatform.attributes`).
- X11 only: `-type` (EWMH window types) and `-zoomed`. Not used: the boxes
  are `overrideredirect`, which the window manager leaves alone anyway.

Click-through. On Windows the boxes get `WS_EX_TRANSPARENT`, and a click on
a locked box reaches the game. Tk offers nothing of the kind on X11, and
there is no `wm` attribute for it, so a locked box on Linux keeps the click.
The overlay stays usable — lock, unlock, drag, resize, the same panels — and
Settings → Overlay says so on Linux. A possible later step, not built: the
X Shape extension can set a window's *input* region to nothing
(`ShapeInput`), which is how some X11 overlays let clicks through; it would
need python-xlib's `shape` extension and a window handle from Tk, and it is
untested here.

`foreground_is_game` answers None off Windows, so the boxes stay up whatever
is in front, as the code always did where Windows could not be asked.

## Joystick buttons

The kernel's joystick interface
([joystick-api, kernel.org](https://www.kernel.org/doc/html/latest/input/joydev/joystick-api.html)):

- `/dev/input/js0` and up. Opened `O_RDONLY | O_NONBLOCK`; "EAGAIN is
  returned when the queue is empty".
- Each read gives whole `struct js_event` records: `__u32 time; __s16
  value; __u8 type; __u8 number;` — eight bytes (`struct.Struct("@IhBB")`).
- `JS_EVENT_BUTTON 0x01`, `JS_EVENT_AXIS 0x02`, `JS_EVENT_INIT 0x80`. On
  open "the driver will issue a series of synthetic events (JS_EVENT_INIT)
  that you can read to obtain the initial state of the joystick" — which is
  why a button already held when EDSMT starts is known, and (through
  `JoystickWatcher`) not counted as a press.
- For a button, `value` is 1 pressed and 0 released.

The page calls the interface legacy and points newer clients at evdev. The
js interface was chosen anyway: it is a plain file read with no library, it
gives button numbers that match the game's own `Joy_N` numbering closely,
and the device nodes are readable by the user at the desk on an ordinary
installation. If a stick is not seen, the thing to check is the permissions
of `/dev/input/js0` (the `input` group). `inputdev.JsReader` keeps the same
interface as `WinmmReader` — `devices()`, `reader(n)` → bit mask or None —
so `JoystickWatcher`, the Settings capture and `inputmix` do not know which
they have. Buttons past 32 are ignored, as on Windows; a torn record at the
end of a read is held back for the next.

## Hotkeys

The X way to a global key is a passive grab on the root window
([XGrabKey(3)](https://manpages.ubuntu.com/manpages/lunar/man3/XGrabKey.3.html)):

- "`XGrabKey` establishes a passive grab on the keyboard": when the key is
  pressed with exactly those modifiers, the keyboard is grabbed and the
  KeyPress goes to the grabbing client. The grab window "must be an
  ancestor of (or the same as) the focus window" — the root window is an
  ancestor of every window, which is what makes the grab global.
- "If some other client has issued a XGrabKey with the same key combination
  on the same window, a BadAccess error results" — that is how "already
  taken by another program" is known (`XServer.grab` catches it).
- A KeyPress is reported "only if the key is pressed with exactly the
  specified modifiers down, and no other modifiers are down", so Caps Lock
  (`Lock`) and Num Lock (`Mod2`) would stop a key working. Every binding is
  grabbed four times — plain, Lock, Mod2, both — and the two are masked off
  a press before it is matched (`x11keys.LOCKS`, `RELEVANT`).
- `XUngrabKey` "releases the key combination on the specified window if it
  was grabbed by this client"; `stop()` does that for every grab and closes
  the display. A client that dies loses its grabs with its connection.

Auto-repeat: the server sends a KeyRelease and a KeyPress with one
timestamp while a key is held; the second press of such a pair is dropped,
so a held key is one action, as `MOD_NOREPEAT` makes it on Windows. Alt is
`Mod1` and Super is `Mod4` on every usual keymap; a keymap with them moved
would need the modifier map read, which is not done.

python-xlib does the protocol work
([python-xlib](https://github.com/python-xlib/python-xlib), pure Python).
It is a Linux-only line of `requirements.txt` and goes into the one-file
build; without it `x11keys.why_not` names it and the keys are off. The real
adapter was driven on a real X server (Xvfb, with XTEST key presses) while
this was built: grabs took, Num Lock on and off both fired, a second client
asking for Alt+1 was refused by name, and the key was free again after
`stop()`. The checks use a stand-in server with the same five calls.

Wayland. The protocol a Wayland desktop speaks has no request by which an
ordinary client takes a key globally; an X grab made through XWayland is a
grab on *that* X server's root, which is an ancestor only of XWayland
windows, so by the manual's focus rule it fires only while an X client has
focus. Whether the game is one depends on the launcher. Rather than keys
that work for some people some of the time, the keys are off on a Wayland
session (`WAYLAND_DISPLAY` set, or `XDG_SESSION_TYPE=wayland`) and Settings
says so; joystick buttons and chat commands do the same job. Something to
revisit if the desktops' global-shortcut portal becomes usual.

## The long press of the fire button

Windows only. It reads the mouse buttons and the window in front through
user32 (`inputdev.WinMouse`). On X11 the same could be done with XInput2 or
evdev, and on Wayland not at all; it was not built. Settings → Rigs says so
on Linux, and the rig keys, joystick buttons and chat commands do the job.

## Updates

`version.json` names two packages, both Windows programs. `build_kind()`
answers `""` for a frozen build on Linux, so the update button opens the
download page as it does for a source checkout, and `EDSMT-<v>.exe` is
never downloaded onto a Linux machine. The Linux file is attached to each
GitHub release beside the Windows ones; it is not installed in place.

## Packaging

- `RUN.sh`: the Linux `RUN.bat`. Finds a Python 3.10 or newer that has
  tkinter (distributions package it apart: `python3-tk`, `python3-tkinter`,
  `tk`), makes `.venv`, installs `requirements.txt`, starts EDSMT. LF line
  endings, enforced by `.gitattributes`.
- `build/EDSMT-onefile.spec` builds on Linux as it is, with two guards: the
  `.ico` and the Windows version resource are not asked for off Windows,
  and `x11keys` plus every `Xlib` submodule are named as hidden imports
  there (python-xlib loads its keysym tables by name). The Windows result
  is unchanged.
- `.github/workflows/build.yml`: a separate `linux` job on `ubuntu-latest`
  installs Tk's shared libraries and Xvfb, runs `tests/run_all.py --quiet`
  under `xvfb-run`, builds the one file and uploads
  `EDSMT-linux-x86_64.tar.gz` (the program, README and LICENSE in one
  folder). The `release` job now waits for both builds and attaches it. The
  Windows job is byte for byte what it was.

## Sources

- Proton launcher script and README — https://github.com/ValveSoftware/Proton/blob/proton_9.0/proton , https://github.com/ValveSoftware/Proton/blob/proton_9.0/README.md
- Flatpak Steam wiki — https://github.com/flathub/com.valvesoftware.Steam/wiki
- Lutris installer reference — https://github.com/lutris/lutris/blob/master/docs/installers.rst
- Heroic default prefix paths — https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/issues/3274
- Bottles documentation — https://github.com/bottlesdevs/documentation/blob/master/flatpak/expose-directories/use-system-home.md
- XDG Base Directory Specification — https://specifications.freedesktop.org/basedir-spec/latest/
- Tk `wm` manual — https://manpages.ubuntu.com/manpages/noble/man3/wm.3tk.html
- Linux joystick API — https://www.kernel.org/doc/html/latest/input/joydev/joystick-api.html
- XGrabKey(3) — https://manpages.ubuntu.com/manpages/lunar/man3/XGrabKey.3.html
- python-xlib — https://github.com/python-xlib/python-xlib
