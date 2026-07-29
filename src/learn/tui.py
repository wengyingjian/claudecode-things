"""
确认流程的轻量 TUI — 基于 ANSI 转义码的交互式确认界面。

使用全屏刷新，单键驱动交互。兼容 macOS/Linux，依赖 termios/tty 模块。
"""
import os
import subprocess
import sys
import tempfile
import termios
import tty

from .state import ConfirmState, Decision, Phase

# ── ANSI 常量 ─────────────────────────────────────────
CLEAR = "\033[2J\033[H"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RESET = "\033[0m"

CATEGORY_LABEL = {
    "skill_prompt": "Skill Prompt",
    "claude_md": "CLAUDE.md",
    "memory": "Memory",
    "code_convention": "代码约定",
}

ACTION_LABEL = {"append": "追加", "replace": "替换", "new": "新建"}

NEW_RULE_MARKER = {True: "🆕 新增", False: "📝 修正"}


def getch() -> str:
    """读取单个按键，不回显。（macOS/Linux 专用，依赖 termios）"""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def render(state: ConfirmState) -> str:
    """渲染完整一帧。"""
    lines = []
    w = _terminal_width()

    # ── 顶栏 ──
    lines.append(f"{BOLD}{'═' * w}{RESET}")
    if state.is_done:
        lines.append(f"  {BOLD}/learn 确认 — 完成{RESET}")
    elif state.phase == Phase.EDITING:
        lines.append(f"  {BOLD}/learn 确认 — 编辑中{RESET}")
    else:
        cur = state.current
        idx = state.current_index + 1
        lines.append(f"  {BOLD}/learn 确认 — 建议 {idx}/{state.total}{RESET}")
    lines.append(f"{BOLD}{'═' * w}{RESET}")
    lines.append("")

    if state.is_done:
        lines.extend(_render_summary(state, w))
    elif state.phase == Phase.EDITING:
        lines.extend(_render_editing(state, w))
    else:
        lines.extend(_render_suggestion(state, w))

    # ── 状态栏 ──
    lines.append("")
    acc = state.count_by(Decision.ACCEPTED)
    edt = state.count_by(Decision.EDITED)
    rej = state.count_by(Decision.REJECTED)
    skp = state.count_by(Decision.SKIPPED)
    lines.append(
        f"  已处理: {GREEN}✅{acc}{RESET}  {YELLOW}✏️{edt}{RESET}  "
        f"{RED}❌{rej}{RESET}  {DIM}⏭️{skp}{RESET}"
    )
    lines.append("")

    # ── 快捷键 ──
    if not state.is_done:
        lines.append(
            f"  {BOLD}[a]{RESET} 接受  {BOLD}[e]{RESET} 编辑  "
            f"{BOLD}[r]{RESET} 拒绝  {BOLD}[q]{RESET} 退出"
        )
    else:
        lines.append(f"  {BOLD}[q]{RESET} 退出")
    lines.append(f"{BOLD}{'═' * w}{RESET}")

    return "\n".join(lines)


def _render_suggestion(state: ConfirmState, w: int) -> list[str]:
    """渲染当前建议的详细信息。"""
    lines = []
    s = state.current
    if not s:
        return lines

    new_marker = NEW_RULE_MARKER.get(s.is_new_rule, "")
    lines.append(f"  {BOLD}📋 建议:{RESET} {s.summary}  {DIM}{new_marker}{RESET}")
    lines.append(f"  {DIM}📂 目标:{RESET} {s.target_file}")
    lines.append(
        f"  {DIM}🏷️  类别:{RESET} {CATEGORY_LABEL.get(s.category, s.category)}"
        f"  ·  {DIM}动作:{RESET} {ACTION_LABEL.get(s.action, s.action)}"
    )
    lines.append(f"  {DIM}{'─' * (w - 4)}{RESET}")
    lines.append(f"  {DIM}📝 描述:{RESET} {s.description}")
    lines.append(f"  {DIM}{'─' * (w - 4)}{RESET}")
    lines.append(f"  {BOLD}📄 内容:{RESET}")
    for line in s.content.split("\n"):
        lines.append(f"  {CYAN}{line}{RESET}")
    lines.append(f"  {DIM}{'─' * (w - 4)}{RESET}")

    return lines


def _render_editing(state: ConfirmState, w: int) -> list[str]:
    """编辑模式的提示。"""
    lines = []
    cur = state.current
    if not cur:
        return lines
    lines.append(f"  {YELLOW}⏳ 正在编辑: {cur.summary}{RESET}")
    lines.append(f"  {DIM}请在编辑器中修改内容，保存后关闭编辑器。{RESET}")
    lines.append(f"  {DIM}关闭时不保存 = 取消编辑。{RESET}")
    return lines


def _render_summary(state: ConfirmState, w: int) -> list[str]:
    """最终汇总。"""
    lines = []
    lines.append(f"  {GREEN}{BOLD}✅ 确认完成！{RESET}")
    lines.append("")
    total = state.total
    acc = state.count_by(Decision.ACCEPTED)
    edt = state.count_by(Decision.EDITED)
    rej = state.count_by(Decision.REJECTED)
    skp = state.count_by(Decision.SKIPPED)

    lines.append(f"  共 {total} 条建议:")
    lines.append(f"    {GREEN}✅ 直接接受: {acc}{RESET}")
    lines.append(f"    {YELLOW}✏️ 编辑后接受: {edt}{RESET}")
    lines.append(f"    {RED}❌ 拒绝: {rej}{RESET}")
    if skp > 0:
        lines.append(f"    {DIM}⏭️ 跳过: {skp}{RESET}")

    if edt > 0:
        lines.append("")
        lines.append(f"  {YELLOW}编辑过的建议:{RESET}")
        for s in state.suggestions:
            if state.decisions.get(s.id) == Decision.EDITED:
                lines.append(f"    - {s.summary} → {s.target_file}")

    return lines


def _terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except (OSError, ValueError):
        return 80


def open_editor(initial_content: str) -> str | None:
    """用系统编辑器打开临时文件，返回修改后的内容。
    返回 None 表示用户取消了编辑（文件未修改）。
    """
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(initial_content)
        tmp_path = f.name

    try:
        result = subprocess.run([editor, tmp_path])
        if result.returncode != 0:
            return None
        with open(tmp_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def run_tui(state: ConfirmState) -> None:
    """主循环。"""
    while True:
        sys.stdout.write(CLEAR)
        sys.stdout.write(render(state))
        sys.stdout.flush()

        if state.is_done:
            getch()
            break

        key = getch()

        if key in ("q", "\x03"):  # q 或 Ctrl-C
            state.mark_remaining_skipped()
        elif key == "a":
            state.accept()
        elif key == "r":
            state.reject()
        elif key == "e":
            content = state.start_edit()
            if content:
                sys.stdout.write(CLEAR)
                sys.stdout.flush()
                edited = open_editor(content)
                if edited is not None:
                    state.finish_edit(edited)
                else:
                    state.cancel_edit()

    # 最终帧
    sys.stdout.write(CLEAR)
    sys.stdout.write(render(state))
    sys.stdout.flush()
