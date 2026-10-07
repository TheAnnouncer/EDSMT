"""UK English, everywhere a commander reads it.

Asked for in these words: "All UK english spellings as well."

Checked: every string in the program that is a phrase (it has a space in
it), and the prose of the README, the patch notes, the security notes, the
contributing notes, the journal notes and the two web pages. A one-word
string is left alone - "center" is a Tk anchor, "meters" is a spelling the
distance box accepts, "Authorization" is the name of an HTTP header - and
so is the CSS inside the pages, which is a language with its own spelling.
"""
import io, os, re, sys, tokenize, ast

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


# US spelling -> what it is in UK English. Whole words only, any case.
US = {
    r"colou?r(s|ed|ing|ful)?": None,          # checked separately below
    r"center(s|ed|ing)?": "centre",
    r"(kilo)?meters?": "metre",
    r"gray": "grey",
    r"behavior(s|al)?": "behaviour",
    r"favorite(s)?": "favourite",
    r"honor(s|ed)?": "honour",
    r"neighbor(s|ing|hood)?": "neighbour",
    r"armor(ed)?": "armour",
    r"vapor": "vapour",
    r"maneuver(s|ed|ing)?": "manoeuvre",
    r"toward": "towards",
    r"afterward": "afterwards",
    r"judgment": "judgement",
    r"catalog(s|ed)?": "catalogue",
    r"dialog(s)?": "dialogue",
    r"traveled|traveling|traveler(s)?": "travelled",
    r"canceled|canceling": "cancelled",
    r"labeled|labeling": "labelled",
    r"modeled|modeling": "modelled",
    r"fulfill": "fulfil",
    r"defense|offense": "defence",
    r"aluminum": "aluminium",
    r"(organ|recogn|real|analy|custom|minim|maxim|priorit|summar|apolog|"
    r"final|categor|visual|util|optim|initial|synchron|author|normal|"
    r"special|emphas|standard|memor|capital|character|critic|familiar|"
    r"general|symbol|legal|stabil|neutral|central|local|personal|"
    r"formal|global|serial|sanit|random)iz(e|es|ed|ing|ation|ations)": "-ise",
    r"analyz(e|es|ed|ing)": "analyse",
}
PATTERN = re.compile(r"\b(" + "|".join(k for k in US if US[k]) + r")\b", re.I)
COLOR = re.compile(r"\bcolor(s|ed|ing|ful)?\b", re.I)


def offenders(text):
    return sorted({m.group(0) for m in PATTERN.finditer(text)} |
                  {m.group(0) for m in COLOR.finditer(text)})


print("== the words the program shows ==")
SOURCES = ["edsmt.py", "overlay.py", "journal.py", "survey.py", "edonline.py",
           "planview.py", "rigplan.py"]
# Anything else to hold to the same spelling, as full paths separated by
# os.pathsep - how the checks kept beside the API's source use this list.
SOURCES += [p for p in os.environ.get("EDSMT_SPELL_EXTRA", "").split(os.pathsep) if p]
for name in SOURCES:
    path = os.path.join(REPO, name)
    found = []
    with io.open(path, encoding="utf-8") as fh:
        source = fh.read()
    # The HTML page the server builds carries its own CSS, which spells it
    # "color" and "center" because that is CSS.
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.STRING:
            continue
        try:
            value = ast.literal_eval(token.string)
        except Exception:
            continue
        if not isinstance(value, str) or " " not in value.strip():
            continue
        if "{" in value and ";" in value and ":" in value:
            continue                        # a block of CSS
        bad = offenders(value)
        if bad:
            found.append("line %d: %s" % (token.start[0], ", ".join(bad)))
    check("%s says it in UK English" % name, not found, found[:6])


print("== the documents ==")
DOCS = ["README.md", "CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md",
        "JOURNAL-NOTES.md", os.path.join("docs", "SURFACE-MINING-JOURNAL.md")]
for name in DOCS:
    path = os.path.join(REPO, name)
    if not os.path.exists(path):
        continue
    with io.open(path, encoding="utf-8") as fh:
        text = fh.read()
    # Code spans and fences are names and values, not prose.
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", " ", text)
    bad = offenders(text)
    check("%s is UK English" % name, not bad, bad)

for name in ("index.html", "edsmt.html"):
    path = os.path.join(REPO, "site", name)
    with io.open(path, encoding="utf-8") as fh:
        page = fh.read()
    page = re.sub(r"<style.*?</style>", " ", page, flags=re.S | re.I)
    page = re.sub(r"<script.*?</script>", " ", page, flags=re.S | re.I)
    page = re.sub(r"<[^>]+>", " ", page)                # tags and attributes
    bad = offenders(page)
    check("site/%s reads in UK English" % name, not bad, bad)

print("== and the checker catches what it is for ==")
check("it would catch 'Pick a color'", offenders("Pick a color") == ["color"])
check("and 'centered on the signal'", offenders("centered on the signal") == ["centered"])
check("and 'organize your finds'", offenders("organize your finds") == ["organize"])
check("but not 'colour', 'centre', 'metres' or 'size'",
      offenders("colour centre metres size resize") == [])

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
