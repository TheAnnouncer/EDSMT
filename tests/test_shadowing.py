"""Catch the app clobbering a toolkit method with an attribute of its own.

This exists because `self.state = None` in the main window replaced
tkinter's own state() method with None, and customtkinter calls state()
during startup - so the app died before drawing a single pixel, with a
TypeError naming neither the attribute nor the file that set it.

No headless widget stub can catch that: a stub has no state() to overwrite.
So it is checked statically instead, against the real customtkinter source
plus the tkinter method names, which are stable and worth pinning anyway.
"""
import ast, os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

# tkinter.Misc / Wm / Tk, which every window inherits. Pinned rather than
# introspected because a machine without Tk cannot import tkinter at all -
# which is exactly the machine this suite is designed to run on.
TK_METHODS = {
    "after", "after_cancel", "after_idle", "anchor", "aspect", "attributes",
    "bbox", "bell", "bind", "bind_all", "bind_class", "bindtags", "cget",
    "client", "clipboard_append", "clipboard_clear", "clipboard_get",
    "colormapwindows", "columnconfigure", "command", "config", "configure",
    "deiconify", "deletecommand", "destroy", "event_add", "event_delete",
    "event_generate", "event_info", "focus", "focus_displayof", "focus_force",
    "focus_get", "focus_lastfor", "focus_set", "forget", "frame", "geometry",
    "getboolean", "getdouble", "getint", "getvar", "grab_current",
    "grab_release", "grab_set", "grab_set_global", "grab_status", "grid",
    "grid_anchor", "grid_bbox", "grid_columnconfigure", "grid_forget",
    "grid_info", "grid_location", "grid_propagate", "grid_remove",
    "grid_rowconfigure", "grid_size", "grid_slaves", "group", "iconbitmap",
    "iconify", "iconmask", "iconname", "iconphoto", "iconposition",
    "iconwindow", "image_names", "image_types", "info", "keys", "lift",
    "location", "lower", "mainloop", "manage", "maxsize", "minsize", "nametowidget",
    "option_add", "option_clear", "option_get", "option_readfile", "overrideredirect",
    "pack", "pack_configure", "pack_forget", "pack_info", "pack_propagate",
    "pack_slaves", "place", "place_configure", "place_forget", "place_info",
    "place_slaves", "positionfrom", "propagate", "protocol", "quit",
    "register", "resizable", "rowconfigure", "selection_clear", "selection_get",
    "selection_handle", "selection_own", "selection_own_get", "send",
    "setvar", "size", "sizefrom", "slaves", "state", "title", "tk_bisque",
    "tk_focusFollowsMouse", "tk_focusNext", "tk_focusPrev", "tk_setPalette",
    "tk_strictMotif", "tkraise", "transient", "unbind", "unbind_all",
    "unbind_class", "update", "update_idletasks", "wait_variable",
    "wait_visibility", "wait_window", "waitvar", "winfo_atom", "winfo_children",
    "winfo_class", "winfo_exists", "winfo_geometry", "winfo_height", "winfo_id",
    "winfo_ismapped", "winfo_manager", "winfo_name", "winfo_parent",
    "winfo_pointerx", "winfo_pointery", "winfo_reqheight", "winfo_reqwidth",
    "winfo_rootx", "winfo_rooty", "winfo_screen", "winfo_screenheight",
    "winfo_screenwidth", "winfo_toplevel", "winfo_viewable", "winfo_width",
    "winfo_x", "winfo_y", "withdraw", "wm_attributes", "wm_geometry",
    "wm_iconbitmap", "wm_protocol", "wm_state", "wm_title",
}


def methods_in(path):
    found = set()
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return found
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not item.name.startswith("_"):
                        found.add(item.name)
    return found


reserved = set(TK_METHODS)
spec = importlib.util.find_spec("customtkinter")
if spec and spec.origin:
    root = os.path.dirname(spec.origin)
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".py"):
                reserved |= methods_in(os.path.join(folder, name))
check("toolkit method names collected", len(reserved) > 150, len(reserved))
check("state is among them - the one that bit", "state" in reserved)

# Attributes deliberately allowed to share a name with a method. Empty, and
# the exemption exists so a considered override is recorded here rather than
# by deleting the check.
ALLOWED = set()

WINDOW_BASES = {"CTk", "CTkToplevel", "Tk", "Toplevel", "Canvas",
                "CTkFrame", "CTkScrollableFrame"}


def window_classes(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                name = base.attr if isinstance(base, ast.Attribute) else \
                       (base.id if isinstance(base, ast.Name) else "")
                if name in WINDOW_BASES:
                    yield node
                    break


print("== no attribute may shadow a toolkit method ==")
checked, clashes = 0, []
for filename in ("edsmt.py", "overlay.py"):
    path = os.path.join(REPO, filename)
    if not os.path.exists(path):
        continue
    tree = ast.parse(open(path, encoding="utf-8").read())
    for cls in window_classes(tree):
        for node in ast.walk(cls):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"):
                        checked += 1
                        if target.attr in reserved and target.attr not in ALLOWED:
                            clashes.append("%s.%s (%s line %d)"
                                           % (cls.name, target.attr, filename,
                                              node.lineno))
check("assignments were actually inspected", checked > 10, checked)
check("none of them shadow a toolkit method", not clashes, clashes)

print("== the specific one that bit ==")
source = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
live = [l for l in source.splitlines()
        if "self.state" in l and not l.strip().startswith("#")]
check("nothing assigns self.state any more", not live, live)
check("the journal state has another name", "self.game" in source)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
