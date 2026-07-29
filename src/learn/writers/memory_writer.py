"""
Memory 文件写入器 — 处理项目 memory 文件的创建和 MEMORY.md 索引维护。

Memory 写入是两步原子操作：
1. 创建 memory 文件
2. 更新 MEMORY.md 索引
任一步失败需回滚。
"""
import re
from pathlib import Path

from ..safe_writer import SafeFileWriter

# MEMORY.md 中按 type 分节
TYPE_SECTION_MAP = {
    "user": "User",
    "feedback": "Feedback",
    "project": "Project",
    "reference": "Reference",
}


def resolve_memory_paths(project_name: str | None = None) -> tuple[Path, Path]:
    """解析 memory 目录路径和 MEMORY.md 路径。

    Args:
        project_name: 项目名（对应 ~/.claude/projects/<project>/）
    """
    if project_name is None:
        # 尝试从当前目录推断
        project_name = Path.cwd().name

    base = Path.home() / ".claude" / "projects" / project_name / "memory"
    return base, base.parent / "MEMORY.md"


def slugify(text: str) -> str:
    """将文本转为 kebab-case slug。"""
    # 移除特殊字符，保留字母、数字、空格和连字符
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    # 空白和连字符压缩为单个连字符
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug


class MemoryWriter:
    """Memory 文件的写入器。"""

    def __init__(self, project_name: str | None = None):
        self.memory_dir, self.index_path = resolve_memory_paths(project_name)
        self.index_writer = SafeFileWriter(self.index_path)

    def list_existing_slugs(self) -> set[str]:
        """列出已有 memory 文件的 slug。"""
        if not self.memory_dir.exists():
            return set()
        return {
            p.stem
            for p in self.memory_dir.iterdir()
            if p.suffix == ".md" and p.is_file()
        }

    def create(
        self,
        name: str,
        description: str,
        content: str,
        mem_type: str = "feedback",
    ) -> Path:
        """创建新的 memory 文件并更新 MEMORY.md 索引。

        两步原子操作：先写 memory 文件 → 再写索引。索引写入失败时回滚。

        Returns:
            创建的 memory 文件路径。
        """
        slug = slugify(name)
        existing = self.list_existing_slugs()
        if slug in existing:
            raise FileExistsError(f"Memory '{slug}' 已存在，请使用不同的 name")

        memory_path = self.memory_dir / f"{slug}.md"
        memory_writer = SafeFileWriter(memory_path)

        # 构建 frontmatter
        full_content = (
            "---\n"
            f"name: {slug}\n"
            f"description: {description}\n"
            "metadata:\n"
            f"  type: {mem_type}\n"
            "---\n"
            "\n"
            f"{content}\n"
        )

        # 第一步：写 memory 文件
        memory_writer.write(full_content)

        # 第二步：更新 MEMORY.md 索引
        try:
            self._append_index(slug, description, mem_type)
        except Exception:
            # 回滚：删除已创建的 memory 文件
            memory_path.unlink(missing_ok=True)
            raise

        return memory_path

    def _append_index(self, slug: str, description: str, mem_type: str) -> None:
        """在 MEMORY.md 中追加索引行。"""
        section_name = TYPE_SECTION_MAP.get(mem_type, "Feedback")
        index_line = f"- [{slug}]({slug}.md) — {description}"
        self.index_writer.append_section(section_name, index_line)


def ensure_memory_index_exists(project_name: str | None = None) -> None:
    """确保 MEMORY.md 存在，如果不存在则创建空索引。"""
    _, index_path = resolve_memory_paths(project_name)
    if not index_path.exists():
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            "# Memory Index\n\n"
            "## Feedback\n\n"
            "## Project\n\n"
            "## User\n\n"
            "## Reference\n\n",
            encoding="utf-8",
        )
