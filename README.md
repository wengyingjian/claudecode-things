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

- [jq](https://stedolan.github.io/jq/)（用于解析 JSON 输入）

```bash
# macOS
brew install jq

# Ubuntu / Debian
sudo apt install jq

# CentOS / RHEL
sudo yum install jq
```

### 使用方法

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

### 卸载

```bash
rm ~/.claude/statusline.sh
# 然后从 ~/.claude/settings.json 中删除 statusLine 配置
```
