# EDSMT's local data: /state.json

Other tools on your own PC - a stream overlay, a Stream Deck button, a
dashboard - can read what EDSMT is doing from one small JSON document. It
is read-only: EDSMT never reads anything back from it, and nothing written
to it changes EDSMT.

## Where it is

    http://127.0.0.1:<port>/state.json

It is served by EDSMT's streaming server, on this PC only (`127.0.0.1`,
never the network), while **Settings > Overlay > Streaming > Serve an OBS
browser source on this PC** is on. The port is the one set there (8765 to
start with). Ask for it as often as once a second; it is worked out fresh
each time.

## What is in it

What the stream pages show, and nothing more. No position on a body
(latitude, longitude) is ever in it. In streamer mode, the system and body
names are hidden in it exactly as they are on screen.

| Field | What it is |
|---|---|
| `app` | Always "EDSMT". |
| `schema` | The shape of this document, 1 for now (see below). |
| `version` | EDSMT's version, as in its title bar. |
| `cmdr` | Your commander's name, from the journal. |
| `system` | The system the session is in (or you are in), as streamer mode allows. |
| `body` | The body, the same way. |
| `session` | The Rhino session: `running` and `paused` (true or false), `seconds` so far and `clock` as text. |
| `tonnes` | What the session has brought up, a list of `commodity` and `tonnes`, most first. |
| `tonnes_total` | All of it added up. |
| `mining` | The commodities being mined, most first (the first few). |
| `cr_hr` | Credits an hour for the session, a whole number; `cr_hr_text` is the same with thousands separators. |
| `merits` | Powerplay merits from the session, or null. `merits_estimated` is true when that figure is worked out rather than read. |
| `rigs_down` | How many of your rigs are down. |
| `nearest` | The nearest deposit not worked out, or null: `commodity`, `distance_m` and `distance` as text, `bearing` in degrees and `compass`. |
| `last_find` | Your newest find, or null: `commodity`, `amount`, `rigs`, `where`, `ago_s` (seconds) and `ago` as text. |
| `colours` | The theme's colours by name, for a page to match EDSMT: `orange`, `amber`, `text`, `dim`, `void`, `green`, `red` and `cyan`, each as #rrggbb. |
| `updated` | When this answer was made, UTC. |

## The schema number

`schema` changes only when a field changes meaning or goes away. A field
added keeps the same number, so a tool should ignore fields it does not
know. Check `schema` before relying on the rest; a tool written for 1 should
stop when it sees 2.
