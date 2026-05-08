param(
    [Parameter(Mandatory = $true)]
    [string]$Domain,
    [string]$PythonVersion = "3.12",
    [string]$ProjectDir = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$CaddyPath = "C:\Program Files\Caddy\caddy.exe",
    [switch]$InstallCaddy,
    [switch]$SkipMt5Install,
    [switch]$StartPanel
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ProjectDir)) {
    Write-Host "Brakuje katalogu projektu: $ProjectDir" -ForegroundColor Red
    exit 1
}

Set-Location $ProjectDir

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Utworzono .env z .env.example" -ForegroundColor Yellow
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -$PythonVersion -m venv .venv
}

$pythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r requirements.txt

if (-not $SkipMt5Install) {
    & $pythonExe -m pip install MetaTrader5
}

$caddyDir = Split-Path -Parent $CaddyPath
$caddyfilePath = Join-Path $caddyDir "Caddyfile"
if (-not (Test-Path $caddyDir)) {
    New-Item -ItemType Directory -Path $caddyDir -Force | Out-Null
}

@"
$Domain {
    reverse_proxy 127.0.0.1:8501
}
"@ | Set-Content -Path $caddyfilePath -Encoding ascii

if ($InstallCaddy) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "Brakuje winget. Zainstaluj Caddy recznie i uruchom skrypt ponownie." -ForegroundColor Red
        exit 1
    }
    winget install --id CaddyServer.Caddy --source winget --accept-source-agreements --accept-package-agreements
}

if (-not (Test-Path $CaddyPath)) {
    Write-Host "Nie znaleziono Caddy pod sciezka: $CaddyPath" -ForegroundColor Yellow
    Write-Host "Zainstaluj Caddy i uruchom go z Caddyfile: $caddyfilePath" -ForegroundColor Yellow
}
else {
    Write-Host "Caddyfile zapisany w: $caddyfilePath" -ForegroundColor Green
    Write-Host "Uruchom Caddy jako administrator poleceniem:" -ForegroundColor Green
    Write-Host "& '$CaddyPath' run --config '$caddyfilePath'" -ForegroundColor White
}

Write-Host "Firewall Windows: otworz porty 80 i 443 tylko dla panelu publicznego." -ForegroundColor Cyan

if ($StartPanel) {
    & $pythonExe -m src.admin.run_http
}
else {
    Write-Host "Panel uruchomisz recznie poleceniem:" -ForegroundColor Green
    Write-Host "& '$pythonExe' -m src.admin.run_http" -ForegroundColor White
}