# The FOLDER build - this is what goes inside the installer.
#
# Two specs, two jobs, and the difference matters:
#   EDSMT-onefile.spec  -> dist\EDSMT.exe        the portable download
#   EDSMT.spec (this)   -> dist\EDSMT\...        what the installer packages
#
# A onefile exe unpacks itself to a temp folder on every single launch. That
# is the right trade for a download somebody saves to their desktop - one
# file, nothing to keep together. It is the wrong trade once an installer is
# involved, because the installer already put a folder somewhere tidy, so
# paying the unpack cost on every launch buys nothing.
#
#   pyinstaller build/EDSMT.spec --noconfirm

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Relative paths in a spec resolve against the SPEC FILE's folder, not the
# project root - and this spec lives in build/. Anchoring on SPECPATH removes
# the whole class of bug.
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICON = os.path.join(ROOT, "radioraxxla.ico")

datas = collect_data_files("customtkinter")
datas += [(ICON, ".")]
# The rig warning sounds. A folder of their own inside the bundle, found
# at run time through sys._MEIPASS like the icon.
datas += [(os.path.join(ROOT, "sounds", name), "sounds")
          for name in ("rig-warning.wav", "rig-warning-profane.wav")]

hiddenimports = collect_submodules("customtkinter")
hiddenimports += ["survey", "planview", "journal", "edonline", "overlay"]

excludes = [
    "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
    "IPython", "jupyter", "notebook", "nbconvert", "tornado",
    "scipy", "sympy", "pytest", "sphinx", "docutils",
    # not aboard: the plan view needs neither
    "matplotlib", "numpy", "pandas",
    # the server and the test harness have no business in the installer
    "fastapi", "uvicorn", "pydantic", "httpx", "tests", "_ctkstub",
]

a = Analysis([os.path.join(ROOT, "edsmt.py")], pathex=[ROOT],
             binaries=[], datas=datas,
             hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
             excludes=excludes, noarchive=False,
             # 2 = no docstrings and no asserts in the shipped bytecode.
             # The docstrings explain how this was built and why; they
             # are for the source, not for every PC it is installed on.
             # The app is checked to run this way before every release.
             optimize=2)

pyz = PYZ(a.pure)

exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name="EDSMT", debug=False, strip=False, upx=False,
          console=False, icon=ICON,
          version=os.path.join(SPECPATH, "version_info.txt"))

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="EDSMT")
