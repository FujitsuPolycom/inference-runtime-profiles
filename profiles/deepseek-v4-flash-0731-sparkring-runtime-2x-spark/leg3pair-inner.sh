#!/bin/bash
# In-container bootstrap for the leg3pair DeepSeek stack (PID-1 side).
# With LMCACHE=1: installs the qualified LMCache wheel (release/v0.5.2-glm52-
# dcp-base + heartbeat patch, built against this image's torch 2.12) over the
# image's older 0.5.2+glm52dcp4.1 cut, starts this rank's MP cache server,
# then execs the engine. Server and engine share the container lifecycle, so
# a container replacement can never leave a server holding a dead engine's
# CUDA IPC mappings.
set -e
unset VLLM_PREFIX_CACHE_RETENTION_INTERVAL VLLM_ADAPTIVE_SPEC_DEPTHS \
      SPARK_ADAPTIVE_MTP_TIMED_WINDOW VLLM_SPARK_TP4_DCP_MODE

if [ "${LMCACHE:-0}" = "1" ]; then
    /opt/venv/bin/pip install -q --no-deps /wheels/lmcache-*.whl
    /opt/venv/bin/pip install -q --no-deps redis async-timeout \
        opentelemetry-exporter-prometheus opentelemetry-sdk \
        opentelemetry-api opentelemetry-semantic-conventions \
        opentelemetry-sdk 2>/dev/null || \
        /opt/venv/bin/pip install -q redis opentelemetry-exporter-prometheus
    /opt/venv/bin/python -c 'import lmcache; print("lmcache", lmcache.__version__)'
    export LMCACHE_DISABLE_BANNER=1
    nohup /opt/venv/bin/lmcache server \
        --instance-id "dsv4leg3-r${LEG3_RANK}-cs256" \
        --host 0.0.0.0 --port 6570 --http-port 6580 \
        --chunk-size 256 \
        --max-gpu-workers 2 --max-cpu-workers 2 \
        --supported-transfer-mode auto \
        --l1-size-gb 8 --l1-use-lazy --l1-init-size-gb 0 --eviction-policy LRU \
        --l2-adapter '{"type":"fs_native","base_path":"/l2cache","num_workers":2,"use_odirect":false,"max_capacity_gb":200}' \
        > /l2cache/server.log 2>&1 &
    for i in $(seq 1 12); do
        grep -q 'Uvicorn running' /l2cache/server.log 2>/dev/null && break
        sleep 3
    done
    grep -q 'Uvicorn running' /l2cache/server.log 2>/dev/null || {
        echo "FATAL: lmcache server did not start; tail:"; tail -5 /l2cache/server.log; exit 1; }
fi

exec /opt/venv/bin/vllm "$@"
