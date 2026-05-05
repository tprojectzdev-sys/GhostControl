<#
.SYNOPSIS
  Installs Axon Remote PC Agent as a per-user Scheduled Task that runs at
  login and survives logoff/login cycles.

.DESCRIPTION
  We use Task Scheduler instead of a Windows Service for two reasons:
    1. App launches need the interactive desktop session. Services run in
       session 0 by default, where windows are invisible to you.
    2. Task Scheduler is built into Windows. No NSSM required.

  The task runs python -m axon_agent with environment variables loaded from
  the .env file in this folder.

.USAGE
  # 1. Install Python 3.11+ and ensure `python` is on PATH.
  # 2. cd agent
  # 3. python -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; pip install -r requirements.txt
  # 4. Copy .env.example to .env and fill in the relay URL + agent token.
  # 5. Open PowerShell *as Administrator*, then:
  #      .\install-task.ps1
  # 6. Log out and back in, OR run:  Start-ScheduledTask -TaskName 'AxonAgent'

.NOTES
  Requires PowerShell 5.1+ (any modern Windows).
#>

[CmdletBinding()]
param(
    [string] $TaskName = "AxonAgent",
    [string] $ProjectDir = (Resolve-Path "$PSScriptRoot").Path
)

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must run as Administrator. Right-click PowerShell -> Run as Administrator."
    exit 1
}

$venvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$envFile    = Join-Path $ProjectDir ".env"
$logsDir    = Join-Path $ProjectDir "logs"

if (-not (Test-Path $venvPython)) {
    Write-Error "Virtualenv not found at $venvPython. Run: python -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path $envFile)) {
    Write-Error "$envFile is missing. Copy .env.example to .env and fill it in."
    exit 1
}

New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

$launcher = Join-Path $ProjectDir "run-agent.ps1"
$runArg   = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcher`""

$action    = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $runArg -WorkingDirectory $ProjectDir
$trigger1  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger2  = New-ScheduledTaskTrigger -AtStartup
$settings  = New-ScheduledTaskSettingsSet `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
                -RestartInterval (New-TimeSpan -Minutes 1) -RestartCount 999
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger @($trigger1, $trigger2) `
    -Settings $settings -Principal $principal `
    -Description "Axon Remote — Windows agent that connects outbound to the cloud relay."

Write-Host ""
Write-Host "Installed scheduled task '$TaskName'." -ForegroundColor Green
Write-Host "Starting it now..."
Start-ScheduledTask -TaskName $TaskName
Write-Host "Tail the log: Get-Content -Wait '$logsDir\agent.log'" -ForegroundColor Cyan
