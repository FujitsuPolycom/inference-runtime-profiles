#!/bin/bash
# @reboot bootstrap for rank 0: brings a cold host back to the DeepSeek
# serving configuration — the ring-runtime stack (leg3pair-dsv4-r0/-r1
# containers: sparkring image + overlay set, DSpark K5 speculation, LMCache
# NVMe tier). leg3pair-launch.sh creates the containers fresh, so there is no
# stale-process sweep and no cache-server ordering here: cache server and
# engine live and die with their container.
#
# Rank 1 is triggered from here over SSH after this node is ready; rank 1's
# own boot script also fires, and both sides launch only if the container is
# not already running, so the two never fight over a live follower.
#
# The fallback from-source stack (ggrun/ggbuild + run-dsv4-lmcache.sh) is
# untouched by this script; switching boot back to it is one crontab edit.

exec > "$HOME/work/qwen38-exl3/logs/boot-dsv4-aa42.log" 2>&1
set -x

RANK1=198.18.200.2
API=http://127.0.0.1:8000

# 0. Already healthy? Nothing to do.
if curl -sf -m 5 "$API/v1/models" >/dev/null 2>&1; then
    echo "boot: endpoint already serving"; exit 0
fi

# 1. Docker + GPU ready (driver can lag the daemon after reboot).
for i in $(seq 1 60); do
    docker info >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1 && break
    sleep 5
done

# 2. Wait for rank 1's host, then launch its follower if absent.
for i in $(seq 1 60); do
    ssh -o BatchMode=yes -o ConnectTimeout=5 "$RANK1" true 2>/dev/null && break
    sleep 10
done
ssh -o BatchMode=yes -o ConnectTimeout=5 "$RANK1" \
    "docker ps --format '{{.Names}}' | grep -q '^leg3pair-dsv4-r1\$' || RANK=1 bash /home/code/work/qwen38-exl3/leg3pair-launch.sh" || true
sleep 5

# 3. Launch rank 0 if absent.
docker ps --format '{{.Names}}' | grep -q '^leg3pair-dsv4-r0$' || \
    RANK=0 bash "$HOME/work/qwen38-exl3/leg3pair-launch.sh"

# 4. Wait for the endpoint (cold model load can take many minutes).
for i in $(seq 1 180); do
    curl -sf -m 5 "$API/v1/models" >/dev/null 2>&1 && { echo "boot: serving"; exit 0; }
    sleep 10
done
echo "boot: endpoint did not come up within 30 min - docker logs leg3pair-dsv4-r0"
exit 1
