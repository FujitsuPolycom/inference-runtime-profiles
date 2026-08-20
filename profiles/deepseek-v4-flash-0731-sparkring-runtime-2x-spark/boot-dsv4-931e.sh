#!/bin/bash
# @reboot bootstrap for rank 1 (follower): launches the ring-runtime DeepSeek
# follower container if it is not already running. Rank 0's boot script also
# triggers this launch over SSH; the running-container check makes whichever
# fires second a no-op, so a live follower is never torn down by a duplicate
# boot path.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROFILE_ENV="${PROFILE_ENV:-$SCRIPT_DIR/.env}"
if [ -f "$PROFILE_ENV" ]; then
    . "$PROFILE_ENV"
fi
: "${HOST_WORK_DIR:?set HOST_WORK_DIR in $PROFILE_ENV or the process environment}"

exec > "$HOST_WORK_DIR/logs/boot-dsv4-rank1.log" 2>&1
set -x

for i in $(seq 1 60); do
    docker info >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1 && break
    sleep 5
done

docker ps --format '{{.Names}}' | grep -q '^leg3pair-dsv4-r1$' || \
    RANK=1 bash "$HOST_WORK_DIR/leg3pair-launch.sh"
echo "boot: follower ensured"
