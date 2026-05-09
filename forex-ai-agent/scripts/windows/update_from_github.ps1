param(
    [Alias("ProjectRoot")]
    [string]$ProjectDir = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [string]$LogDir = "$(Join-Path $env:LOCALAPPDATA 'forex-ai-agent\logs')",
    [switch]$SkipPipInstall,
    [Alias("RestartAdminPanel")]
    [switch]$RestartPanel,
    [switch]$InstallMt5
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )

    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Write-Host $line
    Add-Content -Path $script:LogPath -Value $line
}

function Restart-AdminPanel {
    param(
        [string]$ProjectDir,
        [string]$PythonExe
    )

    if (-not (Test-Path $PythonExe)) {
        Write-Log "Cannot restart admin panel because Python executable is missing: $PythonExe" "WARN"
        return
    }

    $appPath = (Join-Path $ProjectDir 'src\admin\app.py').ToLowerInvariant()
    $processes = Get-CimInstance Win32_Process | Where-Object {
        $commandLine = $_.CommandLine
        if (-not $commandLine) {
            return $false
        }

        $normalized = $commandLine.ToLowerInvariant()
        return $normalized.Contains('src.admin.run_http') -or ($normalized.Contains('streamlit') -and $normalized.Contains($appPath))
    }

    if ($processes) {
        foreach ($process in $processes) {
            Write-Log "Stopping existing admin panel process PID=$($process.ProcessId)"
            try {
                Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
            }
            catch {
                Write-Log "Failed to stop PID $($process.ProcessId): $($_.Exception.Message)" "WARN"
            }
        }
    }
    else {
        Write-Log "No running admin panel process found. Starting a new one."
    }

    Write-Log "Starting admin panel via src.admin.run_http"
    Start-Process -FilePath $PythonExe -ArgumentList '-m', 'src.admin.run_http' -WorkingDirectory $ProjectDir -WindowStyle Hidden | Out-Null
}

$locationPushed = $false

try {
    if (-not (Test-Path $ProjectDir)) {
        throw "Missing project directory: $ProjectDir"
    }

    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }

    $script:LogPath = Join-Path $LogDir ("github-update-{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HHmmss"))
    New-Item -ItemType File -Path $script:LogPath -Force | Out-Null

    Write-Log "Start update. ProjectDir=$ProjectDir Remote=$Remote Branch=$Branch"

    $pythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        throw "Missing .venv\Scripts\python.exe. Run project setup first."
    }

    $gitCommand = Get-Command git -ErrorAction Stop
    $gitWorktree = (& $gitCommand.Source -C $ProjectDir rev-parse --show-toplevel).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $gitWorktree) {
        throw "Could not resolve Git worktree for $ProjectDir"
    }

    Write-Log "Resolved Git worktree: $gitWorktree"

    Push-Location $gitWorktree
    $locationPushed = $true

    $statusOutput = & $gitCommand.Source -C $gitWorktree status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "git status failed."
    }

    if ($statusOutput) {
        Write-Log "Worktree is dirty. Skipping automatic pull to protect local changes." "WARN"
        exit 0
    }

    $currentBranch = (& $gitCommand.Source -C $gitWorktree rev-parse --abbrev-ref HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "git rev-parse failed."
    }

    if ($currentBranch -ne $Branch) {
        Write-Log "Current branch is '$currentBranch'. Expected '$Branch'. Skipping automatic pull." "WARN"
        exit 0
    }

    $requirementsPath = Join-Path $ProjectDir 'requirements.txt'
    $requirementsHashBefore = $null
    if (Test-Path $requirementsPath) {
        $requirementsHashBefore = (Get-FileHash $requirementsPath -Algorithm SHA256).Hash
    }

    Write-Log "Fetching $Remote/$Branch"
    & $gitCommand.Source -C $gitWorktree fetch $Remote $Branch --prune
    if ($LASTEXITCODE -ne 0) {
        throw "git fetch failed."
    }

    Write-Log "Pulling $Remote/$Branch with --ff-only"
    & $gitCommand.Source -C $gitWorktree pull --ff-only $Remote $Branch
    if ($LASTEXITCODE -ne 0) {
        throw "git pull failed."
    }

    $requirementsHashAfter = $null
    if (Test-Path $requirementsPath) {
        $requirementsHashAfter = (Get-FileHash $requirementsPath -Algorithm SHA256).Hash
    }

    if (-not $SkipPipInstall -and $requirementsHashBefore -ne $requirementsHashAfter) {
        Write-Log "requirements.txt changed. Installing dependencies in .venv"
        & $pythonExe -m pip install -r $requirementsPath
        if ($LASTEXITCODE -ne 0) {
            throw "pip install failed after pulling updates."
        }
    }
    else {
        Write-Log "requirements.txt did not change."
    }

    if ($InstallMt5) {
        Write-Log "Installing MetaTrader5 package"
        & $pythonExe -m pip install MetaTrader5
        if ($LASTEXITCODE -ne 0) {
            throw "MetaTrader5 installation failed."
        }
    }

    if ($RestartPanel) {
        Restart-AdminPanel -ProjectDir $ProjectDir -PythonExe $pythonExe
    }

    Write-Log "Update finished successfully."
    exit 0
}
catch {
    Write-Log $_.Exception.Message "ERROR"
    exit 1
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
}
