param(
    [string]$PythonVersion = "3.12",
    [switch]$SkipConnectionCheck,
    [switch]$StartPanel,
    [switch]$StartRelay
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $projectRoot

if (-not (Test-Path ".env")) {
    Write-Host "Brakuje pliku .env w katalogu projektu: $projectRoot" -ForegroundColor Red
    Write-Host "Skopiuj .env.example do .env i uzupelnij dane MT5." -ForegroundColor Yellow
    exit 1
}

Write-Host "Projekt: $projectRoot" -ForegroundColor Cyan

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Tworze srodowisko virtualenv..." -ForegroundColor Cyan
    py -$PythonVersion -m venv .venv
}

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

Write-Host "Aktualizuje pip..." -ForegroundColor Cyan
& $pythonExe -m pip install --upgrade pip

Write-Host "Instaluje zaleznosci projektu..." -ForegroundColor Cyan
& $pythonExe -m pip install -r requirements.txt

Write-Host "Instaluje pakiet MetaTrader5 dla Windows..." -ForegroundColor Cyan
& $pythonExe -m pip install MetaTrader5

if (-not $SkipConnectionCheck) {
    Write-Host "Uruchamiam test polaczenia MT5..." -ForegroundColor Cyan
    & $pythonExe -m src.execution.check_mt5_connection
}

if ($StartRelay) {
    Write-Host "Uruchamiam relay HTTP dla MT5..." -ForegroundColor Cyan
    & $pythonExe -m src.execution.mt5_relay
    exit $LASTEXITCODE
}

if ($StartPanel) {
    Write-Host "Uruchamiam panel HTTP..." -ForegroundColor Cyan
    & $pythonExe -m src.admin.run_http
}
else {
    Write-Host "Srodowisko jest gotowe." -ForegroundColor Green
    Write-Host "Uruchom panel recznie poleceniem:" -ForegroundColor Green
    Write-Host ".\.venv\Scripts\python.exe -m src.admin.run_http" -ForegroundColor White
}