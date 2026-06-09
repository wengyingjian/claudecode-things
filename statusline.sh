#!/bin/bash
# Claude Code 多行状态行脚本
# 第一行：模型名称 + 目录 + git 分支
# 第二行：上下文进度条（颜色编码）+ 成本 + 时长
#
# 依赖：jq（推荐）或 Python 3（自动回退）
# 在 Windows Git Bash 环境中，若未安装 jq，脚本将自动使用 Python 解析 JSON。

input=$(cat)

# JSON 解析：优先使用 jq，若不可用则回退到 Python
_HAS_JQ=true
command -v jq >/dev/null 2>&1 || _HAS_JQ=false

_json_extract() {
    local path="$1"
    local default="${2:-}"

    if $_HAS_JQ; then
        echo "$input" | jq -r "$path // \"${default}\"" 2>/dev/null
    else
        local pypath
        pypath=$(echo "$path" | sed 's/\.\([0-9][0-9]*\)$/[\1]/g; s/\./["/g; s/^/d/; s/$/]/')
        _SL_PATH="$pypath" _SL_DEFAULT="$default" _SL_INPUT="$input" \
            python3 -c '
import json, os
d = json.loads(os.environ["_SL_INPUT"])
try:
    r = eval(os.environ["_SL_PATH"])
    print("" if r is None else r)
except:
    df = os.environ.get("_SL_DEFAULT", "")
    print(df)
' 2>/dev/null
    fi
}

# 提取基本字段
MODEL=$(_json_extract '.model.display_name')
EFFORT=$(_json_extract '.effort.level')
DIR=$(_json_extract '.workspace.current_dir')
TOKEN_USED=$(_json_extract '.context_window.total_input_tokens' '0')
TOKEN_MAX=$(_json_extract '.context_window.context_window_size' '200000')
PCT=$(_json_extract '.context_window.used_percentage' '0' | cut -d. -f1)
DURATION_MS=$(_json_extract '.cost.total_duration_ms' '0')

# ANSI 颜色定义
CYAN='\033[36m'; GREEN='\033[38;5;46m'; YELLOW='\033[38;5;214m'; RED='\033[38;5;196m'; RESET='\033[0m'

# 根据上下文使用率选择进度条颜色
if [ "$PCT" -ge 60 ]; then BAR_COLOR="$RED"
elif [ "$PCT" -ge 40 ]; then BAR_COLOR="$YELLOW"
else BAR_COLOR="$GREEN"; fi

# 构建进度条（10 格宽）
FILLED=$((PCT / 10)); EMPTY=$((10 - FILLED))
printf -v FILL "%${FILLED}s"; printf -v PAD "%${EMPTY}s"
BAR="${FILL// /█}${PAD// /░}"

# Token 格式化（10000 → 10k，200000 → 200k）
TOKEN_USED_K=$((TOKEN_USED / 1000))
TOKEN_MAX_K=$((TOKEN_MAX / 1000))
TOKEN_FMT="${TOKEN_USED_K}k/${TOKEN_MAX_K}k"

# 时长格式化（毫秒 → 分:秒）
MINS=$((DURATION_MS / 60000)); SECS=$(((DURATION_MS % 60000) / 1000))

# Git 分支信息
BRANCH=""
git rev-parse --git-dir > /dev/null 2>&1 && BRANCH=" | 🌿 $(git branch --show-current 2>/dev/null)"

# 推理等级显示（蓝→绿→橙→红）
EFFORT_FMT=""
if [ -n "$EFFORT" ] && [ "$EFFORT" != "null" ]; then
  case "$EFFORT" in
    low)    EFFORT_COLOR='\033[38;5;39m' ;;
    medium) EFFORT_COLOR='\033[38;5;46m' ;;
    high)   EFFORT_COLOR='\033[38;5;214m' ;;
    max)    EFFORT_COLOR='\033[38;5;196m' ;;
    *)      EFFORT_COLOR='\033[38;5;245m' ;;
  esac
  EFFORT_FMT="${EFFORT_COLOR}[${EFFORT}]${RESET}"
fi

# 第一行：模型 + 推理等级 + 目录 + git 分支
echo -e "${CYAN}[$MODEL]${RESET}${EFFORT_FMT} 📁 ${DIR##*/}$BRANCH"

# 第二行：进度条 + token 用量 + 时长
echo -e "${BAR_COLOR}${BAR}${RESET} ${PCT}% ${TOKEN_FMT} | ⏱️ ${MINS}m ${SECS}s"
