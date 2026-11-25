# register-wsl-cleanup-task.ps1 — run from Windows PowerShell (no admin needed).
# Schedules ~/.local/bin/wsl-cleanup --apply in WSL every Sunday at 12:00 and
# logs to /var/log/wsl-cleanup.log. Assumes the distro's vhdx is sparse
# (wsl --manage <distro> --set-sparse true), so trimmed space returns to C:.
param(
    [string]$Distro = "Ubuntu",
    [string]$User = "kamil"
)

$cmd = "{ date; env SUDO_USER=$User /home/$User/.local/bin/wsl-cleanup --apply; } >> /var/log/wsl-cleanup.log 2>&1"
$action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-d $Distro -u root -- sh -c `"$cmd`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 12:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName "WSL weekly cleanup" -Force `
    -Description "Runs wsl-cleanup --apply in $Distro and trims the sparse vhdx" `
    -Action $action -Trigger $trigger -Settings $settings | Out-Null
Get-ScheduledTask -TaskName "WSL weekly cleanup" | Get-ScheduledTaskInfo | Select-Object TaskName, NextRunTime
