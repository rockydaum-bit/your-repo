$ErrorActionPreference = 'Stop'
$logPath = "D:\textautonomous_media_engine\scripts\task_registration.log"

function Register-EngineTask {
    param(
        [string]$TaskName,
        [string]$ScriptPath,
        [string]$Channel = "channel_001_ai_tools",
        [string]$Schedule = "Daily",
        [string]$Time = "6:00AM"
    )
    $action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File $ScriptPath -Channel $Channel"
    if ($Schedule -eq "Daily") {
        $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    } elseif ($Schedule -eq "Weekly") {
        $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $Time
    } else {
        throw "Unsupported schedule: $Schedule"
    }
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -RunLevel Highest
    Add-Content -Path $logPath -Value "[$(Get-Date -Format o)] Registered $TaskName for $Channel ($Schedule $Time) via $ScriptPath"
}

# Register daily task
Register-EngineTask -TaskName "AutonomousMediaEngine-Daily" -ScriptPath "D:\textautonomous_media_engine\scripts\run_daily.ps1" -Schedule "Daily" -Time "6:00AM"

# Register weekly apply task
Register-EngineTask -TaskName "AutonomousMediaEngine-Weekly-Autopromote" -ScriptPath "D:\textautonomous_media_engine\scripts\score_weekly_apply.ps1" -Schedule "Weekly" -Time "7:00AM"
