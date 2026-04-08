$ErrorActionPreference = "Stop"

$appName = "imarisha-scan"
$entrypoint = "src/imarisha_scan/main.py"
$distDir = "dist/windows"

New-Item -ItemType Directory -Path $distDir -Force | Out-Null

pyinstaller `
  --noconfirm `
  --onefile `
  --windowed `
  --name $appName `
  --distpath $distDir `
  $entrypoint

Write-Host "Built $distDir/$appName.exe"
