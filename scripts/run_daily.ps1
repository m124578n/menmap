# 每日採集:static + playwright 快照,再產對比報告,最後 commit 回 git。
# 由 Windows 工作排程器每天 06:00 觸發(見 register_task.ps1)。
# 單一步驟失敗不擋後續;全程寫入 data/logs。

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$logDir = Join-Path $repo "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "$stamp.log"

function Run-Step($label, [scriptblock]$block) {
    "=== $label @ $(Get-Date -Format o) ===" | Tee-Object -FilePath $log -Append
    try {
        & $block 2>&1 | Tee-Object -FilePath $log -Append
    } catch {
        "!! $label 失敗:$_" | Tee-Object -FilePath $log -Append
    }
}

# 驗證期用量控制:預設每後端只抓前 N 家(env 可覆蓋)
if (-not $env:SNAPSHOT_LIMIT) { $env:SNAPSHOT_LIMIT = "60" }

Run-Step "snapshot static"     { uv run python -m ramen snapshot --backend static }
Run-Step "snapshot playwright" { uv run python -m ramen snapshot --backend playwright }
Run-Step "compare"             { uv run python -m ramen compare }

# commit 回 repo(bot 身分),保留快照與 diff 歷史
Run-Step "git commit" {
    git config user.name  "ramen-bot"
    git config user.email "ramen-bot@localhost"
    git add data
    git commit -m "chore(data): 每日快照 $stamp" 2>&1
    git push 2>&1
}

"=== done @ $(Get-Date -Format o) ===" | Tee-Object -FilePath $log -Append
