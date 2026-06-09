#!/bin/bash
# Claude Code 多行状态行脚本
# 第一行：模型名称 + 目录 + git 分支
# 第二行：上下文进度条（颜色编码）+ 成本 + 时长

input=$(cat)

# 提取基本字段
MODEL=$(echo "$input" | jq -r '.model.display_name')
EFFORT=$(echo "$input" | jq -r '.effort.level // ""')
DIR=$(echo "$input" | jq -r '.workspace.current_dir')
TOKEN_USED=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
TOKEN_MAX=$(echo "$input" | jq -r '.context_window.context_window_size // 200000')
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
DURATION_MS=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')

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
