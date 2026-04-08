$ErrorActionPreference = "Stop"

$appName = "imarisha-scan"
$entrypoint = "src/imarisha_scan/main.py"

pyinstaller --noconfirm --onefile --name $appName $entrypoint

Write-Host "Built dist/$appName.exe"
