"""Share my week (1.10040): your week on the surface as a card.

The community map draws one card a week for every commander who shares -
finds, sites, best patch, furthest from Sol, place on the board, ribbons
earned - in the weekly update's style. This fetches yours, saves it in the
pictures folder and hands back the path for the app to open. The name is
the journal's commander name, as the map knows it; never typed.

Plain functions; the app's worker runs fetch_job off the UI thread.
"""
import os
import re
import time
import urllib.parse

import edonline as EDO

TAG = "weekcard"
HOME = EDO.HOME_URL


def _name(cmdr):
    return " ".join(str(cmdr or "").split())


def card_url(cmdr, current=True):
    """The card's address: this week so far, or the last complete week."""
    name = _name(cmdr)
    if not name:
        return ""
    return "%s/v1/public/cmdrs/%s/week.png%s" % (HOME, urllib.parse.quote(name, safe=""),
                                                 "?current=1" if current else "")


def page_url(cmdr, current=True):
    """The page to share: the card, the words, a link to the picture."""
    name = _name(cmdr)
    if not name:
        return ""
    return "%s/weekly/cmdr?cmdr=%s%s" % (HOME, urllib.parse.quote(name, safe=""),
                                         "&current=1" if current else "")


def picture_name(cmdr, when=None):
    """week_<commander>_<yyyymmdd-hhmm>.png - the shape tidy_pictures keeps."""
    slug = re.sub(r"[^a-z0-9]+", "_", _name(cmdr).lower()).strip("_") or "cmdr"
    stamp = time.strftime("%Y%m%d-%H%M", time.gmtime(when if when is not None else time.time()))
    return "week_%s_%s.png" % (slug[:40], stamp)


def explain(message):
    """Why the card did not come, in plain words."""
    text = str(message or "")
    if "404" in text:
        return "You are not on the map yet - share a find and the card is yours."
    if text.lower().startswith("no connection") or "could not reach" in text.lower():
        return "The community map cannot be reached for the card right now."
    return "The card could not be fetched: %s" % text


def fetch_job(cmdr, folder, getter=None, now=None):
    """A callable for the worker: fetches the card and saves it, answering
    the path. Anything that is not a PNG is refused, not written."""
    url = card_url(cmdr)
    path = os.path.join(folder, picture_name(cmdr, now))
    get = getter or EDO.get_bytes

    def job():
        data = get(url, timeout=30.0)
        if not data[:8] == b"\x89PNG\r\n\x1a\n":
            raise RuntimeError("the map sent something that is not a picture")
        os.makedirs(folder, exist_ok=True)
        temp = path + ".tmp"
        with open(temp, "wb") as handle:
            handle.write(data)
        os.replace(temp, path)
        return path
    return job
