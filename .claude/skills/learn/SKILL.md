---
name: learn
description: 自学习 skill — 用户在对话中说"学习"，附带学习指令和要学习的文件路径，脚本自动启动分析 session，产出改进建议，用户逐条确认后写入目标文件。
---

# /learn — 自学习 Skill

## 触发方式

用户在对话中使用 `/learn <学习指令> --apply-to <目标路径>` 触发。

## 目标类型

| 类型 | 触发场景 | 写入位置 | 操作方式 |
|------|----------|----------|----------|
| **Skill Prompt** | 文件路径包含 `SKILL.md` 或 `.claude/skills/` | 目标 SKILL.md | 按 ## 节追加/替换 |
| **CLAUDE.md** | 文件路径为 `CLAUDE.md` | 目标 CLAUDE.md | 按 ## 节追加/替换 |
| **Memory** | 文件路径包含 `memory` | `~/.claude/projects/<project>/memory/` | 新建文件 + MEMORY.md 索引追加 |
| **代码约定** | 其他文件 | CLAUDE.md `## 编码风格` 节 | 追加代码约定条目 |

## 执行流程

1. 解析 `/learn <指令> --apply-to <路径>`
2. 读取目标文件内容
3. 通过 Anthropic API 启动分析 session（Sonnet 5，无 tools）
4. 解析 JSON 建议列表
5. 交互式确认（a=接受 / e=编辑 / r=拒绝 / q=退出）
6. SafeFileWriter 安全写入确认的建议

## 依赖

- Python 3.11+
- uv (包管理)
- anthropic SDK
- ANTHROPIC_API_KEY 环境变量

## 相关 Skill

- `skill-optimizer`：修复单个 skill 的行为问题。如果 `/learn` 产生的改进涉及 skill 的行为修改，应使用 skill-optimizer 进行修复而非直接修改 SKILL.md。
