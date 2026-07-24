#!/usr/bin/env bash
set -euo pipefail

: "${LMCACHE_HOST:=127.0.0.1}"
: "${LMCACHE_PORT:=5555}"
: "${LMCACHE_HTTP_PORT:=8089}"
: "${LMCACHE_CHUNK_SIZE:=512}"
: "${LMCACHE_L1_GB:=48}"
: "${LMCACHE_L1_INIT_GB:=48}"
: "${LMCACHE_L2_PATH:=}"
: "${LMCACHE_LOG:=/tmp/lmcache-mp.log}"

transfer_config="$(printf '{\"kv_connector\":\"LMCacheMPConnector\",\"kv_role\":\"kv_both\",\"kv_connector_extra_config\":{\"lmcache.mp.host\":\"tcp://%s\",\"lmcache.mp.port\":%s,\"lmcache.mp.mq_timeout\":30,\"lmcache.mp.heartbeat_interval\":5}}' "${LMCACHE_HOST}" "${LMCACHE_PORT}")"
rm -f "${LMCACHE_LOG}"

l2_args=()
if [[ -n "${LMCACHE_L2_PATH}" ]]; then
  mkdir -p "${LMCACHE_L2_PATH}"
  l2_args+=(--l2-adapter "{\"type\":\"fs\",\"base_path\":\"${LMCACHE_L2_PATH}\"}")
fi

lmcache server \
  --host "${LMCACHE_HOST}" --port "${LMCACHE_PORT}" \
  --chunk-size "${LMCACHE_CHUNK_SIZE}" \
  --l1-size-gb "${LMCACHE_L1_GB}" --l1-init-size-gb "${LMCACHE_L1_INIT_GB}" \
  --l1-write-ttl-seconds 600 --l1-read-ttl-seconds 300 \
  --eviction-policy LRU --eviction-trigger-watermark 0.90 --eviction-ratio 0.10 \
  "${l2_args[@]}" --l2-store-policy default --l2-prefetch-policy retain \
  --http-port "${LMCACHE_HTTP_PORT}" > >(tee -a "${LMCACHE_LOG}") 2>&1 &
lmcache_pid=$!
trap 'kill "${lmcache_pid}" 2>/dev/null || true' EXIT INT TERM

for _ in $(seq 1 120); do
  kill -0 "${lmcache_pid}" 2>/dev/null || { sed -n '1,320p' "${LMCACHE_LOG}" >&2; exit 1; }
  grep -q 'ZMQ cache server is running' "${LMCACHE_LOG}" 2>/dev/null && break
  sleep 1
done
grep -q 'ZMQ cache server is running' "${LMCACHE_LOG}" 2>/dev/null || { sed -n '1,240p' "${LMCACHE_LOG}" >&2; exit 1; }
echo "LMCache ready: L1=${LMCACHE_L1_GB}GB chunk=${LMCACHE_CHUNK_SIZE} L2=${LMCACHE_L2_PATH:-disabled}"

exec /usr/local/bin/serve-gilded-gnosis.sh --kv-transfer-config "${transfer_config}"
