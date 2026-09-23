"""Check every customtkinter call against the installed library's source.

This is a static check on purpose. The app cannot be started here - there is
no display and no Tkinter - so the only way to know a widget call is valid
before a commander double-clicks the exe is to read the library's own
signatures and compare.

It exists because `bind_all` shipped once. customtkinter raises on it by
design, so the app died on launch with a traceback that named the library
rather than the line that called it. A second class of the same bug is an
argument that simply is not a parameter of that widget: Tk swallows some and
raises on others, and which is which is not obvious from the outside.

Skipped, not failed, if customtkinter is not installed - the rest of the
suite still means something on a machine that has never had it.
"""
import ast, os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

spec = importlib.util.find_spec("customtkinter")
if spec is None or not spec.origin:
    print("  SKIP  customtkinter is not installed here")
    raise SystemExit(0)

CTK_ROOT = os.path.dirname(spec.origin)

# Validate against the library that SHIPS, not whatever is installed here.
# For a while this read customtkinter 6.0.0 while requirements.txt pinned
# below 6 - so every call was checked against a version no user ever ran.
import re as _re
try:
    import importlib.metadata as _meta
    _have = _meta.version("customtkinter")
except Exception:
    _have = ""
_pin = open(os.path.join(REPO, "requirements.txt"), encoding="utf-8").read()
_lo = _re.search(r"customtkinter>=([\d.]+)", _pin)
_hi = _re.search(r"customtkinter[^\n]*<([\d.]+)", _pin)
def _v(t): return tuple(int(x) for x in _re.findall(r"\d+", t)[:3])
check("the customtkinter checked against is the version that ships (%s)" % _have,
      bool(_have) and (not _lo or _v(_have) >= _v(_lo.group(1)))
      and (not _hi or _v(_have) < _v(_hi.group(1))),
      "requirements.txt says %s" % (_pin.strip().splitlines()[-1]))

# ---- read every CTk* class's __init__ out of the library's own source ----
signatures = {}      # class name -> set of accepted keyword names, or None
                     # for a class whose __init__ takes **kwargs
defined = {}         # class name -> {method: True if it only ever raises}
bases = {}           # class name -> the CTk classes it inherits from

for dirpath, _dirs, files in os.walk(CTK_ROOT):
    for name in files:
        if not name.endswith(".py"):
            continue
        path = os.path.join(dirpath, name)
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not node.name.startswith("CTk"):
                continue
            bases[node.name] = [b.id for b in node.bases if isinstance(b, ast.Name)]
            for item in node.body:
                if not isinstance(item, ast.FunctionDef):
                    continue
                if item.name == "__init__":
                    args = item.args
                    names = {a.arg for a in list(args.args) + list(args.kwonlyargs)}
                    names.discard("self")
                    signatures[node.name] = None if args.kwarg else names
                    continue
                # A method you must not call is one whose body is nothing but
                # a raise. A guarded raise inside an "if" is not that: every
                # concrete widget overrides CTkBaseClass.bind with a real one
                # that only raises on a bad argument, and treating those as
                # forbidden makes the check cry wolf on ordinary code.
                body = [st for st in item.body
                        if not (isinstance(st, ast.Expr)
                                and isinstance(st.value, ast.Constant))]
                only_raises = bool(body) and all(isinstance(st, ast.Raise)
                                                 for st in body)
                defined.setdefault(node.name, {})[item.name] = only_raises


def refuses(class_name, method, seen=None):
    """Does this class refuse that method?

    Whichever class defines it first wins, walking up the bases - which is
    the whole point: CTkBaseClass.bind raises, and almost every widget
    overrides it with one that works.
    """
    seen = seen or set()
    if class_name in seen or class_name not in defined and class_name not in bases:
        return False
    seen.add(class_name)
    own = defined.get(class_name, {})
    if method in own:
        return own[method]
    for base in bases.get(class_name, []):
        if base.startswith("CTk"):
            if refuses(base, method, seen):
                return True
    return False


CANDIDATES = sorted({m for methods in defined.values() for m in methods})

check("the library's classes were read", len(signatures) > 10, len(signatures))
check("CTk is among them", "CTk" in signatures)
check("bind_all is refused, as it always has been",
      refuses("CTkBaseClass", "bind_all"))
check("but an ordinary widget's own bind is not",
      not refuses("CTkComboBox", "bind") and not refuses("CTkButton", "bind"))
check("and a widget that really does refuse bind is still caught",
      refuses("CTkSegmentedButton", "bind"))

# ---- now every ctk.CTk* call and every widget method call in our source ----
APP_FILES = ["edsmt.py"]
bad_kwargs, bad_methods = [], []

for filename in APP_FILES:
    src = open(os.path.join(REPO, filename), encoding="utf-8").read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # ctk.CTkButton(...) style construction
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == "ctk" and func.attr.startswith("CTk"):
            accepted = signatures.get(func.attr, "unknown")
            if accepted == "unknown":
                bad_kwargs.append("%s:%d %s is not a customtkinter class"
                                  % (filename, node.lineno, func.attr))
            elif accepted is not None:
                for kw in node.keywords:
                    if kw.arg and kw.arg not in accepted:
                        bad_kwargs.append("%s:%d %s(%s=...) is not a parameter"
                                          % (filename, node.lineno, func.attr, kw.arg))
    # Which names in this file actually hold a customtkinter widget. Without
    # this the check fires on every plain Tk canvas .bind() in the file -
    # tk.Canvas binds perfectly well, it is the CTk widgets that refuse.
    ctk_locals = {}      # our name -> the customtkinter class it holds
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            f = node.value.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                    and f.value.id == "ctk":
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        ctk_locals[target.id] = f.attr
                    elif isinstance(target, ast.Attribute):
                        ctk_locals[ast.unparse(target)] = f.attr

    # ...and "self" inside a class that subclasses one.
    ctk_classes = {}     # our class -> the customtkinter class it extends
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) \
                        and base.value.id == "ctk":
                    ctk_classes[node.name] = base.attr

    def flag(node, receiver, ctk_class, where):
        method = node.func.attr
        if method in CANDIDATES and method != "__init__" \
                and refuses(ctk_class, method):
            bad_methods.append("%s:%d %s.%s() - %s refuses that%s"
                               % (filename, node.lineno, receiver, method,
                                  ctk_class, where))

    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
                and n.name in ctk_classes]:
        for node in ast.walk(cls):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == "self":
                flag(node, "self", ctk_classes[cls.name],
                     " (this class IS a %s)" % ctk_classes[cls.name])

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            try:
                receiver = ast.unparse(node.func.value)
            except Exception:
                continue
            if receiver in ctk_locals:
                flag(node, receiver, ctk_locals[receiver], "")

check("every ctk.CTk* class exists in the installed library",
      not [b for b in bad_kwargs if "is not a customtkinter class" in b],
      bad_kwargs)
check("every keyword passed to a widget is one it accepts",
      not [b for b in bad_kwargs if "is not a parameter" in b], bad_kwargs)
check("nothing calls a method customtkinter refuses",
      not bad_methods, bad_methods)
check("bind_all in particular is not used anywhere",
      "bind_all" not in open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read())

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
