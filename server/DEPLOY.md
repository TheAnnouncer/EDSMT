# Running the EDSMT community API

The API is a small FastAPI app over one SQLite file. EDSMT ships pointing at
the Radio Raxxla instance, `https://api.radioraxxla.com`, so nobody needs to
run their own. This is for anyone who wants to — a squadron, an expedition,
or somebody who would rather keep their finds on their own machine.

Every name in here — the folder, the container, the network — is an example.
Use your own.

---

## With Docker

Copy this `server/` folder to the machine, for example to `/opt/edsmt-api`,
then:

    cd /opt/edsmt-api
    cat > .env <<'EOF'
    RR_HOST_PORT=9110
    RR_PROXY_NETWORK=proxy
    EOF

`RR_PROXY_NETWORK` is the Docker network your reverse proxy is on, so the
proxy can reach the API by container name. If you have no such network yet:

    docker network create proxy

The container runs as an unprivileged user and writes its database to
`./data`. Docker creates that folder as root if it does not exist, and SQLite
then cannot write to it, so make it first and hand it over:

    mkdir -p data
    chown -R 1500 data

Start it:

    docker compose up -d --build
    curl -s localhost:9110/v1/health

The last line should print `"ok": true`, a version and row counts. The port
is bound to localhost only; nothing is reachable from outside until a reverse
proxy is put in front of it.

## Without Docker

It is a plain Python app. Python 3.10 or newer:

    pip install -r requirements.txt
    RR_DB=/path/to/deposits.db python main.py

It listens on port 8080.

---

## Putting it on the internet

Serve it over HTTPS behind whatever web server you already run. Templates for
the common ones are in this folder, each with its install commands at the top:

    vhost-nginx.conf          nginx
    vhost-nginx-limits.conf   nginx rate-limit zones (http context)
    vhost-apache.conf         Apache
    vhost-caddy.conf          Caddy
    detect-stack.sh           read-only: reports what is already serving

**Rate-limit at the proxy.** Submissions are open to every copy of the app,
so the proxy is what stops one client flooding it. The nginx templates carry
sensible limits.

**If a CDN or another proxy sits in front of your web server,** pass the real
client address through to it. Otherwise every commander arrives from the
same handful of addresses and they all share one rate-limit bucket.

---

## Settings

All optional. Put them in `.env` and `docker compose restart`.

| Setting | Default | What it does |
|---|---|---|
| `RR_HOST_PORT` | 9110 | Port on localhost the container is published on |
| `RR_PROXY_NETWORK` | proxy | Docker network the reverse proxy is on |
| `RR_DB` | /data/deposits.db | Where the database lives |
| `RR_WRITE_TOKEN` | *(blank)* | Blank means anyone running the app can share. Set it to make a private instance |
| `RR_STAFF` | *(blank)* | Who may mark sites verified — see below |
| `RR_HALF_LIFE_DAYS` | 21 | How fast confidence in a report fades |
| `RR_DEPLETION_DOUBT` | 0.05 | Doubt left by one "it is stripped" report |
| `RR_REFORMATION_ESTIMATE_DAYS` | 60 | A guess, used only inside the ranking |
| `RR_SELL_API` | *(blank)* | Base URL of a public market index for `/v1/sell` |
| `RR_SELL_API_NAME` | *(blank)* | What `/v1/sell` calls that index |
| `RR_SELL_CACHE` | 900 | Seconds an index answer is reused for |
| `RR_SELL_MIN_INTERVAL` | 1.0 | Fewest seconds between calls to the index |
| `RR_SELL_TIMEOUT` | 8 | Seconds to wait for the index before answering without it |
| `RR_CONTAINER` | edsmt-api | Container name `verify.sh` and `backup.sh` use |

`RR_HALF_LIFE_DAYS` is not how fast a deposit disappears. It is how fast our
confidence in a report nobody has rechecked fades.

`RR_REFORMATION_ESTIMATE_DAYS` (`RR_REGEN_DAYS` is its old name, still
read) is a guess and the API says so: nothing it
returns contains a countdown. What comes back is the elapsed time since a
site was reported stripped, which is a fact, beside `reformation_measured:
false`.

`RR_SELL_API` is optional. Without it `/v1/sell` answers from what
commanders' own games have read at markets. The index it points at must
answer the request described above `SELL_UPSTREAM_BASE` in `main.py`.

---

## Verification — who says a site is real

Every upload is `reported`. **Verification is granted by the server, never
claimed by the app** — an upload that says it is verified is stored as
reported anyway.

Staff are a name against a secret, so the database records *who* confirmed a
site:

    RR_STAFF=CMDR Someone:<a long random secret>,CMDR Another:<another>

Generate each secret with `openssl rand -hex 24` and give it only to that
person. They paste it into Settings → **Token, if you were given one** in the app, and
from then on sites they map are verified in their name. Removing somebody is
deleting their entry and restarting.

Verification does not stop the clock. A site verified months ago still fades
exactly like any other.

---

## Backups

    crontab -e

    17 4 * * *  /opt/edsmt-api/backup.sh >> /opt/edsmt-api/backup.log 2>&1

`backup.sh` takes a consistent snapshot with the database live and keeps 30
days of them.

---

## Pointing the app at it

Settings → **Community API URL** → your hostname, starting `https://`.

---

## What it exposes

    GET  /v1/health         up, which build, row counts
    POST /v1/deposits       share finds
    GET  /v1/deposits       search finds
    GET  /v1/sites          ranked sites
    GET  /v1/intact         which patches are most likely still there
    POST /v1/depletion      report a site worked out
    POST /v1/verify         staff: mark a site verified
    POST /v1/market         share prices read at a market
    GET  /v1/prices         prices commanders have read
    GET  /v1/sell           best sell prices, optionally near a system
    GET  /v1/grounds        what each kind of ground has carried (Where to land)
    GET  /v1/commodities    names, body classes and density tiers

Interactive documentation: `https://<your host>/docs`
