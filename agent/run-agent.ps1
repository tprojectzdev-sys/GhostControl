<#
.SYNOPSIS
  Loads .env, ensures the venv is ready, and runs the agent.

  Used both interactively and by the scheduled task installed by
  install-task.ps1. Logs to logs\agent.log so you can tail it with:
    Get-Content -Wait .\logs\agent.log
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$logsDir = Join-Path $ProjectDir "logs"
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
$logFile = Join-Path $logsDir "agent.log"

function Load-DotEnv($path) {
    if (-not (Test-Path $path)) {
        throw ".env not found at $path. Copy .env.example to .env and fill it in."
    }
    Get-Content $path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { return }
        $name  = $line.Substring(0, $eq).Trim()
        $value = $line.Substring($eq + 1).Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

Load-DotEnv (Join-Path $ProjectDir ".env")

$venvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtualenv missing. Run:  python -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; pip install -r requirements.txt"
}

# Run forever; the scheduled task settings will restart on failure.
& $venvPython -m axon_agent 2>&1 | Tee-Object -FilePath $logFile -Append
exit $LASTEXITCODE
