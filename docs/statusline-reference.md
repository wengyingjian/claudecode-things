# 自定义你的状态行

> 配置自定义状态栏以监控 Claude Code 中的上下文窗口使用情况、成本和 git 状态

状态行是 Claude Code 底部的可自定义栏，可以运行你配置的任何 shell 脚本。它通过 stdin 接收 JSON 会话数据，并显示你的脚本打印的任何内容，为你提供一个持久的、一目了然的上下文使用情况、成本、git 状态或任何其他你想跟踪的内容的视图。

状态行在以下情况下很有用：

* 你想在工作时监控上下文窗口使用情况
* 你需要跟踪会话成本
* 你在多个会话中工作，需要区分它们
* 你希望 git 分支和状态始终可见

## 设置状态行

使用 `/statusline` 命令让 Claude Code 为你生成脚本，或手动创建脚本并将其添加到你的设置中。

### 使用 /statusline 命令

`/statusline` 命令接受描述你想显示的内容的自然语言指令。Claude Code 在 `~/.claude/` 中生成脚本文件并自动更新你的设置：

```
/statusline show model name and context percentage with a progress bar
```

### 手动配置状态行

将 `statusLine` 字段添加到你的用户设置（`~/.claude/settings.json`，其中 `~` 是你的主目录）或项目设置。将 `type` 设置为 `"command"` 并将 `command` 指向脚本路径或内联 shell 命令。

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "padding": 2
  }
}
```

`command` 字段在 shell 中运行，所以你也可以使用内联命令而不是脚本文件。此示例使用 `jq` 解析 JSON 输入并显示模型名称和上下文百分比：

```json
{
  "statusLine": {
    "type": "command",
    "command": "jq -r '\"[\\(.model.display_name)] \\(.context_window.used_percentage // 0)% context\"'"
  }
}
```

可选的 `padding` 字段为状态行内容添加额外的水平间距（以字符为单位）。默认为 `0`。

可选的 `refreshInterval` 字段除了事件驱动的更新外，每 N 秒重新运行一次你的命令。最小值为 `1`。当你的状态行显示基于时间的数据（如时钟）或后台子代理在主会话空闲时更改 git 状态时，设置此选项。

可选的 `hideVimModeIndicator` 字段会抑制提示符下方的内置 `-- INSERT --` 文本。当你的脚本自己呈现 `vim.mode` 时，将此设置为 `true`。

### 禁用状态行

运行 `/statusline` 并要求它删除或清除你的状态行（例如，`/statusline delete`、`/statusline clear`、`/statusline remove it`）。你也可以手动从 settings.json 中删除 `statusLine` 字段。

## 逐步构建状态行

### 创建一个读取 JSON 并打印输出的脚本

Claude Code 通过 stdin 向你的脚本发送 JSON 数据。此脚本使用 `jq`，一个命令行 JSON 解析器，来提取模型名称、目录和上下文百分比，然后打印格式化的行。

将其保存到 `~/.claude/statusline.sh`：

```bash
#!/bin/bash
# Read JSON data that Claude Code sends to stdin
input=$(cat)

# Extract fields using jq
MODEL=$(echo "$input" | jq -r '.model.display_name')
DIR=$(echo "$input" | jq -r '.workspace.current_dir')
# The "// 0" provides a fallback if the field is null
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)

# Output the status line - ${DIR##*/} extracts just the folder name
echo "[$MODEL] 📁 ${DIR##*/} | ${PCT}% context"
```

### 使其可执行

```bash
chmod +x ~/.claude/statusline.sh
```

### 添加到设置

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh"
  }
}
```

## 状态行如何工作

Claude Code 运行你的脚本并通过 stdin 向其传输 JSON 会话数据。你的脚本读取 JSON，提取它需要的内容，并将文本打印到 stdout。Claude Code 显示你的脚本打印的任何内容。

### 何时更新

你的脚本在每条新的助手消息之后、`/compact` 完成后、权限模式更改时或 vim 模式切换时运行。更新在 300ms 处进行防抖。

### 你的脚本可以输出什么

* **多行**：每个 `echo` 或 `print` 语句显示为单独的行
* **颜色**：使用 ANSI 转义码，如 `\033[32m` 表示绿色
* **链接**：使用 OSC 8 转义序列使文本可点击

### 调整输出大小以适应终端

Claude Code 捕获你的脚本输出而不是直接将其连接到终端，因此 `tput cols` 和语言级宽度检测无法从脚本内部读取终端大小。改为读取 `COLUMNS` 和 `LINES` 环境变量。

## 可用数据

Claude Code 通过 stdin 向你的脚本发送以下 JSON 字段：

| 字段 | 描述 |
|------|------|
| `model.id`, `model.display_name` | 当前模型标识符和显示名称 |
| `cwd`, `workspace.current_dir` | 当前工作目录 |
| `workspace.project_dir` | 启动 Claude Code 的目录 |
| `workspace.added_dirs` | 通过 `/add-dir` 或 `--add-dir` 添加的其他目录 |
| `workspace.git_worktree` | 当前目录在使用 `git worktree add` 创建的链接 worktree 内时的 Git worktree 名称 |
| `workspace.repo.host`, `workspace.repo.owner`, `workspace.repo.name` | 从 `origin` 远程解析的存储库标识 |
| `cost.total_cost_usd` | 以美元计的估计会话成本 |
| `cost.total_duration_ms` | 自会话开始以来的总挂钟时间（毫秒） |
| `cost.total_api_duration_ms` | 等待 API 响应的总时间（毫秒） |
| `cost.total_lines_added`, `cost.total_lines_removed` | 更改的代码行数 |
| `context_window.total_input_tokens`, `context_window.total_output_tokens` | 当前在上下文窗口中的令牌计数 |
| `context_window.context_window_size` | 最大上下文窗口大小（令牌） |
| `context_window.used_percentage` | 预计算的已使用上下文窗口百分比 |
| `context_window.remaining_percentage` | 预计算的剩余上下文窗口百分比 |
| `context_window.current_usage` | 来自最后一次 API 调用的令牌计数 |
| `exceeds_200k_tokens` | 最近一次 API 响应中的总令牌计数是否超过 200k |
| `effort.level` | 当前推理工作量（`low`、`medium`、`high`、`xhigh` 或 `max`） |
| `thinking.enabled` | 是否为会话启用了扩展思考 |
| `rate_limits.five_hour.used_percentage`, `rate_limits.seven_day.used_percentage` | 消耗的 5 小时或 7 天速率限制的百分比 |
| `rate_limits.five_hour.resets_at`, `rate_limits.seven_day.resets_at` | Unix 纪元秒，当速率限制窗口重置时 |
| `session_id` | 唯一的会话标识符 |
| `session_name` | 使用 `--name` 标志或 `/rename` 设置的自定义会话名称 |
| `transcript_path` | 对话记录文件的路径 |
| `version` | Claude Code 版本 |
| `output_style.name` | 当前输出样式的名称 |
| `vim.mode` | 启用 vim 模式时的当前 vim 模式 |
| `agent.name` | 使用 `--agent` 标志或配置的代理设置运行时的代理名称 |
| `pr.number`, `pr.url` | 当前分支的开放拉取请求 |
| `pr.review_state` | 开放 PR 的审查状态 |
| `worktree.name` | 活跃 worktree 的名称 |
| `worktree.path` | worktree 目录的绝对路径 |
| `worktree.branch` | worktree 的 Git 分支名称 |
| `worktree.original_cwd` | Claude 进入 worktree 之前所在的目录 |
| `worktree.original_branch` | 进入 worktree 之前检出的 Git 分支 |

### 完整 JSON 架构

```json
{
  "cwd": "/current/working/directory",
  "session_id": "abc123...",
  "session_name": "my-session",
  "transcript_path": "/path/to/transcript.jsonl",
  "model": {
    "id": "claude-opus-4-8",
    "display_name": "Opus"
  },
  "workspace": {
    "current_dir": "/current/working/directory",
    "project_dir": "/original/project/directory",
    "added_dirs": [],
    "git_worktree": "feature-xyz",
    "repo": {
      "host": "github.com",
      "owner": "anthropics",
      "name": "claude-code"
    }
  },
  "version": "2.1.90",
  "output_style": {
    "name": "default"
  },
  "cost": {
    "total_cost_usd": 0.01234,
    "total_duration_ms": 45000,
    "total_api_duration_ms": 2300,
    "total_lines_added": 156,
    "total_lines_removed": 23
  },
  "context_window": {
    "total_input_tokens": 15500,
    "total_output_tokens": 1200,
    "context_window_size": 200000,
    "used_percentage": 8,
    "remaining_percentage": 92,
    "current_usage": {
      "input_tokens": 8500,
      "output_tokens": 1200,
      "cache_creation_input_tokens": 5000,
      "cache_read_input_tokens": 2000
    }
  },
  "exceeds_200k_tokens": false,
  "effort": {
    "level": "high"
  },
  "thinking": {
    "enabled": true
  },
  "rate_limits": {
    "five_hour": {
      "used_percentage": 23.5,
      "resets_at": 1738425600
    },
    "seven_day": {
      "used_percentage": 41.2,
      "resets_at": 1738857600
    }
  },
  "vim": {
    "mode": "NORMAL"
  },
  "agent": {
    "name": "security-reviewer"
  },
  "pr": {
    "number": 1234,
    "url": "https://github.com/anthropics/claude-code/pull/1234",
    "review_state": "pending"
  },
  "worktree": {
    "name": "my-feature",
    "path": "/path/to/.claude/worktrees/my-feature",
    "branch": "worktree-my-feature",
    "original_cwd": "/path/to/project",
    "original_branch": "main"
  }
}
```

### 上下文窗口字段

`context_window` 对象描述来自最近一次 API 响应的实时上下文窗口。

* **合并总计**（`total_input_tokens`, `total_output_tokens`）：当前在上下文窗口中的令牌
* **按组件使用情况**（`current_usage`）：相同的令牌计数按类别分解

`current_usage` 对象包含：

* `input_tokens`：当前上下文中的输入令牌
* `output_tokens`：生成的输出令牌
* `cache_creation_input_tokens`：写入缓存的令牌
* `cache_read_input_tokens`：从缓存读取的令牌

## 示例

### 上下文窗口使用情况

**Bash:**

```bash
#!/bin/bash
input=$(cat)

MODEL=$(echo "$input" | jq -r '.model.display_name')
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)

BAR_WIDTH=10
FILLED=$((PCT * BAR_WIDTH / 100))
EMPTY=$((BAR_WIDTH - FILLED))
BAR=""
[ "$FILLED" -gt 0 ] && printf -v FILL "%${FILLED}s" && BAR="${FILL// /▓}"
[ "$EMPTY" -gt 0 ] && printf -v PAD "%${EMPTY}s" && BAR="${BAR}${PAD// /░}"

echo "[$MODEL] $BAR $PCT%"
```

**Python:**

```python
#!/usr/bin/env python3
import json, sys

data = json.load(sys.stdin)
model = data['model']['display_name']
pct = int(data.get('context_window', {}).get('used_percentage', 0) or 0)

filled = pct * 10 // 100
bar = '▓' * filled + '░' * (10 - filled)

print(f"[{model}] {bar} {pct}%")
```

**Node.js:**

```javascript
#!/usr/bin/env node
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
    const data = JSON.parse(input);
    const model = data.model.display_name;
    const pct = Math.floor(data.context_window?.used_percentage || 0);

    const filled = Math.floor(pct * 10 / 100);
    const bar = '▓'.repeat(filled) + '░'.repeat(10 - filled);

    console.log(`[${model}] ${bar} ${pct}%`);
});
```

### Git 状态与颜色

**Bash:**

```bash
#!/bin/bash
input=$(cat)

MODEL=$(echo "$input" | jq -r '.model.display_name')
DIR=$(echo "$input" | jq -r '.workspace.current_dir')

GREEN='\033[32m'
YELLOW='\033[33m'
RESET='\033[0m'

if git rev-parse --git-dir > /dev/null 2>&1; then
    BRANCH=$(git branch --show-current 2>/dev/null)
    STAGED=$(git diff --cached --numstat 2>/dev/null | wc -l | tr -d ' ')
    MODIFIED=$(git diff --numstat 2>/dev/null | wc -l | tr -d ' ')

    GIT_STATUS=""
    [ "$STAGED" -gt 0 ] && GIT_STATUS="${GREEN}+${STAGED}${RESET}"
    [ "$MODIFIED" -gt 0 ] && GIT_STATUS="${GIT_STATUS}${YELLOW}~${MODIFIED}${RESET}"

    echo -e "[$MODEL] 📁 ${DIR##*/} | 🌿 $BRANCH $GIT_STATUS"
else
    echo "[$MODEL] 📁 ${DIR##*/}"
fi
```

### 成本和持续时间跟踪

**Bash:**

```bash
#!/bin/bash
input=$(cat)

MODEL=$(echo "$input" | jq -r '.model.display_name')
COST=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
DURATION_MS=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')

COST_FMT=$(printf '$%.2f' "$COST")
DURATION_SEC=$((DURATION_MS / 1000))
MINS=$((DURATION_SEC / 60))
SECS=$((DURATION_SEC % 60))

echo "[$MODEL] 💰 $COST_FMT | ⏱️ ${MINS}m ${SECS}s"
```

### 显示多行

**Bash:**

```bash
#!/bin/bash
input=$(cat)

MODEL=$(echo "$input" | jq -r '.model.display_name')
DIR=$(echo "$input" | jq -r '.workspace.current_dir')
COST=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
DURATION_MS=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')

CYAN='\033[36m'; GREEN='\033[32m'; YELLOW='\033[33m'; RED='\033[31m'; RESET='\033[0m'

if [ "$PCT" -ge 90 ]; then BAR_COLOR="$RED"
elif [ "$PCT" -ge 70 ]; then BAR_COLOR="$YELLOW"
else BAR_COLOR="$GREEN"; fi

FILLED=$((PCT / 10)); EMPTY=$((10 - FILLED))
printf -v FILL "%${FILLED}s"; printf -v PAD "%${EMPTY}s"
BAR="${FILL// /█}${PAD// /░}"

MINS=$((DURATION_MS / 60000)); SECS=$(((DURATION_MS % 60000) / 1000))

BRANCH=""
git rev-parse --git-dir > /dev/null 2>&1 && BRANCH=" | 🌿 $(git branch --show-current 2>/dev/null)"

echo -e "${CYAN}[$MODEL]${RESET} 📁 ${DIR##*/}$BRANCH"
COST_FMT=$(printf '$%.2f' "$COST")
echo -e "${BAR_COLOR}${BAR}${RESET} ${PCT}% | ${YELLOW}${COST_FMT}${RESET} | ⏱️ ${MINS}m ${SECS}s"
```

### 可点击链接

**Bash:**

```bash
#!/bin/bash
input=$(cat)

MODEL=$(echo "$input" | jq -r '.model.display_name')

REMOTE=$(git remote get-url origin 2>/dev/null | sed 's/git@github.com:/https:\/\/github.com\//' | sed 's/\.git$//')

if [ -n "$REMOTE" ]; then
    REPO_NAME=$(basename "$REMOTE")
    printf '%b' "[$MODEL] 🔗 \e]8;;${REMOTE}\a${REPO_NAME}\e]8;;\a\n"
else
    echo "[$MODEL]"
fi
```

### 速率限制使用情况

**Bash:**

```bash
#!/bin/bash
input=$(cat)

MODEL=$(echo "$input" | jq -r '.model.display_name')
FIVE_H=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
WEEK=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

LIMITS=""
[ -n "$FIVE_H" ] && LIMITS="5h: $(printf '%.0f' "$FIVE_H")%"
[ -n "$WEEK" ] && LIMITS="${LIMITS:+$LIMITS }7d: $(printf '%.0f' "$WEEK")%"

[ -n "$LIMITS" ] && echo "[$MODEL] | $LIMITS" || echo "[$MODEL]"
```

### 缓存昂贵的操作

**Bash:**

```bash
#!/bin/bash
input=$(cat)

MODEL=$(echo "$input" | jq -r '.model.display_name')
DIR=$(echo "$input" | jq -r '.workspace.current_dir')
SESSION_ID=$(echo "$input" | jq -r '.session_id')

CACHE_FILE="/tmp/statusline-git-cache-$SESSION_ID"
CACHE_MAX_AGE=5  # seconds

cache_is_stale() {
    [ ! -f "$CACHE_FILE" ] || \
    [ $(($(date +%s) - $(stat -f %m "$CACHE_FILE" 2>/dev/null || stat -c %Y "$CACHE_FILE" 2>/dev/null || echo 0))) -gt $CACHE_MAX_AGE ]
}

if cache_is_stale; then
    if git rev-parse --git-dir > /dev/null 2>&1; then
        BRANCH=$(git branch --show-current 2>/dev/null)
        STAGED=$(git diff --cached --numstat 2>/dev/null | wc -l | tr -d ' ')
        MODIFIED=$(git diff --numstat 2>/dev/null | wc -l | tr -d ' ')
        echo "$BRANCH|$STAGED|$MODIFIED" > "$CACHE_FILE"
    else
        echo "||" > "$CACHE_FILE"
    fi
fi

IFS='|' read -r BRANCH STAGED MODIFIED < "$CACHE_FILE"

if [ -n "$BRANCH" ]; then
    echo "[$MODEL] 📁 ${DIR##*/} | 🌿 $BRANCH +$STAGED ~$MODIFIED"
else
    echo "[$MODEL] 📁 ${DIR##*/}"
fi
```

## 子代理状态行

`subagentStatusLine` 设置为代理面板中显示的每个子代理渲染自定义行体。

```json
{
  "subagentStatusLine": {
    "type": "command",
    "command": "~/.claude/subagent-statusline.sh"
  }
}
```

该命令在每个刷新周期运行一次，所有可见的子代理行作为单个 JSON 对象传递到 stdin。输入包括基本钩子字段加上 `columns`（可用行宽）和 `tasks` 数组。

将一个 JSON 行写入 stdout，用于你想覆盖的每一行，形式为 `{"id": "<task id>", "content": "<row body>"}`。

## 提示

* **使用模拟输入测试**：`echo '{"model":{"display_name":"Opus"},"workspace":{"current_dir":"/home/user/project"},"context_window":{"used_percentage":25},"session_id":"test-session-abc"}' | ./statusline.sh`
* **保持输出简短**：状态栏的宽度有限，所以长输出可能会被截断或换行不当
* **缓存慢速操作**：你的脚本在活跃会话期间频繁运行，所以像 `git status` 这样的命令可能会导致延迟。请参阅缓存示例了解如何处理这个问题。

社区项目如 [ccstatusline](https://github.com/sirmalloc/ccstatusline) 和 [starship-claude](https://github.com/martinemde/starship-claude) 提供带有主题和其他功能的预构建配置。

## 故障排除

**状态行未出现**

* 验证你的脚本是可执行的：`chmod +x ~/.claude/statusline.sh`
* 检查你的脚本输出到 stdout，而不是 stderr
* 手动运行你的脚本以验证它产生输出
* 在安装了 Git Bash 的 Windows 上，`command` 路径中的反斜杠可能在脚本运行前被当作转义字符消耗。在路径中使用正斜杠。
* 如果 `disableAllHooks` 在你的设置中设置为 `true`，状态行也会被禁用。删除此设置或将其设置为 `false` 以重新启用。
* 运行 `claude --debug` 以记录会话中第一次状态行调用的退出代码和 stderr
* 要求 Claude 读取你的设置文件并直接执行 `statusLine` 命令以显示错误

**状态行显示 `--` 或空值**

* 在第一次 API 响应完成之前，字段可能为 `null`
* 在你的脚本中使用回退处理 null 值，如 jq 中的 `// 0`
* 如果值在多条消息后仍然为空，请重新启动 Claude Code

**上下文百分比显示意外值**

* 使用 `used_percentage` 获得最简单的准确上下文状态
* 上下文百分比可能与 `/context` 输出不同，因为每个的计算时间不同

**OSC 8 链接不可点击**

* 验证你的终端支持 OSC 8 超链接（iTerm2、Kitty、WezTerm）
* Terminal.app 不支持可点击链接
* 如果链接文本出现但不可点击，Claude Code 可能未检测到你的终端中的超链接支持。在启动 Claude Code 之前设置 `FORCE_HYPERLINK` 环境变量：
  ```bash
  FORCE_HYPERLINK=1 claude
  ```
* SSH 和 tmux 会话可能根据配置剥离 OSC 序列
* 如果转义序列显示为文字文本，使用 `printf '%b'` 而不是 `echo -e`

**工作区信任需要**

* 状态行命令仅在你接受当前目录的工作区信任对话框时运行。如果未接受信任，你将看到通知 `statusline skipped · restart to fix`。重新启动 Claude Code 并接受信任提示以启用它。

**脚本错误或挂起**

* 以非零代码退出或不产生输出的脚本会导致状态行变为空白
* 慢速脚本会阻止状态行更新，直到它们完成。保持脚本快速以避免陈旧输出。
* 如果在慢速脚本运行时触发新的更新，正在进行的脚本会被取消
* 在配置之前使用模拟输入独立测试你的脚本

**通知共享状态行行**

* 系统通知显示在与你的状态行相同行的右侧
* 在窄终端上，这些通知可能会截断你的状态行输出

## Windows 配置

在 Windows 上，Claude Code 通过 Git Bash 运行状态行命令（如果已安装），或在没有 Git Bash 时通过 PowerShell 运行。

Git Bash 将未引用的反斜杠视为转义字符，因此在 `command` 字符串中使用正斜杠编写文件路径。

要将 PowerShell 脚本作为状态行运行：

```json
{
  "statusLine": {
    "type": "command",
    "command": "powershell -NoProfile -File C:/Users/username/.claude/statusline.ps1"
  }
}
```

```powershell
$input_json = $input | Out-String | ConvertFrom-Json
$cwd = $input_json.cwd
$model = $input_json.model.display_name
$used = $input_json.context_window.used_percentage
$dirname = Split-Path $cwd -Leaf

if ($used) {
    Write-Host "$dirname [$model] ctx: $used%"
} else {
    Write-Host "$dirname [$model]"
}
```

---

> 参考来源：https://code.claude.com/docs/llms.txt
> 文档版本：基于 Claude Code v2.1.153+
