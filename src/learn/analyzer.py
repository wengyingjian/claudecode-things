"""
分析器 — 通过 Anthropic API 启动分析 session，产出结构化改进建议。

分析 session 仅接收「学习指令 + 目标文件内容」，不传 tools（物理隔离）。
"""
import json
import sys
from pathlib import Path
from typing import Optional

import anthropic

from .state import Suggestion

# ── 配置常量 ────────────────────────────────────────────
ANALYSIS_MODEL = "claude-sonnet-5"
ANALYSIS_MAX_TOKENS = 8000
ANALYSIS_TIMEOUT = 120  # 秒

# ── System Prompt 模板 ──────────────────────────────────
SYSTEM_PROMPT_SKILL = """\
你是一个 Skill Prompt 分析专家。你的任务是分析 SKILL.md 文件，对照学习指令，发现改进点。

分析视角：
- 指令是否清晰、无歧义？
- 是否有遗漏的边界情况？
- 触发条件描述是否完整？
- 输出格式约束是否明确？
- 是否有与用户意图冲突的规则？

输出 JSON 数组，每条建议包含：
- summary: 一句话标题
- description: 为什么需要这个改动（1-2句）
- target_file: 目标文件路径
- category: "skill_prompt"
- content: 建议写入的 Markdown 内容（包含 ## 节标题）
- action: "append" | "replace" | "new"
- is_new_rule: true=新增规则, false=修正已有规则
"""

SYSTEM_PROMPT_CLAUDE_MD = """\
你是一个项目配置分析专家。你的任务是分析 CLAUDE.md 文件，对照学习指令，发现改进点。

分析视角：
- 编码约定是否完整？
- 工具链配置是否准确？
- 项目结构描述是否反映最新状态？
- 是否有冗余或矛盾的规则？
- 是否有未记录的隐式约定？

输出 JSON 数组，每条建议包含：
- summary: 一句话标题
- description: 为什么需要这个改动（1-2句）
- target_file: 目标文件路径
- category: "claude_md"
- content: 建议写入的 Markdown 内容（包含 ## 节标题）
- action: "append" | "replace"
- is_new_rule: true=新增规则, false=修正已有规则
"""

SYSTEM_PROMPT_CODE = """\
你是一个代码约定分析专家。你的任务是分析项目代码，对照学习指令，发现可提取的编码约定。

分析视角：
- 重复出现的编码模式
- 隐式的命名约定
- 错误处理的一致模式
- 项目特有的技术选择（如"用 uv 不用 pip"）
- 注释风格约定

输出 JSON 数组，每条建议包含：
- summary: 一句话标题
- description: 为什么这应该成为约定（1-2句）
- target_file: 目标文件路径（CLAUDE.md）
- category: "code_convention"
- content: 建议写入的约定内容
- action: "append"
- is_new_rule: true
"""

SYSTEM_PROMPT_MEMORY = """\
你是一个用户偏好分析专家。你的任务是从学习指令中提取可持久化的用户偏好和项目背景信息。

分析视角：
- 用户明确表达的偏好（如"我喜欢用 uv"）
- 项目特定的上下文信息
- 工作流约定
- 工具使用偏好
- 反馈模式（用户反复纠正的内容）

输出 JSON 数组，每条建议包含：
- summary: 一句话标题
- description: 为什么需要记住这个（1-2句）
- target_file: memory 文件路径（~/.claude/projects/<project>/memory/<slug>.md）
- category: "memory"
- content: 建议写入的 memory 内容（含 frontmatter）
- action: "new"
- is_new_rule: true
"""

SYSTEM_PROMPTS = {
    "skill_prompt": SYSTEM_PROMPT_SKILL,
    "claude_md": SYSTEM_PROMPT_CLAUDE_MD,
    "code_convention": SYSTEM_PROMPT_CODE,
    "memory": SYSTEM_PROMPT_MEMORY,
}


class AnalysisError(Exception):
    """分析过程失败的异常。"""


def run_analysis(
    learning_instructions: str,
    file_path: str,
    file_content: str,
    category: str,
    base_system_prompt: Optional[str] = None,
    model: str = ANALYSIS_MODEL,
) -> list[Suggestion]:
    """通过 Anthropic API 分析单个文件。

    Args:
        learning_instructions: 用户的学习指令
        file_path: 分析的目标文件路径
        file_content: 目标文件内容（已读取）
        category: 分析类别 (skill_prompt | claude_md | code_convention | memory)
        base_system_prompt: 自定义 system prompt（覆盖默认）
        model: 使用的模型 ID

    Returns:
        分析产出的建议列表
    """
    system = base_system_prompt or SYSTEM_PROMPTS.get(category, SYSTEM_PROMPT_CLAUDE_MD)
    system += "\n\n## 参考学习指令\n" + learning_instructions

    user_message = (
        f"请分析以下文件 ({file_path}):\n\n"
        f"```markdown\n{file_content}\n```"
    )

    try:
        client = anthropic.Anthropic(
            timeout=ANALYSIS_TIMEOUT,
            max_retries=2,
        )

        response = client.messages.create(
            model=model,
            max_tokens=ANALYSIS_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )

        texts = [b.text for b in response.content if b.type == "text"]
        raw = "\n".join(texts)

        return _parse_suggestions(raw, file_path, category)

    except anthropic.APIError as e:
        raise AnalysisError(f"API 调用失败: {e}") from e
    except json.JSONDecodeError as e:
        raise AnalysisError(f"JSON 解析失败: {e}") from e


def _parse_suggestions(
    raw_response: str,
    default_target: str,
    default_category: str,
) -> list[Suggestion]:
    """从 API 响应中解析建议列表。"""
    # 尝试提取 JSON 数组
    json_str = _extract_json_array(raw_response)
    items = json.loads(json_str)

    suggestions = []
    for i, item in enumerate(items):
        suggestions.append(Suggestion(
            id=i + 1,
            summary=item.get("summary", "未命名建议"),
            description=item.get("description", ""),
            target_file=item.get("target_file", default_target),
            category=item.get("category", default_category),
            content=item.get("content", ""),
            action=item.get("action", "append"),
            is_new_rule=item.get("is_new_rule", False),
        ))

    return suggestions


def _extract_json_array(text: str) -> str:
    """从文本中提取 JSON 数组。"""
    # 尝试找 ```json ... ``` 代码块
    import re
    match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if match:
        return match.group(1)

    # 尝试找裸 JSON 数组
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        return match.group(0)

    raise json.JSONDecodeError("无法提取 JSON 数组", text, 0)


def analyze_multi_files(
    learning_instructions: str,
    files: list[tuple[str, str, str]],  # (path, content, category)
    model: str = ANALYSIS_MODEL,
) -> list[Suggestion]:
    """分析多个文件，返回合并的建议列表。

    Args:
        learning_instructions: 用户的学习指令
        files: [(file_path, file_content, category), ...]
        model: 使用的模型 ID

    Returns:
        所有文件分析的合并建议（ID 去重）。
    """
    all_suggestions: list[Suggestion] = []
    seen_summaries: set[str] = set()

    for file_path, file_content, category in files:
        suggestions = run_analysis(
            learning_instructions=learning_instructions,
            file_path=file_path,
            file_content=file_content,
            category=category,
            model=model,
        )
        for s in suggestions:
            key = s.summary.strip().lower()
            if key not in seen_summaries:
                seen_summaries.add(key)
                all_suggestions.append(s)

    # 重新编号
    for i, s in enumerate(all_suggestions):
        s.id = i + 1

    return all_suggestions
