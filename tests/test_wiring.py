"""Every self.something() call must resolve to something that exists.

This exists because FindWindow.__init__ ended with

    top.bind("<Configure>", self._rewrap)

and _rewrap was never written. The AttributeError aborted __init__ at that
line, so the filter row, the three search buttons, the results table and the
status label were never built - and Tk swallows exceptions raised inside a
button command, so the window simply opened empty with no error anywhere.

The shipped symptom was "Find shows nothing". The cause was a typo'd
reference three screens away from the code that looked broken.

Nothing else catches this. The stubs answer any attribute with a callable,
so a headless run cannot see it; the packaging audit looks for functions
written and never called, which is the exact opposite failure.
"""
import ast, os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


# ---------------------------------------------------------------------------
# Names the toolkit provides, so a call to one of them is not a missing method
# ---------------------------------------------------------------------------

def public_methods(path):
    found = set()
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return found
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found.add(item.name)
    return found


# Pinned, because the machine this runs on has no Tk to introspect.
TOOLKIT = {
    "after", "after_cancel", "after_idle", "attributes", "bbox", "bell",
    "bind", "bind_all", "bind_class", "bindtags", "cget", "clipboard_append",
    "clipboard_clear", "clipboard_get", "columnconfigure", "config",
    "configure", "deiconify", "destroy", "event_generate", "focus",
    "focus_force", "focus_get", "focus_set", "geometry", "grab_release",
    "grab_set", "grid", "grid_columnconfigure", "grid_forget",
    "grid_rowconfigure", "iconbitmap", "iconify", "iconphoto", "lift",
    "lower", "mainloop", "maxsize", "minsize", "nametowidget",
    "overrideredirect", "pack", "pack_forget", "pack_propagate",
    "pack_slaves", "place", "place_forget", "protocol", "quit", "register",
    "resizable", "rowconfigure", "state", "title", "tkraise", "transient",
    "unbind", "unbind_all", "update", "update_idletasks", "wait_window",
    "winfo_children", "winfo_exists", "winfo_height", "winfo_ismapped",
    "winfo_pointerx", "winfo_pointery", "winfo_reqheight", "winfo_reqwidth",
    "winfo_rootx", "winfo_rooty", "winfo_screenheight", "winfo_screenwidth",
    "winfo_toplevel", "winfo_width", "winfo_x", "winfo_y", "withdraw",
    "wm_attributes", "wm_geometry", "wm_state", "wm_title",
    # tkinter.Canvas, which the plan view draws on. Not in the customtkinter
    # source, so introspecting the library never finds these.
    "addtag_withtag", "canvasx", "canvasy", "coords", "create_arc",
    "create_bitmap", "create_image", "create_line", "create_oval",
    "create_polygon", "create_rectangle", "create_text", "create_window",
    "dchars", "delete", "find_all", "find_closest", "find_overlapping",
    "find_withtag", "gettags", "itemcget", "itemconfig", "itemconfigure",
    "move", "moveto", "postscript", "scale", "tag_bind", "tag_lower",
    "tag_raise", "tag_unbind", "type", "xview", "yview",
}
spec = importlib.util.find_spec("customtkinter")
if spec and spec.origin:
    root = os.path.dirname(spec.origin)
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".py"):
                TOOLKIT |= public_methods(os.path.join(folder, name))

check("toolkit method names collected", len(TOOLKIT) > 150, len(TOOLKIT))
check("bind is among them", "bind" in TOOLKIT)


# ---------------------------------------------------------------------------
# Walk every class and resolve every self.x(...) it makes
# ---------------------------------------------------------------------------

def base_names(cls):
    for base in cls.bases:
        if isinstance(base, ast.Attribute):
            yield base.attr
        elif isinstance(base, ast.Name):
            yield base.id


def provided_by(cls):
    """Everything a call on self may legitimately land on, in this class.

    Methods it defines; attributes it assigns anywhere (an attribute can
    hold a callable, and several do); and anything a for-loop or with or
    walrus binds onto self.
    """
    names = set()
    for item in cls.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(item.name)
    for node in ast.walk(cls):
        targets = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        elif isinstance(node, ast.For):
            targets = [node.target]
        for target in targets:
            for sub in ast.walk(target):
                if (isinstance(sub, ast.Attribute)
                        and isinstance(sub.value, ast.Name)
                        and sub.value.id == "self"):
                    names.add(sub.attr)
        # setattr(self, "name", ...) - nothing uses it today, but a missed
        # one here would read as a false failure and get the check deleted.
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "setattr" and len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "self"
                and isinstance(node.args[1], ast.Constant)):
            names.add(node.args[1].value)
    return names


def calls_on_self(cls):
    """self.x(...) and bare self.x passed as a callback.

    A callback reference is the whole point: the bug that prompted this
    file was a reference handed to bind(), not a call.
    """
    for node in ast.walk(cls):
        if (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"
                and isinstance(node.ctx, ast.Load)):
            yield node.attr, node.lineno


FILES = ("edsmt.py", "overlay.py", "planview.py")
print("== every self.x on a window class resolves ==")

inspected, missing = 0, []
for filename in FILES:
    path = os.path.join(REPO, filename)
    if not os.path.exists(path):
        continue
    tree = ast.parse(open(path, encoding="utf-8").read())
    classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    for name, cls in classes.items():
        # Everything this class provides, plus everything its in-file
        # ancestors provide, plus the toolkit.
        pool = set(TOOLKIT)
        seen, queue = set(), [name]
        while queue:
            current = queue.pop()
            if current in seen or current not in classes:
                continue
            seen.add(current)
            pool |= provided_by(classes[current])
            queue.extend(base_names(classes[current]))
        for attr, line in calls_on_self(cls):
            inspected += 1
            if attr not in pool:
                missing.append("%s.%s (%s line %d)" % (name, attr, filename, line))

check("references were actually inspected", inspected > 400, inspected)
check("none of them point at nothing", not missing, missing[:12])

# ---------------------------------------------------------------------------
# And then actually build every window, with the stub's catch-all turned off
# ---------------------------------------------------------------------------
# The stub answers ANY unknown attribute with a callable, which is what let
# the missing _rewrap through a full headless run. Real Tk does not do that.
# So for this one check the catch-all only covers names the toolkit really
# provides, and anything else raises the way it would on a commander's
# machine. It is the difference between "the logic is right" and "the window
# opens".

sys.path.insert(0, os.path.join(HERE, "stubs"))
sys.path.insert(0, REPO)
import _ctkstub as C

_original = C._W.__getattr__

def _strict(self, name):
    if name in TOOLKIT or name.startswith("__"):
        def anything(*a, **kw): return None
        return anything
    raise AttributeError("%s has no attribute %r"
                         % (type(self).__name__, name))

import edsmt as A
import survey as SV


class _Store:
    """Answers anything with an empty result. A window must build against
    an empty database - that is what first run looks like."""
    def __getattr__(self, name):
        def nothing(*a, **kw): return []
        return nothing


class _Comm:
    ready = False
    can_read = True
    url = "https://api.radioraxxla.com"


def _app():
    app = C._W()
    app.community = _Comm()
    app.store = _Store()
    app.settings = dict(A.DEFAULT_SETTINGS)
    app.game = None
    app.updates = None
    app.signal_choices = lambda: [str(n) for n in range(1, 9)]
    return app


ROW = {"id": 1, "system": "Ega", "body": "Ega 1", "location": "1",
       "offered": "", "lat": 1.0, "lon": 2.0}
DEPOSIT = {"id": 1, "system": "Ega", "body": "Ega 1", "location": "1",
           "commodity": "Gold", "rigs": 2, "lat": 1.0, "lon": 2.0,
           "bearing": 90.0, "distance": 1.2, "kind": "", "amount": "",
           "density": "", "notes": ""}

class _Watcher:
    system = "Ega"
    def system_bodies(self, system=None):
        return [{"body": "Ega 1", "landable": True, "distance_ls": 12.0,
                 "planet_class": SV.ROCKY, "volcanism": "", "gravity_g": 0.2,
                 "temperature_k": 180.0, "locations": 3, "mapped": True}]


def _land_app():
    """The stub app, with the real Where to land methods on it."""
    import types
    app = _app()
    app.watcher = _Watcher()
    app.prices, app.grounds, app.land_sites = {}, None, {}
    app._land_asked, app._grounds_at, app._grounds_asked = {}, 0.0, 0.0
    app._land_error, app.survey_book = "", None
    for name in ("want_landing", "land_rows", "land_signature", "land_swept",
                 "land_sites_for", "land_problem", "follow_land",
                 "_land_changed", "take_grounds", "take_landing"):
        setattr(app, name, types.MethodType(getattr(A.EDSMT, name), app))
    app._Comm_calls = []
    app.community.grounds = lambda: app._Comm_calls.append("grounds") or True
    app.community.system_sites = lambda s: app._Comm_calls.append(s) or True
    return app


WINDOWS = [
    ("FindWindow", lambda: A.FindWindow(_app())),
    ("LandWindow", lambda: A.LandWindow(_land_app())),
    ("SettingsWindow", lambda: A.SettingsWindow(_app())),
    ("WelcomeWindow", lambda: A.WelcomeWindow(_app())),
    ("EditLocationWindow", lambda: A.EditLocationWindow(_app(), dict(ROW))),
    ("EditWindow", lambda: A.EditWindow(_app(), dict(DEPOSIT))),
]

print("== every window finishes building ==")
C._W.__getattr__ = _strict
built = []
try:
    for name, make in WINDOWS:
        try:
            make()
            built.append((name, None))
        except Exception as exc:
            built.append((name, "%s: %s" % (type(exc).__name__, exc)))
finally:
    C._W.__getattr__ = _original

for name, error in built:
    check("%s reaches the end of __init__" % name, error is None, error)

# And prove the strictness is real, or the five checks above are theatre.
class _Naive(C._W):
    def __init__(self):
        C._W.__init__(self)
        self.bind("<Configure>", self._never_written)

C._W.__getattr__ = _strict
try:
    _Naive()
    caught = False
except AttributeError:
    caught = True
finally:
    C._W.__getattr__ = _original
check("a missing method really does raise under this stub", caught)

print("== nothing is defined twice ==")
# edit_deposit was defined twice in EDSMT and here() was defined twice
# before it. Python keeps the LAST definition silently, so the first one -
# usually the one with the error handling, or the one the tests matched on
# - simply stops existing. Both shipped. Neither was caught by anything.
import collections
dupes = []
for filename in FILES + ("survey.py", "journal.py", "edonline.py"):
    path = os.path.join(REPO, filename)
    if not os.path.exists(path):
        continue
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        seen = collections.Counter(
            item.name for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)))
        for name, count in seen.items():
            if count > 1:
                dupes.append("%s.%s defined %d times (%s)"
                             % (node.name, name, count, filename))
    # module level too
    seen = collections.Counter(
        item.name for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)))
    for name, count in seen.items():
        if count > 1:
            dupes.append("%s() defined %d times (%s)" % (name, count, filename))

check("no method or function is defined twice", not dupes, dupes)

print("== the core loop runs, not just the windows ==")
# EDSMT itself was never constructed by ANY test, and every other suite
# used __new__ to skip __init__. So mark_deposit - the button the whole
# app exists for - raised TypeError on the first F10 of every new body
# for an unknown number of releases. The deposit reached the CSV, then
# the raise aborted the share, the redraw and the status line. From the
# button Tk swallowed it entirely; from F10 it was reported as a
# "Journal problem", blaming the reader for a bug in the store.
#
# This drives the real methods against the real Survey on a temp folder.
import tempfile, shutil
import survey as SV

_tmp = tempfile.mkdtemp(prefix="edsmt-wiring-")
try:
    store = SV.Survey(_tmp)

    class _Game:
        running = True
        system, body = "Ega", "Ega 1"
        lat, lon, heading = 12.5, -45.5, 90.0
        radius_m = 1.2e6
        cmdr = "TESTER"
        in_srv = landed = True
        has_position = True
        detected_type = detected_density = None
        star_pos = (0.0, 0.0, 0.0)
        system_address = 10477373803
        body_facts = {"Ega 1": {"planet_class": "Icy body"}}
        def body_temperature(self): return 210.0
        def body_profile(self):
            return {"planet_class": "Icy body", "gravity": 0.3,
                    "atmosphere": "", "volcanism": ""}

    app = A.EDSMT.__new__(A.EDSMT)
    app.store = store
    app.game = _Game()
    app.settings = dict(A.DEFAULT_SETTINGS)
    app.said = []
    app.say = lambda text, colour=None: app.said.append(str(text))
    app.signal = lambda: "1"
    app.selected = None
    app.shared = []
    app.share = lambda *a, **k: app.shared.append(a)
    for name in ("refresh_locations", "refresh_deposits", "refresh_commodities",
                 "redraw", "refresh_location_note", "on_pick"):
        setattr(app, name, (lambda *a, **k: None))
    def _box(value):
        # Bound as a default argument on purpose: a bare `lambda: value`
        # in a comprehension closes over the LOOP variable, so all four
        # boxes returned whatever the last one happened to be.
        return type("B", (), {"get": staticmethod(lambda v=value: v)})()
    app.fields = {k: _box(v)
                  for k, v in (("commodity", "Water"), ("rigs", "3"),
                               ("amount", "High"), ("density", "Medium"))}

    # The exact case that was broken: no signal row exists yet, so
    # mark_deposit must CREATE one. This is the first F10 on a new body.
    before = len(store.locations)
    error = None
    try:
        A.EDSMT.mark_deposit(app)
    except Exception as exc:
        error = "%s: %s" % (type(exc).__name__, exc)
    check("the first F10 on a new body does not raise", error is None, error)
    check("and it created the signal row it needed",
          len(store.locations) > before, len(store.locations))
    check("the deposit was recorded", len(store.deposits) == 1,
          len(store.deposits))
    check("and the commander was told", any("Water" in t for t in app.said),
          app.said)

    # set_location must accept every column LOCATION_FIELDS carries, or
    # the caller raises on a keyword the store silently never had.
    import inspect
    accepted = set(inspect.signature(SV.Survey.set_location).parameters)
    described = {"planet_class", "gravity", "atmosphere", "volcanism",
                 "temperature_k", "lat", "lon", "radius_m"}
    missing = sorted(described - accepted)
    check("set_location accepts every field its callers pass", not missing,
          missing)
finally:
    shutil.rmtree(_tmp, ignore_errors=True)

print("== the specific one that bit ==")
source = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
check("_rewrap is defined, not just bound", "def _rewrap(" in source)
check("and it is still bound", 'bind("<Configure>", self._rewrap)' in source)

print("== the importer only asks the store for things the store has ==")
# The exact mistake this catches was made while writing it: set_location
# was handed notes="imported from ...", which LOCATION_FIELDS carries as a
# column but the method has no parameter for. It would have raised
# TypeError on the first real import - past the backup, past the first
# rows, halfway through somebody's database.
import inspect as _inspect
import survey as _SV

_tree = ast.parse(source)
_imp = next(n for n in ast.walk(_tree)
            if isinstance(n, ast.FunctionDef) and n.name == "import_finds")
_bad = []
for _node in ast.walk(_imp):
    if not isinstance(_node, ast.Call):
        continue
    _func = _node.func
    if not (isinstance(_func, ast.Attribute)
            and isinstance(_func.value, ast.Name) and _func.value.id == "store"):
        continue
    _method = getattr(_SV.Survey, _func.attr, None)
    if _method is None:
        _bad.append("Survey has no %s()" % _func.attr)
        continue
    if _func.attr == "add_deposit":
        _allowed = set(_SV.DEPOSIT_FIELDS)          # **row, filtered to these
    else:
        _allowed = set(_inspect.signature(_method).parameters)
    for _kw in _node.keywords:
        if _kw.arg and _kw.arg not in _allowed:
            _bad.append("store.%s(%s=...) - not accepted" % (_func.attr, _kw.arg))
check("every keyword the importer passes the store is one it takes",
      not _bad, _bad)

print("== the import button is wired to something that exists ==")
_settings = next(n for n in ast.walk(_tree)
                 if isinstance(n, ast.ClassDef) and n.name == "SettingsWindow")
_commands = sorted({k.value.attr
                    for n in ast.walk(_settings) if isinstance(n, ast.Call)
                    for k in n.keywords
                    if k.arg == "command"
                    and isinstance(k.value, ast.Attribute)
                    and isinstance(k.value.value, ast.Name)
                    and k.value.value.id == "self"})
_missing = [c for c in _commands if not hasattr(A.SettingsWindow, c)]
check("every button in Settings names a method that is really there",
      not _missing, _missing)
check("and Import another tool's CSV is one of them",
      "import_now" in _commands, _commands)

_now = next(n for n in ast.walk(_settings)
            if isinstance(n, ast.FunctionDef) and n.name == "import_now")
_called = {n.func.id for n in ast.walk(_now)
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
check("it goes through the importer rather than reimplementing it",
      {"import_finds", "import_summary"} <= _called, sorted(_called))

print("== the two formats cannot be confused for one another ==")
_sets = {k: set(v["columns"]) for k, v in A.IMPORT_FORMATS.items()}
check("no format's columns are a subset of another's",
      not [(a, b) for a in _sets for b in _sets
           if a != b and _sets[a] <= _sets[b]],
      [(a, b) for a in _sets for b in _sets if a != b and _sets[a] <= _sets[b]])
check("every declared column is written the way the header is compared",
      all(c == A._import_key(c) for s in _sets.values() for c in s),
      [c for s in _sets.values() for c in s if c != A._import_key(c)])
check("and every format says which tool it is, in words a person reads",
      all(v["label"].strip() for v in A.IMPORT_FORMATS.values()))


print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
