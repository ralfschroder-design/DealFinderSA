#Requires -Version 5.1
<#
.SYNOPSIS
    Registers a Windows Scheduled Task that runs DealFinderSA daily.

.DESCRIPTION
    FOR LOCAL TESTING ONLY. Production deployments use cron via scripts/run_scrape.sh
    on a Linux server running from git.

    Registers (or replaces) a task named "DealFinderSA-scrape" that calls the repo's
    venv Python with `-m dealfinder.cli run-scrape`, with the working directory set to
    the repo root. Idempotent — safe to re-run; an existing task is replaced.

.PARAMETER RunTime
    Daily trigger time in HH:mm format. Default: "07:00".

.EXAMPLE
    .\register_scheduled_task.ps1
    # Registers task at 07:00

.EXAMPLE
    .\register_scheduled_task.ps1 -RunTime "08:30"
    # Registers task at 08:30

.NOTES
    To unregister:  Unregister-ScheduledTask -TaskName "DealFinderSA-scrape" -Confirm:$false
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter()]
    [ValidatePattern('^\d{2}:\d{2}$')]
    [string]$RunTime = "07:00"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName    = "DealFinderSA-scrape"
$RepoRoot    = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython  = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "venv not found at '$VenvPython'. Run 'python -m venv .venv && pip install -e .' first."
    exit 1
}

$Action  = New-ScheduledTaskAction `
    -Execute $VenvPython `
    -Argument "-m dealfinder.cli run-scrape" `
    -WorkingDirectory $RepoRoot

$Trigger = New-ScheduledTaskTrigger -Daily -At $RunTime

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Remove existing task silently so registration is idempotent
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    if ($PSCmdlet.ShouldProcess($TaskName, "Unregister existing scheduled task")) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed existing task '$TaskName'."
    }
}

if ($PSCmdlet.ShouldProcess($TaskName, "Register scheduled task")) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action   $Action `
        -Trigger  $Trigger `
        -Settings $Settings `
        -Description "DealFinderSA daily scrape (LOCAL TESTING). Production uses cron." `
        -RunLevel Highest `
        -Force | Out-Null

    Write-Host ""
    Write-Host "Task registered: $TaskName"
    Write-Host "  Python  : $VenvPython"
    Write-Host "  Args    : -m dealfinder.cli run-scrape"
    Write-Host "  Workdir : $RepoRoot"
    Write-Host "  Schedule: daily at $RunTime"
    Write-Host ""
    Write-Host "To unregister:"
    Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
}
