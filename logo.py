"""The EDSMT logo (1.10040): which picture of the badge suits a screen's
scaling, and which file a window wears as its icon on each system.

The badge comes in two sizes, 256 and 512 pixels, round with clear corners.
A window shows the smaller one shrunk wherever that is enough and the larger
one on a high-DPI scaling, so it is never blown up. Windows wears edsmt.ico
(16 to 256 pixels) through iconbitmap, with the older Radio Raxxla icon kept
only for when edsmt.ico is missing; Linux has no use for an .ico and takes
the badge itself through iconphoto.
"""
import os

BADGE_SMALL = "edsmt-badge-256.png"
BADGE_LARGE = "edsmt-badge-512.png"
SMALL_PX = 256
ICON = "edsmt.ico"
OLD_ICON = "radioraxxla.ico"
# How big the badge is drawn, in the window's own pixels before scaling.
WELCOME_PX = 160
ABOUT_PX = 96


def badge_file(px, scaling=1.0):
    """The badge file for one drawn `px` across at `scaling`: the 256 file
    while that is enough, the 512 once the screen needs more pixels."""
    try:
        need = float(px) * float(scaling)
    except (TypeError, ValueError):
        need = float(px)
    return BADGE_SMALL if need <= SMALL_PX else BADGE_LARGE


def icon_choices(folder, platform, exists=os.path.isfile):
    """[(how, path)] to try, best first, of the files that are there: "bitmap"
    for iconbitmap, "photo" for iconphoto. `folder` is where the app's files
    are - edsmt.ico beside it, the badge in images/ under it."""
    if str(platform).startswith("win"):
        wanted = [("bitmap", os.path.join(folder, ICON)),
                  ("bitmap", os.path.join(folder, OLD_ICON))]
    else:
        wanted = [("photo", os.path.join(folder, "images", BADGE_SMALL))]
    return [(how, path) for how, path in wanted if exists(path)]
