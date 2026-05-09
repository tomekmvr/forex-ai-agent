param(
    [string]$TaskName = "ForexAiAgentDailyGithubUpdate",
    [string]$Time = "03:00",
    [Alias("ProjectRoot")]
    [string]$ProjectDir = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [Alias("RestartPanel")]
    [switch]$RestartAdminPanel,
    [switch]$InstallMt5
)

$ErrorActionPreference = "Stop"

if ($Time -notmatch '^(?:[01]\d|2[0-3]):[0-5]\d$') {
    throw "Time must use HH:mm format, for example 03:00 or 22:30."
}

$updateScript = Join-Path $PSScriptRoot "update_from_github.ps1"
if (-not (Test-Path $updateScript)) {
    throw "Missing update script: $updateScript"
}

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$triggerTime = [datetime]::ParseExact($Time, 'HH:mm', $null)

$actionArguments = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', ('"{0}"' -f $updateScript),
    '-ProjectDir', ('"{0}"' -f $ProjectDir),
    '-Remote', $Remote,
    '-Branch', $Branch
) -join ' '

if ($RestartAdminPanel) {
    $actionArguments = "$actionArguments -RestartAdminPanel"
}

if ($InstallMt5) {
    $actionArguments = "$actionArguments -InstallMt5"
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $actionArguments
$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Task '$TaskName' registered for daily updates at $Time for $ProjectDir on $Branch from $Remote."
Write-Host "The task runs as $currentUser and starts when that user session is available."
if ($RestartAdminPanel) {
    Write-Host "After a successful update, the task will also restart the admin panel."
}
if ($InstallMt5) {
    Write-Host "After a successful update, the task will also install the MetaTrader5 package."
}