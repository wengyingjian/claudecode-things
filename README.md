# Claude Code Things

Claude Code 实用工具和配置集合。

## 状态栏（Status Line）

为 Claude Code 添加多行状态栏，实时显示模型、上下文用量、会话时长等信息。

### 效果预览

```
[qwen3.7-max][high] 📁 my-project | 🌿 main
██████░░░░ 58% 116k/200k | ⏱️ 12m 34s
```

**第一行：**
- `[模型名称]` — 当前使用的模型（青色）
- `[推理等级]` — low/medium/high/max（蓝→绿→橙→红）
- `📁 目录名` — 当前工作目录
- `🌿 git 分支` — 当前 Git 分支（如在 Git 仓库中）

**第二行：**
- 上下文进度条 — 10 格宽度，颜色随使用率变化：
  - 🟢 绿色：0%–39%
  - 🟡 黄色：40%–59%
  - 🔴 红色：60%+
- Token 用量 — 格式如 `116k/200k`
- 会话时长 — 格式如 `12m 34s`

### 前置要求

**macOS / Linux：**
- [jq](https://stedolan.github.io/jq/)（用于解析 JSON 输入）

```bash
# macOS
brew install jq

# Ubuntu / Debian
sudo apt install jq

# CentOS / RHEL
sudo yum install jq
```

**Windows：**
- PowerShell 5.1+（Windows 自带）或 PowerShell 7+（推荐）
- 无需额外依赖，PowerShell 内置 JSON 解析

### 使用方法

#### macOS / Linux（Bash 版）

1. 将 `statusline.sh` 复制到 `~/.claude/` 目录：

```bash
cp statusline.sh ~/.claude/statusline.sh
chmod +x ~/.claude/statusline.sh
```

2. 编辑 `~/.claude/settings.json`，添加 `statusLine` 配置：

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh"
  }
}
```

3. 重启 Claude Code 即可生效。

#### Windows（PowerShell 版）

1. 将 `statusline.ps1` 复制到 `%USERPROFILE%\.claude\` 目录：

```powershell
Copy-Item statusline.ps1 "$env:USERPROFILE\.claude\statusline.ps1"
```

2. 编辑 `%USERPROFILE%\.claude\settings.json`，添加 `statusLine` 配置。路径中使用**正斜杠**（Git Bash 会将反斜杠视为转义字符）：

```json
{
  "statusLine": {
    "type": "command",
    "command": "powershell -NoProfile -File C:/Users/你的用户名/.claude/statusline.ps1"
  }
}
```

> **提示：** 如果你安装了 PowerShell 7+，可以用 `pwsh` 替代 `powershell` 以获得更好的性能：
> ```json
> {
>   "statusLine": {
>     "type": "command",
>     "command": "pwsh -NoProfile -File C:/Users/你的用户名/.claude/statusline.ps1"
>   }
> }
> ```

3. 重启 Claude Code 即可生效。

> **注意：** 如果 Windows 执行策略阻止脚本运行，请先放宽策略：
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

### 卸载

**macOS / Linux：**

```bash
rm ~/.claude/statusline.sh
# 然后从 ~/.claude/settings.json 中删除 statusLine 配置
```

**Windows：**

```powershell
Remove-Item "$env:USERPROFILE\.claude\statusline.ps1"
# 然后从 settings.json 中删除 statusLine 配置
```

## 参考文档

- [状态行完整参考文档](docs/statusline-reference.md) — Claude Code 状态行的完整配置指南、可用字段、示例和故障排除
