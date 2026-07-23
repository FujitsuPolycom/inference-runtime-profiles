param(
  [Parameter(Mandatory)] [string] $Container,
  [Parameter(Mandatory)] [string] $Name,
  [string] $Root = "$PSScriptRoot\..\profiles"
)
$ErrorActionPreference = 'Stop'
$safe = $Name -replace '[^A-Za-z0-9._-]', '-'
$out = Join-Path $Root $safe
New-Item -ItemType Directory -Force -Path $out | Out-Null

$inspect = docker inspect $Container | ConvertFrom-Json
if (-not $inspect) { throw "Container not found: $Container" }
$cfg = $inspect[0]

$env = @{}
foreach ($item in $cfg.Config.Env) {
  $parts = $item -split '=', 2
  if ($parts.Count -eq 2) { $env[$parts[0]] = $parts[1] }
}

# Deliberately retain only reproducibility-relevant, non-secret variables.
$keep = $env.Keys | Where-Object {
  $_ -match '^(CUDA|NCCL|TP|DCP|MTP|KV|VLLM|B12X|SPARKINFER|LMCACHE|GPU|MAX_|GRAPH|PORT|MODEL|PYTORCH|TORCH|TRITON|CUTE|OMP|GLOO|SAFETENSORS)'
}
$cleanEnv = [ordered]@{}
foreach ($key in ($keep | Sort-Object)) {
  $value = $env[$key]
  $value = $value -replace '(?i)(password|token|secret|api[_-]?key)=[^,; ]+', '$1=<REDACTED>'
  $value = $value -replace '(?i)(/home/|/root/|C:\\Users\\)[^ :"'']+', '<PRIVATE_PATH>'
  $value = $value -replace '\b(?:\d{1,3}\.){3}\d{1,3}\b', '<PRIVATE_IP>'
  $cleanEnv[$key] = $value
}

$manifest = [ordered]@{
  schema_version = 1
  profile = $safe
  captured_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  image = $cfg.Config.Image
  image_id = $cfg.Image
  command = $cfg.Config.Cmd
  entrypoint = $cfg.Config.Entrypoint
  environment = $cleanEnv
  mounts = @($cfg.Mounts | ForEach-Object {
    [ordered]@{ type=$_.Type; destination=$_.Destination; mode=$_.Mode }
  })
  labels = [ordered]@{}
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $out 'manifest.json')
@"`n# $safe`n`nCaptured from a running container with private values redacted. Review before publishing.`n"@ | Set-Content -Encoding utf8 (Join-Path $out 'README.md')
Write-Host "Wrote sanitized profile: $out"

