"""
确认流程的状态模型 — 纯逻辑，不涉及 UI。

状态模型: 一个线性建议列表 + 当前位置指针 + 每个条目的决策记录。
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Decision(Enum):
    PENDING = auto()   # 尚未处理
    ACCEPTED = auto()  # 直接接受
    EDITED = auto()    # 编辑后接受
    REJECTED = auto()  # 拒绝
    SKIPPED = auto()   # 退出时未处理的


class Phase(Enum):
    CONFIRMING = auto()  # 逐条确认中
    EDITING = auto()     # 正在外部编辑器编辑
    DONE = auto()        # 全部处理完毕


@dataclass
class Suggestion:
    """分析 session 产出的单条建议。"""
    id: int
    summary: str          # 一句话标题
    description: str      # 为什么需要这个改动
    target_file: str      # 目标文件路径
    category: str         # skill_prompt | claude_md | memory | code_convention
    content: str          # 建议写入的内容
    action: str           # append | replace | new
    is_new_rule: bool = False  # True=新增规则, False=修正已有规则


@dataclass
class ConfirmState:
    """确认流程的完整状态。"""
    suggestions: list[Suggestion]
    current_index: int = 0
    decisions: dict[int, Decision] = field(default_factory=dict)
    edited_content: dict[int, str] = field(default_factory=dict)
    phase: Phase = Phase.CONFIRMING

    def __post_init__(self):
        for s in self.suggestions:
            self.decisions.setdefault(s.id, Decision.PENDING)

    # ── 查询 ──────────────────────────────────────────

    @property
    def current(self) -> Optional[Suggestion]:
        if 0 <= self.current_index < len(self.suggestions):
            return self.suggestions[self.current_index]
        return None

    @property
    def total(self) -> int:
        return len(self.suggestions)

    @property
    def is_done(self) -> bool:
        return self.phase == Phase.DONE

    def count_by(self, decision: Decision) -> int:
        return sum(1 for d in self.decisions.values() if d == decision)

    def accepted_suggestions(self) -> list[Suggestion]:
        """返回所有已接受（含编辑后）的建议。"""
        return [
            s for s in self.suggestions
            if self.decisions.get(s.id) in (Decision.ACCEPTED, Decision.EDITED)
        ]

    def get_final_content(self, s: Suggestion) -> str:
        """获取建议的最终内容（编辑后的或原始的）。"""
        if self.decisions.get(s.id) == Decision.EDITED:
            return self.edited_content.get(s.id, s.content)
        return s.content

    # ── 操作 ──────────────────────────────────────────

    def accept(self) -> None:
        """接受当前建议，不做修改。"""
        cur = self.current
        if cur:
            self.decisions[cur.id] = Decision.ACCEPTED
        self._advance()

    def reject(self) -> None:
        """拒绝当前建议。"""
        cur = self.current
        if cur:
            self.decisions[cur.id] = Decision.REJECTED
        self._advance()

    def start_edit(self) -> Optional[str]:
        """进入编辑模式，返回建议内容供编辑器修改。"""
        cur = self.current
        if cur:
            self.phase = Phase.EDITING
            return cur.content
        return None

    def finish_edit(self, edited: str) -> None:
        """编辑完成，保存修改后的内容。"""
        cur = self.current
        if cur:
            if edited.strip() != cur.content.strip():
                self.decisions[cur.id] = Decision.EDITED
                self.edited_content[cur.id] = edited
            else:
                self.decisions[cur.id] = Decision.ACCEPTED
        self.phase = Phase.CONFIRMING
        self._advance()

    def cancel_edit(self) -> None:
        """取消编辑，回到确认界面。"""
        self.phase = Phase.CONFIRMING

    def _advance(self) -> None:
        """移到下一个待处理的建议。"""
        self.current_index += 1
        while self.current_index < self.total:
            sid = self.suggestions[self.current_index].id
            if self.decisions.get(sid) == Decision.PENDING:
                return
            self.current_index += 1
        self.phase = Phase.DONE

    def mark_remaining_skipped(self) -> None:
        """退出时将所有未处理的标记为跳过。"""
        for s in self.suggestions:
            if self.decisions.get(s.id) == Decision.PENDING:
                self.decisions[s.id] = Decision.SKIPPED
        self.phase = Phase.DONE
