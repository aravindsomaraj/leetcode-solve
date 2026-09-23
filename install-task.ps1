param([string]$At = "05:40", [string]$TaskName = "LeetCode Daily Runner")
$ErrorActionPreference = "Stop"
$projectDir = $PSScriptRoot
$launcher = (Get-Command py.exe -ErrorAction Stop).Source
if (-not (Test-Path (Join-Path $projectDir "config.json"))) {
    throw "Create config.json first; see README.md."
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw "Task already exists. Edit it in Task Scheduler or remove it before reinstalling."
}
$action = New-ScheduledTaskAction -Execute $launcher `
    -Argument ('-3 "' + (Join-Path $projectDir "bot.py") + '" run') `
    -WorkingDirectory $projectDir
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 60) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 30)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Run the daily LeetCode solver. Time uses this computer's local timezone." | Out-Null
Write-Host "Installed '$TaskName' for $At LOCAL time. Default assumes India Standard Time."
Write-Host "Runs while your Windows user is signed in, including when the screen is locked."
Write-Host "See README to run while signed out. Logs: $projectDir\runs\bot.log"
