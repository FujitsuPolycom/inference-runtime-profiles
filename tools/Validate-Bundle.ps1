param([Parameter(Mandatory)] [string] $Path)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path (Join-Path $Path 'manifest.json')) -and
    -not (Test-Path (Join-Path $Path 'profile.env.example'))) {
  throw 'manifest.json or profile.env.example is missing'
}
$text = Get-ChildItem -LiteralPath $Path -File -Recurse | Get-Content -Raw
$patterns = @('password','api[_-]?key','private[_-]?key','/home/[^/]+','/root/','192\.168\.','10\.[0-9]+\.','172\.(1[6-9]|2[0-9]|3[01])\.')
$hits = $patterns | Where-Object { $text -match $_ }
if ($hits) { throw "Possible private data found: $($hits -join ', ')" }
Write-Host "Bundle looks publishable: $Path"
