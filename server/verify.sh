#!/usr/bin/env bash
# Prove the API actually works, end to end, from the box it runs on.
#
#   ./verify.sh                       against the local container (9110)
#   ./verify.sh https://api.radioraxxla.com    through the reverse proxy
#
# It writes one deposit to a throwaway system called "EDSMT Verify", reads it
# back, and reports. Safe to run against the live database - the test rows
# are all in that one fake system and can be dropped with the SQL at the end.
set -uo pipefail

# 8080 is the port INSIDE the container. The host binds RR_HOST_PORT,
# 9110 by default, because 8080 is usually already taken on a busy box.
BASE="${1:-http://127.0.0.1:${RR_HOST_PORT:-9110}}"
TOKEN="${RR_WRITE_TOKEN:-}"
AUTH=()
[ -n "$TOKEN" ] && AUTH=(-H "Authorization: Bearer $TOKEN")

# Identify as the app does. An edge bot filter sees a bare "curl/8.x"
# and treats it as something to block, so a diagnostic sending the
# default agent tests the filter rather than the API - which is exactly
# how this script once reported seven failures against a healthy service.
UA=(-A "EDSMT/1.1 (+https://radioraxxla.com/EDSMT/)")

pass=0; fail=0
check() {
    if [ "$2" = "1" ]; then echo "  PASS  $1"; pass=$((pass+1))
    else echo "  FAIL  $1  ${3:-}"; fail=$((fail+1)); fi
}
has() { echo "$1" | grep -q "$2" && echo 1 || echo 0; }

echo "checking $BASE"
echo

health=$(curl -fsS "${UA[@]}" --max-time 10 "$BASE/v1/health" 2>&1)
check "the API answers /v1/health" "$(has "$health" '"ok":true')" "$health"
check "it reports its version" "$(has "$health" '"version"')" 
echo "        $health"
echo

stamp=$(date +%s)
body=$(cat <<JSON
{"\$schema":"radioraxxla/surfacemining/1",
 "header":{"uploaderID":"verify","softwareName":"verify.sh","softwareVersion":"1.0",
           "gatewayTimestamp":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"},
 "message":{"deposits":[
   {"system":"EDSMT Verify","planet":"V 1","spot":"$stamp","type":"Magnesite",
    "rigs":4,"lat":1.5,"lon":-2.5,"density":"High"}]}}
JSON
)
up=$(curl -fsS "${UA[@]}" --max-time 10 -X POST "$BASE/v1/deposits" \
        -H 'Content-Type: application/json' "${AUTH[@]}" -d "$body" 2>&1)
check "a deposit can be uploaded" "$(has "$up" '"accepted":1')" "$up"

again=$(curl -fsS "${UA[@]}" --max-time 10 -X POST "$BASE/v1/deposits" \
        -H 'Content-Type: application/json' "${AUTH[@]}" -d "$body" 2>&1)
check "the same one again is a duplicate, not a second row" \
      "$(has "$again" '"duplicates":1')" "$again"

found=$(curl -fsS "${UA[@]}" --max-time 10 "$BASE/v1/deposits?commodity=Magnesite&system=EDSMT%20Verify" 2>&1)
check "it comes back out of a search" "$(has "$found" 'EDSMT Verify')" "${found:0:200}"

sites=$(curl -fsS "${UA[@]}" --max-time 10 "$BASE/v1/sites?limit=5" 2>&1)
check "site ranking answers" "$(has "$sites" '"sites"')" "${sites:0:200}"

bad=$(curl -s "${UA[@]}" --max-time 10 -o /dev/null -w '%{http_code}' -X POST "$BASE/v1/deposits" \
        -H 'Content-Type: application/json' "${AUTH[@]}" -d '{"nonsense":true}')
check "rubbish is rejected with a 422" "$([ "$bad" = "422" ] && echo 1 || echo 0)" "got $bad"

case "$BASE" in
  https://*)
    code=$(curl -s "${UA[@]}" --max-time 10 -o /dev/null -w '%{http_code}' "${BASE/https:/http:}/v1/health")
    check "plain http redirects or is refused" \
          "$([ "$code" = "301" ] || [ "$code" = "308" ] || [ "$code" = "000" ] && echo 1 || echo 0)" \
          "got $code"
    ;;
esac

echo
echo "$pass passed, $fail failed"
echo
echo "To clear the rows this made:"
echo "  docker exec -it ${RR_CONTAINER:-edsmt-api} python -c \\"
echo "    \"import sqlite3;c=sqlite3.connect('/data/deposits.db');\\"
echo "     c.execute(\\\"delete from deposits where system='EDSMT Verify'\\\");\\"
echo "     c.execute(\\\"delete from sites where system='EDSMT Verify'\\\");c.commit()\""
[ "$fail" -eq 0 ] || exit 1
