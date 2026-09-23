#!/usr/bin/env bash
# Nightly backup. SQLite must not be copied while it is being written to -
# .backup takes a consistent snapshot with the database live.
#
# The sqlite3 command line tool is NOT installed on a stock Ubuntu server,
# and a backup that fails at 4am because of a missing package is worse than
# no backup at all, because you believe you have one. The container always
# has Python, and Python has had Connection.backup() since 3.7, so if the
# host tool is missing the job is done inside the container instead.
set -euo pipefail
cd "$(dirname "$0")"

STAMP=$(date +%Y%m%d-%H%M%S)
OUT="backups/deposits-${STAMP}.db"
mkdir -p backups

if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 data/deposits.db ".backup '${OUT}'"
else
    # /data inside the container is ./data out here, so the snapshot is
    # written there and then moved into place.
    docker exec "${RR_CONTAINER:-edsmt-api}" python -c "
import sqlite3
source = sqlite3.connect('/data/deposits.db')
target = sqlite3.connect('/data/.backup-in-progress.db')
source.backup(target)
target.close(); source.close()"
    mv data/.backup-in-progress.db "${OUT}"
fi

gzip -f "${OUT}"

# Keep 30 days
find backups -name 'deposits-*.db.gz' -mtime +30 -delete
echo "backed up to ${OUT}.gz"
