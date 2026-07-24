#!/usr/bin/env bash
set -u

GREEN='\033[32m'; RED='\033[31m'; BLUE='\033[34m'; RESET='\033[0m'
ok()   { printf "${GREEN}[PASS]${RESET} %s\n" "$*"; }
warn() { printf "${BLUE}[INFO]${RESET} %s\n" "$*"; }
bad()  { printf "${RED}[FAIL]${RESET} %s\n" "$*"; }

expected=(ForceP2P=0x11 RMForceP2PType=1 RMPcieP2PType=2 GrdmaPciTopoCheckOverride=1 EnableResizableBar=1)
file=/etc/modprobe.d/nvidia-p2p-override.conf
if [[ -r "$file" ]] && grep -q 'ForceP2P=0x11' "$file"; then
  ok "P2P override file present: $file"
else
  bad "P2P override file missing or incomplete: $file"
fi

params=/proc/driver/nvidia/params
if [[ -r "$params" ]]; then
  values=$(cat "$params")
  for item in "${expected[@]}"; do
    key=${item%%=*}; value=${item#*=}
    if grep -Eq "(^|[ ;])${key}:?[[:space:]]*${value}([ ;]|$)" <<<"$values"; then
      ok "runtime $key=$value"
    else
      bad "runtime $key is not $value"
    fi
  done
else
  bad "NVIDIA runtime parameter file is unavailable"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  warn "GPU topology (idle link speed may be lower than loaded speed):"
  nvidia-smi topo -m || true
  warn "Run a loaded benchmark to verify PCIe Gen5 x16; idle Gen1 is normal."
else
  bad "nvidia-smi is not installed"
fi

if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
try:
    import torch
    n = torch.cuda.device_count()
    print(f"\033[34m[INFO]\033[0m CUDA devices visible: {n}")
    if n > 1:
        pairs = [(i, j, torch.cuda.can_device_access_peer(i, j))
                 for i in range(n) for j in range(i + 1, n)]
        for i, j, enabled in pairs:
            tag = '\033[32m[PASS]\033[0m' if enabled else '\033[31m[FAIL]\033[0m'
            print(f"{tag} peer access CUDA {i}->{j}: {enabled}")
except Exception as exc:
    print(f"\033[34m[INFO]\033[0m torch peer check unavailable: {exc}")
PY
fi
