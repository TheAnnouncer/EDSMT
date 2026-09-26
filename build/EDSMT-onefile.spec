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
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

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
    "matplotlib", "numpy", "pandas",
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

exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name="EDSMT", debug=False, strip=False, upx=False,
          runtime_tmpdir=None, console=False, icon=ICON,
          version=os.path.join(SPECPATH, "version_info.txt"))
