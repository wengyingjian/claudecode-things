# Claude Code 多行状态行脚本 (PowerShell 版)
# 第一行：模型名称 + 推理等级 + 目录 + git 分支
# 第二行：上下文进度条（颜色编码）+ token 用量 + 时长

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 读取 stdin JSON 输入
$jsonStr = $input | Out-String
$data = $jsonStr | ConvertFrom-Json

# 提取基本字段
$model = $data.model.display_name
$effort = if ($data.effort -and $data.effort.level) { $data.effort.level } else { "" }
$dir = $data.workspace.current_dir
$tokenUsed = if ($data.context_window.total_input_tokens) { $data.context_window.total_input_tokens } else { 0 }
$tokenMax = if ($data.context_window.context_window_size) { $data.context_window.context_window_size } else { 200000 }
$pctRaw = if ($data.context_window.used_percentage) { $data.context_window.used_percentage } else { 0 }
$pct = [math]::Floor($pctRaw)
$durationMs = if ($data.cost.total_duration_ms) { $data.cost.total_duration_ms } else { 0 }

# ANSI 颜色
$esc = [char]27
$cyan = "${esc}[36m"
$green = "${esc}[38;5;46m"
$yellow = "${esc}[38;5;214m"
$red = "${esc}[38;5;196m"
$reset = "${esc}[0m"

# 根据上下文使用率选择进度条颜色
if ($pct -ge 60) { $barColor = $red }
elseif ($pct -ge 40) { $barColor = $yellow }
else { $barColor = $green }

# 构建进度条（10 格宽）
$filled = [math]::Floor($pct / 10)
$empty = 10 - $filled
$bar = ("█" * $filled) + ("░" * $empty)

# Token 格式化
$tokenUsedK = [math]::Floor($tokenUsed / 1000)
$tokenMaxK = [math]::Floor($tokenMax / 1000)
$tokenFmt = "${tokenUsedK}k/${tokenMaxK}k"

# 时长格式化
$mins = [math]::Floor($durationMs / 60000)
$secs = [math]::Floor(($durationMs % 60000) / 1000)

# 目录名（取最后一级）
$dirName = Split-Path $dir -Leaf

# Git 分支信息
$branch = ""
try {
    $null = git rev-parse --git-dir 2>$null
    if ($LASTEXITCODE -eq 0) {
        $branchRaw = git branch --show-current 2>$null
        if ($branchRaw) {
            $branch = " | 🌿 $branchRaw"
        }
    }
} catch {}

# 推理等级颜色
$effortFmt = ""
if ($effort -and $effort -ne "null") {
    switch ($effort) {
        "low"    { $effortColor = "${esc}[38;5;39m" }
        "medium" { $effortColor = "${esc}[38;5;46m" }
        "high"   { $effortColor = "${esc}[38;5;214m" }
        "max"    { $effortColor = "${esc}[38;5;196m" }
        default  { $effortColor = "${esc}[38;5;245m" }
    }
    $effortFmt = "${effortColor}[${effort}]${reset}"
}

# 第一行：模型 + 推理等级 + 目录 + git 分支
Write-Host "${cyan}[$model]${reset}${effortFmt} 📁 $dirName$branch"

# 第二行：进度条 + token 用量 + 时长
Write-Host "${barColor}$bar${reset} $pct% $tokenFmt | ⏱️ ${mins}m ${secs}s"
