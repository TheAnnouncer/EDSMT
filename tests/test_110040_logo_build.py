"""1.10040: the new EDSMT logo is the app's icon everywhere a build puts one.

The badge (images/edsmt-badge-256.png and -512.png) and the Windows icon
(edsmt.ico) ship in both builds; the .exe, the installer and the website's
favicon wear edsmt.ico; radioraxxla.ico ships as the fallback the window
uses if the new icon is missing.

    python tests/test_110040_logo_build.py
"""
import io
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


def read(*parts):
    return io.open(os.path.join(REPO, *parts), encoding="utf-8").read()


print("== the files ==")
ico = open(os.path.join(REPO, "edsmt.ico"), "rb").read()
reserved, kind, count = struct.unpack("<HHH", ico[:6])
sizes = sorted({(ico[6 + 16 * i] or 256) for i in range(count)})
check("edsmt.ico is a Windows icon from 16 to 256 px", reserved == 0 and kind == 1
      and {16, 32, 48, 256} <= set(sizes), sizes)
for size in (256, 512):
    data = open(os.path.join(REPO, "images", "edsmt-badge-%d.png" % size), "rb").read()
    w, h = struct.unpack(">II", data[16:24])
    check("images/edsmt-badge-%d.png is a %d px PNG with transparency" % (size, size),
          data[:8] == b"\x89PNG\r\n\x1a\n" and (w, h) == (size, size) and data[25] == 6, (w, h, data[25]))
check("the old icon is still there as the fallback", os.path.isfile(os.path.join(REPO, "radioraxxla.ico")))

print("== both builds ==")
for spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
    text = read("build", spec)
    check("%s: the .exe wears edsmt.ico" % spec, re.search(r'ICON = os\.path\.join\(ROOT, "edsmt\.ico"\)', text))
    check("%s: ships the fallback icon too" % spec, '"radioraxxla.ico"' in text)
    check("%s: ships the badge in both sizes" % spec,
          '"edsmt-badge-256.png"' in text and '"edsmt-badge-512.png"' in text)
    check("%s: the new modules are listed" % spec,
          all('"%s"' % m in text for m in ("welcome", "logo", "hubmanifest", "tabstrip", "uichrome",
                                           "webhooks", "streamer")))
check("the installer wears edsmt.ico", "SetupIconFile=..\\edsmt.ico" in read("build", "installer.iss"))
check("the website's favicon is the new icon", 'copy /y "edsmt.ico" "upload\\favicon.ico"' in read("BUILD.bat"))

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
