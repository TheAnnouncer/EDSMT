"""
Your own Discord channels (1.10040, #315): up to five webhooks.

Each one is a row of the settings list "discord_webhooks":

    {"name": "Radio Raxxla", "url": "https://discord.com/api/webhooks/...",
     "finds": False, "sessions": True, "map": True, "card": False}

    finds     every find you mark, one message each
    sessions  one summary when a Rhino session ends, edited after the sale
    map       the map picture sent with that summary
    card      the session card (sessioncard.py) sent with it too (1.10040)

A row saved before a switch existed takes a new row's setting for it, so an
older settings file reads the same as it did.

A post goes to every row with its kind switched on. A webhook address is a
password for its channel: the app keeps it behind dots, and a row is known
everywhere else by its name, or by hook_key() - never by its address.

Every find also reaches the Radio Raxxla Discord through the community map.
That channel's webhook lives on the server and is never in the app.

Plain data, no Tk and no network, so all of it is checked without a display.
"""

import hashlib

MAX_HOOKS = 5
KINDS = ("finds", "sessions", "map", "card")
# A new row: the session summary with its map, not every find - a post per
# find was a channel nobody could read (1.10035). The card is asked for.
NEW_ROW = {"finds": False, "sessions": True, "map": True, "card": False}
# The one webhook a settings file from before 1.10040 had becomes this.
UPGRADED_NAME = "My Discord"
# Where that file kept it, and its switches. Gone once it is a list.
OLD_KEYS = ("discord_webhook", "discord_post_finds", "discord_post_sessions",
            "discord_attach_map", "discord_finds_level")


def default_name(number):
    """The name of a row left blank: Discord 1, Discord 2 and so on."""
    return "Discord %d" % int(number)


def entry(name="", url="", **switches):
    """One row with every key there; a switch not given is a new row's."""
    out = {"name": str(name or "").strip(), "url": str(url or "").strip()}
    for kind in KINDS:
        out[kind] = bool(switches.get(kind, NEW_ROW[kind]))
    return out


def clean(rows):
    """The list as the app uses it: rows that are dicts, every key in each,
    a name on each ("Discord N" when it was left blank), at most MAX_HOOKS."""
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        item = entry(row.get("name"), row.get("url"),
                     **{kind: row.get(kind, NEW_ROW[kind]) for kind in KINDS})
        if not item["name"]:
            item["name"] = default_name(len(out) + 1)
        out.append(item)
        if len(out) >= MAX_HOOKS:
            break
    return out


def old_address(saved):
    """The single webhook a file from before 1.10040 holds and upgrade()
    makes the first row of; "" for a file that has the list already, or
    never had one."""
    saved = saved or {}
    if isinstance(saved.get("discord_webhooks"), list):
        return ""
    return str(saved.get("discord_webhook") or "").strip()


def upgrade(merged, saved):
    """The single webhook of a file from before 1.10040 as one row named
    "My Discord", with the switches it had - so everything it posted keeps
    posting - and the old keys gone. A file that already has the list keeps
    it as it is; one that never had a webhook gets an empty list.

    1.10034 posted every find by default and wrote that default into the
    file, so 1.10035 turned per-find posts off once for any file it had not
    seen yet (discord_finds_level). That still holds here."""
    saved = saved or {}
    if not isinstance(saved.get("discord_webhooks"), list):
        url = old_address(saved)
        rows = []
        if url:
            try:
                level = int(saved.get("discord_finds_level") or 0)
            except (TypeError, ValueError):
                level = 0
            rows.append(entry(UPGRADED_NAME, url,
                              finds=level >= 1 and bool(saved.get("discord_post_finds", False)),
                              sessions=saved.get("discord_post_sessions", True),
                              map=saved.get("discord_attach_map", True)))
        merged["discord_webhooks"] = rows
    for key in OLD_KEYS:
        merged.pop(key, None)
    return merged


def wanted(rows, kind, valid):
    """The rows a post of `kind` goes to: that switch on, and an address
    `valid` (the app's own webhook test) takes. A blank or broken address
    posts nothing - the Settings window says so when it is saved."""
    return [row for row in clean(rows)
            if row.get(kind) and row["url"] and valid(row["url"])]


def hook_key(url):
    """A short name for one webhook that is not its address. The Discord
    message each session was posted as is kept under it, so an edit only
    ever goes to the channel that holds that message - and the address is
    never written down beside it."""
    text = str(url or "").strip().rstrip("/")
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
