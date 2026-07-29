"""
CLAUDE.md 文件写入器 — 处理用户级和项目级 CLAUDE.md 的读写操作。

CLAUDE.md 由多个 ## 节组成，操作围绕节的追加/替换。
"""
from pathlib import Path

from ..safe_writer import SafeFileWriter, has_duplicate

# 常见编码风格节名变体
CODE_STYLE_HEADINGS = [
    "编码风格", "编码规范", "Code Style", "Coding Conventions",
    "编码约定", "Style Guide",
]


def resolve_claude_md_path(level: str, project_root: Path | None = None) -> Path:
    """解析 CLAUDE.md 路径。

    Args:
        level: "user" → ~/.claude/CLAUDE.md, "project" → <project_root>/CLAUDE.md
        project_root: 项目根目录（仅 project 级别需要）
    """
    if level == "user":
        return Path.home() / ".claude" / "CLAUDE.md"
    elif level == "project":
        if project_root is None:
            raise ValueError("项目级别 CLAUDE.md 需要指定 project_root")
        return Path(project_root) / "CLAUDE.md"
    else:
        raise ValueError(f"无效的 level: {level}，应为 'user' 或 'project'")


class ClaudeMdWriter:
    """CLAUDE.md 文件的写入器。"""

    def __init__(self, file_path: str | Path):
        self.writer = SafeFileWriter(file_path)

    def exists(self) -> bool:
        return self.writer.file_path.exists()

    def read(self) -> str:
        return self.writer.read_or_empty()

    def append_section(self, heading: str, content: str, dedup: bool = True) -> bool:
        """在指定节下追加内容。返回 True 表示实际写入了。"""
        if dedup:
            existing = self.read()
            if has_duplicate(existing, content):
                return False
        self.writer.append_section(heading, content)
        return True

    def replace_section(self, heading: str, content: str) -> None:
        """替换指定节的完整内容。"""
        self.writer.replace_section(heading, content)

    def find_code_style_heading(self) -> str | None:
        """自动探测编码风格节名，返回匹配到的标题。"""
        return self.writer.find_section_heading(CODE_STYLE_HEADINGS)

    def ensure_code_style_section(self) -> str:
        """确保存在编码风格节，返回节名（已有则返回已有节名，否则创建）。"""
        existing = self.find_code_style_heading()
        if existing:
            return existing
        return CODE_STYLE_HEADINGS[0]  # 默认中文名

    def append_code_convention(self, content: str) -> bool:
        """追加代码约定到编码风格节。自动探测或创建节。"""
        heading = self.ensure_code_style_section()
        return self.append_section(heading, content)
