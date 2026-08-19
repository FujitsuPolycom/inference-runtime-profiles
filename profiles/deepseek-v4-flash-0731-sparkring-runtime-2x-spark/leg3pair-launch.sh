#!/bin/bash
# DeepSeek-V4-Flash-0731 on the 2x Spark pair, using the 4x ring's runtime:
# the sparkring image (r34-sm121a-flat2-20260810) plus its /var/tmp overlay
# set, reproduced from the live ring container's spec. This is the
# speculation-capable configuration: DSpark depth 5 (= the checkpoint's
# dspark_block_size, the validator's minimum) with moe_backend b12x — the
# component pairing on which speculation serves without the output corruption
# that forced it off in the venv-dsv4 stack (vllm issue #43416).
#
# Deltas from the ring container, and nothing else:
#   - TP 4 -> 2, --nnodes 2, master 198.18.200.1:29500, rank 1 --headless
#   - SPARK_TP4/VLLM_SPARK_TP4 custom-transport env removed: its source admits
#     only world_size==4, so NCCL carries the collectives at TP2
#   - NCCL set to this pair's proven point-to-point config (single rail
#     rocep1s0f0, GID 0, RoCE v1) instead of the ring's 4-cycle settings
#   - first-launch memory envelope: 131072 context, 10 GiB KV, 8 seqs,
#     gpu-memory-utilization 0.70 (the GB10 unified-memory ceiling)
#   - served names: dsv4-flash (gateway compatibility) + leg3
#
# Env comes from /var/tmp/leg3pair.env (185 lines captured from the ring
# container, transport family stripped); binds from /var/tmp/leg3pair.binds
# (51 mounts; model/cache/HF sources re-pointed to this pair's paths).
#
# LMCACHE=1 (default) adds the NVMe KV tier: the r18-qualified LMCache branch
# (wheel at /ws/wheels-t212, heartbeat patch included, torch-2.12 build) is
# installed over the image's older cut at container start, one MP server runs
# per rank inside the engine's own container, and the engine gets the MP
# connector config. L2 lives at lmcache-l2-dsv4-0731-spec-b256 — a fresh path
# because checkpoint (0731) and transfer set (DSpark hidden-state caches) both
# differ from the no-spec tier's. LMCACHE=0 launches without the tier.
#
# Usage: RANK=0|1 [LMCACHE=0|1] bash leg3pair-launch.sh   (on the HOST)
set -eu
RANK="${RANK:?set RANK=0 or 1}"
LMCACHE="${LMCACHE:-1}"
HOSTIP=$([ "$RANK" = "0" ] && echo 198.18.200.1 || echo 198.18.200.2)
IMG=sparkring/glm52-exl3-r7-3.5bpw:r34-sm121a-flat2-20260810
L2DIR=/home/code/work/qwen38-exl3/lmcache-l2-dsv4-0731-spec-b256

mkdir -p /var/tmp/leg3-cache "$HOME/.cache/huggingface" "$L2DIR"

ARGS=(run -d --name "leg3pair-dsv4-r$RANK"
  --network host --ipc host --gpus all --shm-size 16g
  --ulimit memlock=-1:-1 --cap-add IPC_LOCK
  --device /dev/infiniband
  --entrypoint /bin/bash)

while IFS= read -r e; do
  [ -n "$e" ] && ARGS+=(-e "$e")
done < /var/tmp/leg3pair.env

ARGS+=(-e "VLLM_HOST_IP=$HOSTIP"
  -e NCCL_SOCKET_IFNAME=enp1s0f0np0 -e GLOO_SOCKET_IFNAME=enp1s0f0np0
  -e TP_SOCKET_IFNAME=enp1s0f0np0
  -e NCCL_IB_HCA=rocep1s0f0 -e NCCL_IB_GID_INDEX=0
  -e NCCL_IB_SUBNET_AWARE_ROUTING=0 -e NCCL_CROSS_NIC=1
  -e NCCL_DEBUG=INFO
  -e "LMCACHE=$LMCACHE" -e "LEG3_RANK=$RANK")

if [ "$LMCACHE" = "1" ]; then
  # The MP connector pins KV via CUDA IPC; the VMM allocator must not remap.
  ARGS+=(-e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:False)
fi

while IFS= read -r b; do
  [ -n "$b" ] && ARGS+=(-v "$b")
done < /var/tmp/leg3pair.binds
ARGS+=(-v /home/code/work/qwen38-exl3/wheels-t212:/wheels:ro
  -v "$L2DIR:/l2cache"
  -v /var/tmp/leg3pair-inner.sh:/leg3pair-inner.sh:ro)

ARGS+=("$IMG" -c 'exec bash /leg3pair-inner.sh "$@"'
  _ serve /models/deepseek-v4-flash-0731
  --tensor-parallel-size 2 --nnodes 2 --node-rank "$RANK"
  --master-addr 198.18.200.1 --master-port 29500
  --distributed-executor-backend mp
  --dtype bfloat16
  --max-model-len 131072 --max-num-seqs 8
  --gpu-memory-utilization 0.70
  --kv-cache-memory-bytes 10737418240
  --kernel-config '{"enable_cutedsl_warmup": false}'
  --served-model-name dsv4-flash leg3
  --kv-cache-dtype fp8
  --enable-auto-tool-choice --tool-call-parser deepseek_v4
  --speculative-config '{"method": "dspark", "num_speculative_tokens": 5, "moe_backend": "b12x"}'
  --port 8000 --host 0.0.0.0)

if [ "$LMCACHE" = "1" ]; then
  ARGS+=(--kv-transfer-config '{"kv_connector":"LMCacheMPConnector","kv_role":"kv_both","kv_load_failure_policy":"recompute","kv_connector_extra_config":{"lmcache.mp.server_urls":["tcp://192.168.0.200:6570","tcp://192.168.0.174:6570"],"lmcache.mp.mq_timeout":60,"lmcache.mp.heartbeat_interval":10}}')
fi

[ "$RANK" = "1" ] && ARGS+=(--headless)

docker rm -f "leg3pair-dsv4-r$RANK" 2>/dev/null || true
docker "${ARGS[@]}"
echo "launched leg3pair-dsv4-r$RANK"
