"""1.10040: the overlay can be read on bright ground.

On a white or icy body the boxes over the game were hard to see. Each box can
now have a see-through dark backdrop behind it - Off, Light, Medium, Strong
or Solid - and "darker by itself on bright ground" takes it to at least
Medium on icy and rocky-ice bodies, from the body type the journal gave.
Nothing changes on any other ground unless asked for.

    python tests/test_110040_backdrop.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
import overlay as OV  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


print("== the rule ==")
S = OV.backdrop_style
check("off is no backdrop", S("off") is None and S("") is None and S("nonsense") is None)
check("light, medium and strong are meshes, solid is filled",
      (S("light"), S("medium"), S("strong"), S("solid")) == ("gray25", "gray50", "gray75", ""))
check("on an icy body, auto takes it to at least medium",
      S("off", True, "Icy body") == "gray50" and S("light", True, "Rocky ice body") == "gray50")
check("but never lighter than asked", S("strong", True, "Icy body") == "gray75" and S("solid", True, "Icy body") == "")
check("on other ground auto leaves it alone", S("off", True, "Rocky body") is None
      and S("light", True, "High metal content body") == "gray25")
check("auto switched off leaves it alone everywhere", S("off", False, "Icy body") is None)
check("the choices Settings offers", [v for _l, v in OV.BACKDROPS] == ["off", "light", "medium", "strong", "solid"])


class Canvas:
    """Records every mark instead of making one."""
    def __init__(self):
        self.calls = []

    def delete(self, *_a):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kw):
            self.calls.append((name, args, kw))
        return record


class Window:
    def winfo_width(self): return 420
    def winfo_height(self): return 420
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080


class App:
    def __init__(self, ground=""):
        self.ground = ground

    def colour_for(self, name):
        return "#ff7a18"

    def planet_class(self):
        return self.ground


def drawn(mode, settings, ground=""):
    options = {"overlay_mode": mode, "overlay_click_through": True}
    options.update(settings)
    over = OV.Overlay(app=App(ground), tk_module=None, settings=options)
    over.window = Window()
    over.canvas = Canvas()
    over.draw([], 0.0, body="Ega 1", location="1")
    return over.canvas.calls


def backdrops(calls):
    return [kw for name, _a, kw in calls if name == "create_rectangle" and "backdrop" in (kw.get("tags") or ())]


print("== drawn behind the boxes ==")
for mode in ("radar", "strip"):
    plain = drawn(mode, {"overlay_backdrop": "off", "overlay_backdrop_auto": False})
    check("%s, off: no backdrop" % mode, not backdrops(plain), backdrops(plain))
    medium = drawn(mode, {"overlay_backdrop": "medium"})
    found = backdrops(medium)
    check("%s, medium: one dark meshed panel" % mode, len(found) == 1 and found[0].get("stipple") == "gray50"
          and found[0].get("outline") == "", found)
    check("%s: and it is sent to the back, under everything" % mode,
          any(name == "tag_lower" and a and a[0] == "backdrop" for name, a, _k in medium))
    icy = drawn(mode, {"overlay_backdrop": "off", "overlay_backdrop_auto": True}, ground="Icy body")
    check("%s, off + auto on an icy body: medium by itself" % mode,
          [k.get("stipple") for k in backdrops(icy)] == ["gray50"], backdrops(icy))
    rocky = drawn(mode, {"overlay_backdrop": "off", "overlay_backdrop_auto": True}, ground="Rocky body")
    check("%s, off + auto on rocky ground: nothing" % mode, not backdrops(rocky))

print("== settings ==")
src = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
check("new installs: no backdrop on ordinary ground, auto on", '"overlay_backdrop": "off"' in src
      and '"overlay_backdrop_auto": True' in src)
check("both are in Settings, each with a note", 'self._choice(body, "overlay_backdrop"' in src
      and 'self._switch(body, "overlay_backdrop_auto"' in src
      and '    "overlay_backdrop": "' in src.split("TIPS = {", 1)[-1]
      and '    "overlay_backdrop_auto": "' in src.split("TIPS = {", 1)[-1])

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
