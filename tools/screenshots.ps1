# Captures d'écran du panneau sur données fictives (tools/demo), pour le README.
# Prérequis : servir la racine du dépôt (python -m http.server 8765 --bind 127.0.0.1, ou HCO_PORT) ;
# les modules JavaScript ne se chargent pas depuis file://.
# Usage : pwsh tools/screenshots.ps1   → docs/screenshots/<langue>-<onglet>.png
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$browser = @(
  'C:\Program Files\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
$out = Join-Path $root 'docs\screenshots'
New-Item -ItemType Directory -Force $out | Out-Null
$port = if ($env:HCO_PORT) { $env:HCO_PORT } else { '8765' }
$page = "http://127.0.0.1:$port/tools/demo/index.html"
$profile = Join-Path ([IO.Path]::GetTempPath()) 'hco-shots-profile'
foreach ($lang in 'fr', 'en') {
  foreach ($shot in @(@{tab='curve'; h=1700}, @{tab='planning'; h=1500}, @{tab='savings'; h=1150}, @{tab='diag'; h=1200}, @{tab='boiler'; h=1700}, @{tab='settings'; h=1250})) {
    $file = Join-Path $out "$lang-$($shot.tab).png"
    & $browser --headless=new --disable-gpu --hide-scrollbars `
      "--user-data-dir=$profile" "--window-size=1200,$($shot.h)" --virtual-time-budget=4000 `
      "--screenshot=$file" "$page`?tab=$($shot.tab)&lang=$lang" 2>$null | Out-Null
    Write-Output "$lang-$($shot.tab): $((Get-Item $file).Length) octets"
  }
}
