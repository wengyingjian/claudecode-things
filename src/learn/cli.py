"""
/learn CLI 入口 — 解析参数、启动分析、确认、写入。
"""
import argparse
import sys
from pathlib import Path

from .state import ConfirmState, Decision
from .analyzer import run_analysis, AnalysisError
from .tui import run_tui
from .writers.skill_writer import SkillWriter
from .writers.claude_writer import ClaudeMdWriter, resolve_claude_md_path
from .writers.memory_writer import MemoryWriter, ensure_memory_index_exists


# 目标类型到分析类别的映射
TARGET_CATEGORY_MAP = {
    ".claude/skills": "skill_prompt",
    "SKILL.md": "skill_prompt",
    "CLAUDE.md": "claude_md",
    "memory": "memory",
}


def _detect_category(target_path: str) -> str:
    """根据文件路径自动推断分析类别。"""
    p = target_path.lower()
    if "memory" in p or "MEMORY.md" in p:
        return "memory"
    if "skill" in p or "SKILL.md" in p:
        return "skill_prompt"
    if "claude.md" in p:
        return "claude_md"
    return "code_convention"


def _resolve_target_path(target: str) -> Path:
    """解析目标文件路径。"""
    p = Path(target).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


def _apply_suggestion(state: ConfirmState, s) -> None:
    """将单条建议写入目标文件。"""
    content = state.get_final_content(s)
    target_path = _resolve_target_path(s.target_file)

    if s.category == "skill_prompt":
        writer = SkillWriter(target_path)
        if s.action == "new" and not writer.exists():
            # 从 content 中提取 frontmatter 信息，或使用默认值
            writer.create(
                name=Path(s.target_file).parent.name or "learned-skill",
                description=s.summary,
                body=content,
            )
        elif s.action == "replace":
            # 从 summary 推断节名（简化处理）
            heading = s.summary.split("：")[0] if "：" in s.summary else s.summary
            writer.replace_section(heading, content)
        else:
            heading = s.summary.split("：")[0] if "：" in s.summary else s.summary
            writer.append_rule(heading, content)

    elif s.category == "memory":
        writer = MemoryWriter()
        ensure_memory_index_exists()
        try:
            writer.create(
                name=s.summary,
                description=s.description,
                content=content,
                mem_type="feedback",
            )
        except FileExistsError:
            print(f"  ⚠️ Memory 已存在，跳过: {s.summary}")

    elif s.category in ("claude_md", "code_convention"):
        writer = ClaudeMdWriter(target_path)
        if s.action == "replace":
            heading = s.summary.split("：")[0] if "：" in s.summary else s.summary
            writer.replace_section(heading, content)
        else:
            if s.category == "code_convention":
                writer.append_code_convention(content)
            else:
                heading = s.summary.split("：")[0] if "：" in s.summary else s.summary
                writer.append_section(heading, content)


def main():
    parser = argparse.ArgumentParser(
        description="/learn — 自学习 skill：分析文件并产出改进建议",
    )
    parser.add_argument(
        "instructions",
        nargs="?",
        help="学习指令（如 '学习：始终使用 uv 管理 Python 依赖'）",
    )
    parser.add_argument(
        "--apply-to",
        dest="target",
        help="要学习的目标文件路径",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="跳过交互确认，直接应用所有建议",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅分析不写入（预览模式）",
    )

    args = parser.parse_args()

    if not args.instructions:
        parser.print_help()
        print("\n示例: /learn '学习：始终使用 uv 管理 Python 依赖' --apply-to ~/.claude/CLAUDE.md")
        sys.exit(1)

    # 确定分析目标
    if args.target:
        target_path = _resolve_target_path(args.target)
        category = _detect_category(str(target_path))

        # 读取目标文件
        try:
            file_content = target_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"⚠️ 目标文件不存在: {target_path}")
            print("将作为新建文件分析...")
            file_content = ""

        files_to_analyze = [(str(target_path), file_content, category)]
    else:
        print("错误: 请用 --apply-to 指定目标文件")
        sys.exit(1)

    # 启动分析
    print(f"🔍 正在分析 '{args.target}' ...")
    try:
        suggestions = run_analysis(
            learning_instructions=args.instructions,
            file_path=str(target_path),
            file_content=file_content,
            category=category,
        )
    except AnalysisError as e:
        print(f"❌ 分析失败: {e}")
        sys.exit(1)

    if not suggestions:
        print("✅ 未发现改进建议。")
        return

    print(f"📋 发现 {len(suggestions)} 条改进建议\n")

    # 交互确认
    if args.yes:
        state = ConfirmState(suggestions=suggestions)
        for s in suggestions:
            state.accept()
        print(f"✅ 已自动接受 {len(suggestions)} 条建议")
    else:
        state = ConfirmState(suggestions=suggestions)
        run_tui(state)

    # 应用确认的建议
    accepted = state.accepted_suggestions()
    if args.dry_run:
        print(f"\n🔍 [预览模式] 将要应用 {len(accepted)} 条建议，不实际写入")
        for s in accepted:
            print(f"  - {s.summary} → {s.target_file}")
        return

    if not accepted:
        print("\n没有需要应用的建议。")
        return

    print(f"\n📝 正在应用 {len(accepted)} 条建议...")
    errors = []
    for s in accepted:
        try:
            _apply_suggestion(state, s)
            print(f"  ✅ {s.summary}")
        except Exception as e:
            print(f"  ❌ {s.summary}: {e}")
            errors.append((s, e))

    if errors:
        print(f"\n⚠️ {len(errors)} 条建议应用失败")
        sys.exit(1)
    else:
        print(f"\n✅ 成功应用 {len(accepted)} 条建议！")


if __name__ == "__main__":
    main()
