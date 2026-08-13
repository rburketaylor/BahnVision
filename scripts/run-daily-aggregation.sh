#!/bin/sh
# Reads ADMIN_API_KEY from PID 1's environment at execution time so the key is
# never embedded in the crontab entry. BusyBox crond only exports a minimal
# environment to jobs, so we read the container environment directly.
set -eu

admin_api_key="$(
    tr '\000' '\n' </proc/1/environ |
        sed -n 's/^ADMIN_API_KEY=//p' |
        head -n 1
)"

if [ -z "$admin_api_key" ]; then
    echo "ADMIN_API_KEY is required" >&2
    exit 1
fi

exec wget -q -O- \
    --header="X-API-Key: ${admin_api_key}" \
    --post-data="" \
    http://backend:8000/api/v1/heatmap/aggregate-daily \
    >/dev/null 2>&1
