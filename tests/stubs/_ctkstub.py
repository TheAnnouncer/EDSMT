"""Fake tkinter and customtkinter, so edsmt.py imports and its real logic can
be exercised on a machine with no display and no Tk.

There is deliberately no matplotlib stub. The plan view is drawn on a plain
canvas and no plotting library is installed by requirements.txt, so importing
matplotlib here made the suite pass on a machine that happened to have it and
fail on a clean build box - which is exactly backwards.
"""
import sys, types

def _mod(name):
    m = types.ModuleType(name); sys.modules[name] = m; return m

class _Var:
    def __init__(self, value=None, **kw): self._v = value
    def get(self): return self._v
    def set(self, v): self._v = v

class _W:
    """Records everything so tests can assert on widget state."""
    def __init__(self, *a, **kw):
        self._kw = dict(kw); self._text = ""; self._values = list(kw.get("values", []))
        self._children = []
        self._var = kw.get("variable")
        self._touched = False
        self._placeholder = ""
        self._visible = False
        self._parent = a[0] if a else None
        if isinstance(self._parent, _W): self._parent._children.append(self)
    def __getattr__(self, name):
        def anything(*a, **kw): return None
        return anything
    # entry / combobox surface
    def get(self):
        if self._var is not None: return self._var.get()
        # Real customtkinter shows the class name until something sets a
        # value. The tests must see that, or they cannot catch the bug it
        # caused.
        if self._text == "" and not self._touched:
            return getattr(self, "_placeholder", "")
        return self._text
    def set(self, v):
        self._text = str(v); self._touched = True
        if self._var is not None: self._var.set(v)
    def insert(self, index, value):
        self._text = (self._text or "") + str(value); self._touched = True
    def delete(self, first, last=None):
        self._text = ""; self._touched = True
    def configure(self, **kw):
        self._kw.update(kw)
        if "values" in kw: self._values = list(kw["values"])
    def cget(self, k): return self._kw.get(k)
    def winfo_children(self): return list(self._children)
    def destroy(self):
        # Real Tk detaches the widget from its parent; the tests depend on
        # winfo_children() actually shrinking after a redraw.
        parent = getattr(self, "_parent", None)
        if isinstance(parent, _W) and self in parent._children:
            parent._children.remove(self)
        self._children = []
    # Real Tk's winfo_children() lists unpacked widgets too, so visibility
    # has to be tracked separately or a test cannot tell them apart.
    def pack(self, **kw): self._visible = True
    def grid(self, **kw): self._visible = True
    def place(self, **kw): self._visible = True
    def pack_forget(self): self._visible = False
    def grid_forget(self): self._visible = False
    def winfo_ismapped(self): return bool(getattr(self, "_visible", False))
    def bind(self, *a, **kw): return None
    def after(self, ms, fn=None, *a):
        return "after#1"
    def update(self): return None
    def clipboard_clear(self): return None
    def clipboard_append(self, t): self.clipboard = t

# ---- tkinter ----
tk = _mod("tkinter")
tk.Tk = _W; tk.Frame = _W; tk.Canvas = _W; tk.Toplevel = _W; tk.Widget = _W
tk.Label = _W
tk.StringVar = _Var; tk.BooleanVar = _Var; tk.IntVar = _Var; tk.DoubleVar = _Var
tk.Variable = _Var
tk.TclError = type("TclError", (Exception,), {})
tk.END = "end"
mb = _mod("tkinter.messagebox"); mb.showerror = lambda *a, **k: None
mb.showinfo = lambda *a, **k: None; mb.askyesno = lambda *a, **k: True
tk.messagebox = mb
_mod("tkinter.font").Font = _W
_mod("tkinter.ttk").Frame = _W
fd = _mod("tkinter.filedialog"); fd.askdirectory = lambda *a, **k: ""
tk.filedialog = fd

# ---- customtkinter ----
ctk = _mod("customtkinter")
ctk.__version__ = "6.0.0-stub"
class _Combo(_W):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._placeholder = "CTkComboBox"

for n in ("CTk", "CTkFrame", "CTkLabel", "CTkButton", "CTkEntry", "CTkComboBox",
          "CTkOptionMenu", "CTkCheckBox", "CTkScrollableFrame", "CTkTextbox",
          "CTkSwitch", "CTkTabview", "CTkToplevel", "CTkSegmentedButton",
          "CTkProgressBar", "CTkSlider", "CTkRadioButton", "CTkScrollbar",
          "CTkFont", "CTkImage", "CTkInputDialog"):
    setattr(ctk, n, type(n, (_W,), {}))
ctk.CTkComboBox = _Combo
ctk.StringVar = _Var; ctk.BooleanVar = _Var; ctk.IntVar = _Var; ctk.DoubleVar = _Var
ctk.set_appearance_mode = lambda *a, **k: None
ctk.set_default_color_theme = lambda *a, **k: None
ctk.set_widget_scaling = lambda *a, **k: None
