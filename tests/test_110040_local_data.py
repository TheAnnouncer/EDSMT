"""1.10040 (#217): the documented, read-only local data interface.

Other tools on the same PC read what EDSMT is doing from /state.json on the
streaming server (127.0.0.1 only). It carries a schema number and EDSMT's
version, every field is written up in docs/LOCAL-DATA.md, and nothing in it
is a position on a body or any of the community map's finds beyond what the
stream pages already show.

    python tests/test_110040_local_data.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import streamout as SO  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


state = SO.stream_state(cmdr="Jameson", system="Ega", body="Ega 1", mined={"Platinum": 40},
                        seconds=600, running=True, cr_hr=1000000, rigs_down=3, version="1.10040",
                        near=[{"range_m": 120.0, "bearing": 90.0,
                               "deposit": {"commodity": "Platinum", "lat": 1.0, "lon": 2.0}}])
print("== a schema and a version ==")
check("schema 1", state.get("schema") == SO.SCHEMA == 1, state.get("schema"))
check("EDSMT's version", state.get("version") == "1.10040")
check("an empty state carries them too", SO.stream_state().get("schema") == 1
      and "version" in SO.stream_state())
text = json.dumps(state)
check("no position on a body anywhere in it", '"lat"' not in text and '"lon"' not in text
      and "latitude" not in text.lower())

print("== every field written up ==")
doc_path = os.path.join(REPO, "docs", "LOCAL-DATA.md")
check("docs/LOCAL-DATA.md is there", os.path.isfile(doc_path))
doc = open(doc_path, encoding="utf-8").read() if os.path.isfile(doc_path) else ""
named = set(re.findall(r"`([a-z_]+)`", doc))


def keys(value, prefix=""):
    out = []
    if isinstance(value, dict):
        for key, inner in value.items():
            out.append(key)
            out += keys(inner, key + ".")
    elif isinstance(value, list) and value:
        out += keys(value[0], prefix)
    return out


fields = set(keys(state)) | set(keys(dict(state, last_find={"commodity": "", "amount": "", "rigs": 0,
                                                             "where": "", "ago_s": 0, "ago": ""})))
missing = sorted(f for f in fields if f not in named)
check("every field in /state.json is in the document", not missing, missing)
check("the document says how the schema changes, where it is, and that it is read-only",
      "schema" in doc and "127.0.0.1" in doc and "/state.json" in doc and "read-only" in doc.lower())
# The words are built from parts so that this file does not name them either.
_PRIVATE = "|".join(("EDSMT" + "-Private", "RUN" + "BOOK", "DEV" + "LOG", "BACK" + "LOG", "the " + "owner"))
check("and names nothing private", not re.search(_PRIVATE, doc))
guide = open(os.path.join(REPO, "docs", "GUIDE.md"), encoding="utf-8").read()
check("the guide points to it", "LOCAL-DATA.md" in guide)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
