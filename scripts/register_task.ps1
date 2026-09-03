# 註冊 Windows 工作排程,每天台北時間 20:00 執行 run_daily.ps1。
# 手動執行一次即可:  powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
# 移除:  Unregister-ScheduledTask -TaskName "RamenDailySnapshot" -Confirm:$false

$repo = Split-Path -Parent $PSScriptRoot
$script = Join-Path $repo "scripts\run_daily.ps1"

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -NonInteractive -File `"$script`"" `
    -WorkingDirectory $repo

# 每天 20:00;電腦在睡眠就喚醒來跑(WakeToRun);關機錯過的話,開機後補跑(StartWhenAvailable)。
# 跑的期間 run_daily.ps1 會暫緩閒置自動睡眠。
$trigger = New-ScheduledTaskTrigger -Daily -At 8:00PM
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4)   # 兩後端並行全抓約 1.5 小時,留重試餘裕

Register-ScheduledTask `
    -TaskName "RamenDailySnapshot" `
    -Description "雙北拉麵地圖每日資料採集" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Force

Write-Host "已註冊工作排程 'RamenDailySnapshot'(每天 20:00)。"
Write-Host "立即測試一次:Start-ScheduledTask -TaskName RamenDailySnapshot"
