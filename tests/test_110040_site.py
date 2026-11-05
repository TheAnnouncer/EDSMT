"""1.10040: radioraxxla.com/EDSMT/ looks like the rest of radioraxxla.com.

The page wears the site's own header, status strip and footer (the ones the
other pages carry, from the site's stylesheet and scripts), says Windows and
Linux, carries the weekly update from the community map, points at the
Discord channels the map posts to, and links nowhere outside Radio Raxxla's
own sites and the services it names.

    python tests/test_110040_site.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
page = io.open(os.path.join(REPO, "site", "index.html"), encoding="utf-8").read()

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


def block(start, end):
    i = page.find(start)
    j = page.find(end, i)
    return page[i:j + len(end)] if i >= 0 and j >= 0 else ""


print("== the site's own header ==")
head = block('<header class="site-head">', "</header>")
links = re.findall(r'<a class="link" href="([^"]+)"', head)
check("the same main menu as every other page, in the same order",
      links == ["/", "/squadron.html", "/systems.html", "/map.html", "/frequency.html",
                "/music.html", "/streamers.html", "/news.html", "/tools.html",
                "/merch.html", "/comms.html"], links)
check("EDSMT sits under Tools", 'href="/tools.html" aria-current="page"' in head)
check("with the on-air strip the site's script fills", 'data-np="station"' in head
      and "data-stardate" in head and "data-galaxy" in head)
check("stylesheet and scripts are the site's, at one version",
      len(set(re.findall(r'(?:raxxla\.css|raxxla\.js|config\.js)\?v=([\d.]+)', page))) == 1
      and "raxxla.css?v=2026.10.01.1" not in page)

print("== the site's own footer ==")
foot = block('<footer class="site-foot">', "</footer>")
labels = re.findall(r'<span class="label">([^<]+)</span>', foot)
check("Listen, Support and Site columns, as on the other pages", labels == ["Listen", "Support", "Site"],
      labels)
check("PayPal and Discord filled in by the site's config", 'data-link="paypal"' in foot
      and 'data-link="discord"' in foot)
# The site's footer has a line linking a personal site; the EDSMT page leaves it out.
check("the footer's personal-site line is left out", 'From <a href="https://www.the' not in page)
check("the not-affiliated line", "Not affiliated with Frontier Developments plc" in foot)

print("== what the page says ==")
check("Windows and Linux", re.search(r"Free &middot; Windows and Linux &middot;", page))
check("a Linux download that goes to the release page",
      "github.com/TheAnnouncer/EDSMT/releases/latest" in page and "Linux" in block('<div class="ctas">', "</div>"))
check("Linux in the system requirements", re.search(r'<span class="k">Linux</span>', page))
check("cloud desktops named, game-only streaming services said plainly",
      "Maximum Settings" in page and "GeForce NOW" in page)
outside_notes = page.replace(block('<section class="section" id="whatsnew">', "</section>"), "")
check("every find carries the CMDR name - never 'your choice' (the patch notes may quote the old line)",
      "your choice" not in outside_notes.lower() and "anonymous" not in outside_notes.lower())

print("== the weekly update ==")
weekly = block('<section class="section" id="weekly">', "</section>")
check("a weekly section", bool(weekly))
check("read from the site's own copy, so the site's content policy allows it",
      "fetch('weekly.json'" in page or 'fetch("weekly.json"' in page)
check("with the whole page one click away", "https://edsmt.radioraxxla.com/weekly" in weekly)
check("and the Discord channels the map posts to", "#edsmt-finds" in weekly and "#edsmt-weekly" in weekly
      and "discord.gg/DjH9uZabet" in weekly)
check("it says something sensible before the numbers arrive", "data-weekly" in weekly
      and "Loading" not in weekly)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
