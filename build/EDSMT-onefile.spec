# One file. The whole program in a single EDSMT.exe.
#
# This is the download people actually get: click the link, run the file.
# No zip to extract, no installer to approve, no folder of DLLs to keep
# together - which is where non-technical commanders lose the thread.
#
# A onefile build unpacks itself to a temp folder on every launch, so it
# starts slower than a folder build. That cost used to be about ten seconds
# because a plotting library and a dataframe library were aboard. Neither is
# any more, so it is a second or two, which is worth paying to make the
# download a single file.
#
#   pyinstaller build/EDSMT-onefile.spec --noconfirm

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICON = os.path.join(ROOT, "radioraxxla.ico")

datas = collect_data_files("customtkinter")
datas += [(ICON, ".")]
# The rig warning sounds. A folder of their own inside the bundle, found
# at run time through sys._MEIPASS like the icon.
datas += [(os.path.join(ROOT, "sounds", name), "sounds")
          for name in ("rig-warning.wav", "rig-warning-profane.wav")]
# The Rhino on the first-run window and in Settings > About.
datas += [(os.path.join(ROOT, "images", name), "images")
          for name in ("rhino-banner.png", "rhino-about.png")]

hiddenimports = collect_submodules("customtkinter")
hiddenimports += ["survey", "planview", "journal", "edonline", "overlay",
                  "rigplan", "bodybook", "mapimage", "shiphold",
                  "sessionledger", "supportbundle",
                  "chattags", "inputdev", "inputmix"]
# Guided survey and the pointers (1.10035): the window imports both.
hiddenimports += ["waypoints", "guidance"]
# Map pictures (1.10035) are drawn with Pillow. It is imported inside
# functions, so name it: a build that left it out would still start, and
# every picture button would then say the library is missing.
hiddenimports += ["PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont"]

excludes = [
    "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
    "IPython", "jupyter", "notebook", "nbconvert", "tornado",
    "scipy", "sympy", "pytest", "sphinx", "docutils",
    "matplotlib", "numpy", "pandas",
    "fastapi", "uvicorn", "pydantic", "httpx", "tests", "_ctkstub",
]

# 1.10035: the Find filters and the Powerplay record.
hiddenimports += ["finder", "powerplay", "sellplan", "board", "crowd", "presale", "gamebinds", "galaxy"]

# 1.10035: importing from other tools, depleted marks and regrowth, the bin
# and favourites, and the map filters.
hiddenimports += ["importers", "regrowth", "sitebook", "markerfilter"]
# 1.10038: which mining location you are in, without targeting it.
hiddenimports += ["zone"]
# 1.10039: the shape of an overlay box - a keystone and a bend.
hiddenimports += ["warp"]
# 1.10039: the game's own HUD colours as a theme.
hiddenimports += ["gametheme"]
# 1.10039: the same spec builds the Linux file (dist/EDSMT, no extension).
# The work keys there go through python-xlib, imported inside a function
# and loading its keysym tables by name, so the whole package is named.
# Windows gets none of this, and its build is the same as before.
LINUX = sys.platform.startswith("linux")
if LINUX:
    hiddenimports += ["x11keys"] + collect_submodules("Xlib")

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

# The .ico and the version resource are Windows things; on Linux neither
# applies, so neither is asked for.
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name="EDSMT", debug=False, strip=False, upx=False,
          runtime_tmpdir=None, console=False,
          icon=None if LINUX else ICON,
          version=None if LINUX else os.path.join(SPECPATH, "version_info.txt"))
