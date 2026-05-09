param(
    [string]$ProjectDir = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$Branch = "main",
    [switch]$RestartPanel,
    [switch]$InstallMt5
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ProjectDir)) {
    Write-Host "Brakuje katalogu projektu: $ProjectDir" -ForegroundColor Red
    exit 1
}

Set-Location $ProjectDir

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Brakuje .venv. Najpierw uruchom install_public_panel.ps1 lub setup projektu." -ForegroundColor Red
    exit 1
}

$pythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"

git fetch origin
git checkout $Branch
git pull --ff-only origin $Branch

& $pythonExe -m pip install -r requirements.txt

if ($InstallMt5) {
    & $pythonExe -m pip install MetaTrader5
}

if ($RestartPanel) {
    $processes = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match "python|pythonw" -and
        $_.CommandLine -and
        (
            $_.CommandLine -like "*src.admin.run_http*" -or
            $_.CommandLine -like "*streamlit run*app.py*"
        )
    }

    foreach ($process in $processes) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
        }
        catch {
            Write-Host "Nie udalo sie zatrzymac procesu PID $($process.ProcessId): $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }

    Start-Process -FilePath $pythonExe -ArgumentList "-m", "src.admin.run_http" -WorkingDirectory $ProjectDir
    Write-Host "Panel zostal uruchomiony ponownie." -ForegroundColor Green
}

Write-Host "Aktualizacja z GitHub zakonczona." -ForegroundColor Green