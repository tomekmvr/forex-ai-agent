param(
    [string]$ProjectDir = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$TaskName = "ForexAIAgentRunner",
    [int]$IntervalMinutes = 15,
    [switch]$AtStartup
)

$ErrorActionPreference = "Stop"

if ($IntervalMinutes -le 0) {
    Write-Host "IntervalMinutes musi byc dodatnie." -ForegroundColor Red
    exit 1
}

$pythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "Brakuje interpretera: $pythonExe" -ForegroundColor Red
    exit 1
}

$logsDir = Join-Path $ProjectDir "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

$runOncePrefix = ""
if (-not $AtStartup) {
    $runOncePrefix = "$env:FOREX_AGENT_RUNNER_RUN_ONCE='true'; "
}

$runnerScript = "$runOncePrefix& '$pythonExe' -m src.runtime.agent_runner *> '$logsDir\agent_runner.log'"

if ($AtStartup) {
    schtasks /Create /SC ONSTART /TN $TaskName /TR "powershell.exe -ExecutionPolicy Bypass -Command $runnerScript" /RU $env:USERNAME /RL HIGHEST /F
}
else {
    schtasks /Create /SC MINUTE /MO $IntervalMinutes /TN $TaskName /TR "powershell.exe -ExecutionPolicy Bypass -Command $runnerScript" /RU $env:USERNAME /RL HIGHEST /F
}

Write-Host "Zadanie Harmonogramu zadan zostalo utworzone: $TaskName" -ForegroundColor Green