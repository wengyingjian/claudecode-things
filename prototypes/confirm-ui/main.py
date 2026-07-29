"""
确认 UI 原型 — 入口。

用法:
  uv run python3 prototypes/confirm-ui/

原型问题:
  逐条确认 + 外部编辑器编辑 + 拒绝的交互流程是否顺畅？
  用户基于展示信息能否快速做出决策？
"""
from state import ConfirmState, Suggestion
from tui import run

# ── 模拟分析 session 返回的 5 条建议 ──
TEST_SUGGESTIONS = [
    Suggestion(
        id=1,
        summary="添加 Python 编码风格约定",
        description="建议在 CLAUDE.md 中添加：使用 uv run python3 而非系统 pip",
        target_file="~/.claude/CLAUDE.md",
        category="code_convention",
        content=(
            "## Python 编码风格\n"
            "- 使用 `uv run python3` 运行脚本\n"
            "- 禁止魔法数字，使用常量或枚举"
        ),
        action="append",
    ),
    Suggestion(
        id=2,
        summary="改进 statusline.sh 的错误处理",
        description="当前脚本在 git 目录外执行时会静默失败，建议添加分支检测",
        target_file="statusline.sh",
        category="code_convention",
        content=(
            "# 在脚本顶部添加错误处理\n"
            'set -euo pipefail\n'
            "\n"
            "# 检查是否在 git 仓库内\n"
            'if ! git rev-parse --git-dir > /dev/null 2>&1; then\n'
            '    echo "no git"\n'
            "    exit 0\n"
            "fi"
        ),
        action="replace",
    ),
    Suggestion(
        id=3,
        summary="记录用户偏好：使用 uv 管理 Python 依赖",
        description="基于本次对话，用户偏好使用 uv 而非 pip，应记录到 memory",
        target_file="~/.claude/projects/claudecode-things/memory/uv-preference.md",
        category="memory",
        content=(
            "---\n"
            "name: uv-preference\n"
            "description: 用户偏好使用 uv 管理 Python 依赖\n"
            "metadata:\n"
            "  type: user\n"
            "---\n"
            "\n"
            "用户偏好使用 `uv run python3` 运行 Python 脚本，"
            "使用 `uv add` 添加依赖，而非系统 pip。"
        ),
        action="new",
    ),
    Suggestion(
        id=4,
        summary="添加文件头部注释规范",
        description="项目缺少统一的文件头部注释格式，建议在 CLAUDE.md 中约定",
        target_file="~/.claude/CLAUDE.md",
        category="code_convention",
        content=(
            "## 文件头部注释\n"
            "- 每个源文件应以简短注释开头，说明文件用途\n"
            "- 格式: `# <filename> — <一句话描述>`"
        ),
        action="append",
    ),
    Suggestion(
        id=5,
        summary="skill prompt 应添加输入验证说明",
        description="statusline skill 的 SKILL.md 缺少对输入参数的验证描述",
        target_file="~/.claude/skills/statusline/SKILL.md",
        category="skill_prompt",
        content=(
            "## 输入验证\n"
            "- `--shell` 参数必须为 `bash`, `zsh`, `powershell` 之一\n"
            "- 无效输入时返回错误提示而非静默降级"
        ),
        action="append",
    ),
]


def main():
    state = ConfirmState(suggestions=TEST_SUGGESTIONS)
    run(state)

    # 输出最终决策结果供后续脚本使用
    print("\n决策汇总:")
    for s in TEST_SUGGESTIONS:
        d = state.decisions[s.id]
        edited = state.edited_content.get(s.id)
        marker = {
            "ACCEPTED": "✅",
            "EDITED": "✏️",
            "REJECTED": "❌",
            "SKIPPED": "⏭️",
        }.get(d.name, "?")
        extra = f" (修改后)" if edited else ""
        print(f"  {marker} [{d.name}] {s.summary}{extra}")


if __name__ == "__main__":
    main()
