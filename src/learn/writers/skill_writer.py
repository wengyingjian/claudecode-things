"""
SKILL.md 文件写入器 — 处理 Skill Prompt 文件的读写操作。

支持：新建 skill、追加规则、替换规则、新增节。
"""
from pathlib import Path

from ..safe_writer import SafeFileWriter, has_duplicate

# Skill prompt 中不应被替换的节名（元数据节）
PROTECTED_SECTIONS = {"name", "description", "metadata", "frontmatter"}


class SkillWriter:
    """SKILL.md 文件的写入器。"""

    def __init__(self, skill_path: str | Path):
        self.writer = SafeFileWriter(skill_path)

    def exists(self) -> bool:
        return self.writer.file_path.exists()

    def read(self) -> str:
        return self.writer.read_or_empty()

    def create(self, name: str, description: str, body: str = "") -> None:
        """新建 skill 文件，构造完整 frontmatter + body。"""
        content = _build_skill_frontmatter(name, description)
        if body:
            content += f"\n{body}\n"
        self.writer.write(content)

    def append_rule(self, section: str, content: str, dedup: bool = True) -> bool:
        """在指定节下追加规则。返回 True 表示实际写入了内容。"""
        if section.lower() in PROTECTED_SECTIONS:
            raise ValueError(f"不允许修改受保护的节: {section}")

        if dedup:
            try:
                existing = self.writer.read()
                if has_duplicate(existing, content):
                    return False
            except FileNotFoundError:
                pass

        self.writer.append_section(section, content)
        return True

    def replace_section(self, section: str, content: str) -> None:
        """替换指定节的完整内容。"""
        if section.lower() in PROTECTED_SECTIONS:
            raise ValueError(f"不允许修改受保护的节: {section}")
        self.writer.replace_section(section, content)


def _build_skill_frontmatter(name: str, description: str) -> str:
    """构建 skill 的 YAML frontmatter。"""
    return (
        f"---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"---\n"
    )
