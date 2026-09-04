# 每日採集:static + playwright 快照 → 對比報告 → publish(D1 增量)→ commit/push 回 git(→ Pages 自動建置)。
# 由 Windows 工作排程器每天 20:00 觸發(見 register_task.ps1)。
# 單一步驟失敗不擋後續;全程寫入 data/logs。

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# Python/git 輸出都是 UTF-8;PowerShell 5.1 預設用 ANSI(CP950)解碼原生程式輸出,
# 會把中文 log 打成亂碼,這裡把主控台編碼切成 UTF-8。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# 跑的期間不讓電腦「閒置自動睡眠」(ES_CONTINUOUS | ES_SYSTEM_REQUIRED),結束時解除。
# 註:手動按睡眠仍會睡;醒來後兩個快照程序會接著跑,中間幾家可能失敗(逐店 commit,進度不丟)。
$power = Add-Type -Namespace Ramen -Name Power -PassThru -MemberDefinition `
    '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
$null = $power::SetThreadExecutionState([uint32]2147483649)   # 0x80000001(PS 5.1 的 0x8... 字面值會變負數,用十進位)

$logDir = Join-Path $repo "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "$stamp.log"

# 寫 log:轉成純文字(stderr 進來的 ErrorRecord 只留訊息本身,不帶 PowerShell 位置資訊),
# 檔案用 UTF-8(Tee-Object/Out-File 在 5.1 預設是 UTF-16)。
function Log {
    param([Parameter(ValueFromPipeline = $true)] $line)
    process {
        $text = if ($line -is [System.Management.Automation.ErrorRecord]) {
            $line.Exception.Message
        } else { "$line" }
        Write-Host $text
        $text | Out-File -FilePath $log -Append -Encoding utf8
    }
}

function Run-Step($label, [scriptblock]$block) {
    "=== $label @ $(Get-Date -Format o) ===" | Log
    try {
        & $block 2>&1 | Log
    } catch {
        "!! $label 失敗:$_" | Log
    }
}

# 每日用量(env 可覆蓋;空字串 = 全抓):
# - static 全抓 591 家(每家約 6 秒,約 50 分鐘):營業狀態/評分天天保鮮
# - playwright 每天輪 100 家(每家約 8 秒,約 15 分鐘):評論/菜單照/貼文不會天天變,
#   約 6 天輪完一輪。有 limit 就會輪替:優先抓從沒抓過/最久沒抓的店
#   (見 ramen/snapshot.py 的 _pick_entries)。被降級/失敗變多時再調小。
if ($null -eq $env:SNAPSHOT_LIMIT_STATIC)     { $env:SNAPSHOT_LIMIT_STATIC = "" }
if ($null -eq $env:SNAPSHOT_LIMIT_PLAYWRIGHT) { $env:SNAPSHOT_LIMIT_PLAYWRIGHT = "100" }
Remove-Item Env:SNAPSHOT_LIMIT -ErrorAction SilentlyContinue   # 避免舊的通用 limit 蓋過

# 兩個後端「同時」跑(各自節流,DB 用 WAL + 逐店 commit 所以能並寫)。
# 各自的輸出直接由 Python 以 UTF-8 寫到獨立 log(data/logs/{date}-{backend}.log),
# 主 log 只記啟動/結束與摘要。
function Start-Snapshot($backend, $limit) {
    $sub = Join-Path $logDir "$stamp-$backend.log"
    $cmd = "uv run python -m ramen snapshot --backend $backend"
    if ($limit) { $cmd += " --limit $limit" }
    "=== snapshot $backend 啟動 @ $(Get-Date -Format o)(limit=$(if ($limit) { $limit } else { '全抓' }))→ $sub ===" | Log
    $p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "$cmd >> `"$sub`" 2>&1" `
        -WorkingDirectory $repo -NoNewWindow -PassThru
    $null = $p.Handle   # 先摸一下 Handle,結束後才讀得到 ExitCode(PowerShell 5.1 的老毛病)
    [pscustomobject]@{ Backend = $backend; Process = $p; Log = $sub }
}

# 每週(星期日)重新搜尋一次 seed,放在快照「之前」讓新店當天就被抓:
# 新店追加並記 added_at(新店雷達)、既有店更新名稱/地址/座標、搜不到的不刪只計數。
# 報告在 data/diff/{date}-seed.md。$env:SEED_REFRESH = "1" 強制跑、"0" 跳過。
$refreshSeed = if ($env:SEED_REFRESH) { $env:SEED_REFRESH -eq "1" } else { (Get-Date).DayOfWeek -eq [DayOfWeek]::Sunday }
if ($refreshSeed) {
    Run-Step "seed refresh" { uv run python -m ramen seed --refresh 2>&1 }
}

$jobs = @(
    (Start-Snapshot "static"     $env:SNAPSHOT_LIMIT_STATIC),
    (Start-Snapshot "playwright" $env:SNAPSHOT_LIMIT_PLAYWRIGHT)
)
$jobs | ForEach-Object { $_.Process } | Wait-Process
foreach ($j in $jobs) {
    $code = $j.Process.ExitCode
    "=== snapshot $($j.Backend) 結束 @ $(Get-Date -Format o),exit=$code ===" | Log
    if (Test-Path $j.Log) { Get-Content $j.Log -Encoding UTF8 -Tail 2 | Log }
    if ($code -ne 0) { "!! snapshot $($j.Backend) 失敗(exit=$code),詳見 $($j.Log)" | Log }
}

Run-Step "compare"             { uv run python -m ramen compare }

# publish:把當天變動推上線(本機 SQLite 是正本,雲端是複本)。
# - D1:只推當天新增/取代的列(scripts/publish_d1.py,冪等,失敗明天可重推)
# - Pages:只重新產 shops.json;下面 git push 後 Cloudflare Pages 會自己從 GitHub 建置部署
#   (專案已接 Git,只在 web/ 有變動時建置;shops.json 天天變所以天天建)
# 設 $env:PUBLISH="0" 可跳過 D1 推送(例如手動測試時)。
if ($env:PUBLISH -ne "0") {
    Run-Step "publish d1" { Set-Location (Join-Path $repo "worker"); npm run db:publish 2>&1; Set-Location $repo }
}
Run-Step "export shops.json" { uv run python scripts/export_web_data.py 2>&1 }

# commit 回 repo(bot 身分),保留快照與 diff 歷史;shops.json 跟著進 git,和線上一致
Run-Step "git commit" {
    git add data web/public/shops.json
    # -c 只對這次 commit 生效,不改 repo 的 user.name/email
    git -c user.name=ramen-bot -c user.email=ramen-bot@localhost `
        commit -m "chore(data): 每日快照 $stamp" 2>&1
    git push 2>&1
}

"=== done @ $(Get-Date -Format o) ===" | Log
$null = $power::SetThreadExecutionState([uint32]2147483648)   # 0x80000000:解除,恢復原本的睡眠設定
