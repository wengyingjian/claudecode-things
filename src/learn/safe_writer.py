"""
SafeFileWriter — 安全文件写入基元。

所有目标类型的写入共享同一安全机制：备份 → 原子写入 → 验证。
"""
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


class WriteError(Exception):
    """写入失败的基类异常。"""


class BackupExistsError(WriteError):
    """备份文件已存在（可能上次写入中断）。"""


class WriteVerificationError(WriteError):
    """写入后验证失败。"""


class SafeFileWriter:
    """安全文件写入器：备份 → 原子写入 → 验证。"""

    BACKUP_DIR_NAME = ".learn-backups"
    MAX_BACKUPS = 10

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path).expanduser().resolve()
        self.backup_dir = self.file_path.parent / self.BACKUP_DIR_NAME
        self._backup_path: Path | None = None

    # ── 公共 API ──────────────────────────────────

    def write(self, content: str) -> None:
        """安全写入文件内容（全量替换）。"""
        self._ensure_dir()
        self._backup()
        self._atomic_write(content)
        self._verify(content)
        self._cleanup_old_backups()

    def read(self) -> str:
        """读取当前文件内容。"""
        if not self.file_path.exists():
            raise FileNotFoundError(f"文件不存在: {self.file_path}")
        return self.file_path.read_text(encoding="utf-8")

    def read_or_empty(self) -> str:
        """读取文件内容，文件不存在时返回空字符串。"""
        try:
            return self.read()
        except FileNotFoundError:
            return ""

    def append_section(self, heading: str, content: str) -> None:
        """在指定 ## heading 下追加内容，heading 不存在则新建节。"""
        original = self.read_or_empty()
        new_content = section_append(original, heading, content)
        self.write(new_content)

    def replace_section(self, heading: str, content: str) -> None:
        """替换指定 ## heading 的全部内容（从 heading 到下一个 ## 或 EOF）。"""
        original = self.read_or_empty()
        new_content = section_replace(original, heading, content)
        self.write(new_content)

    def find_section_heading(self, candidates: list[str]) -> str | None:
        """在文件中查找第一个匹配的节标题，返回匹配到的标题名。"""
        try:
            text = self.read()
        except FileNotFoundError:
            return None
        for line in text.split("\n"):
            if line.startswith("## "):
                heading = line[3:].strip()
                if heading in candidates:
                    return heading
        return None

    # ── 内部方法 ──────────────────────────────────

    def _ensure_dir(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _backup(self) -> None:
        """创建带时间戳的备份。"""
        if not self.file_path.exists():
            return

        self.backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        name = f"{self.file_path.name}.{ts}.bak"
        self._backup_path = self.backup_dir / name

        if self._backup_path.exists():
            raise BackupExistsError(
                f"备份文件已存在: {self._backup_path}，可能存在并发写入冲突"
            )
        shutil.copy2(self.file_path, self._backup_path)

    def _atomic_write(self, content: str) -> None:
        """先写临时文件，再 rename（原子操作）。"""
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".tmp",
            dir=str(self.file_path.parent),
            delete=False,
            encoding="utf-8",
        )
        try:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
            tmp_path.chmod(0o644)
            tmp_path.replace(self.file_path)
        except Exception:
            Path(tmp.name).unlink(missing_ok=True)
            raise

    def _verify(self, expected: str) -> None:
        """验证写入内容正确，失败时从备份恢复。"""
        actual = self.file_path.read_text(encoding="utf-8")
        if actual != expected:
            if self._backup_path and self._backup_path.exists():
                shutil.copy2(self._backup_path, self.file_path)
            raise WriteVerificationError(
                f"写入验证失败: {self.file_path}，已从备份恢复"
            )

    def _cleanup_old_backups(self) -> None:
        """保留最近 MAX_BACKUPS 个备份，删除更旧的。"""
        if not self.backup_dir.exists():
            return
        prefix = f"{self.file_path.name}."
        backups = sorted(
            [p for p in self.backup_dir.iterdir() if p.name.startswith(prefix)],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in backups[self.MAX_BACKUPS:]:
            old.unlink(missing_ok=True)


# ── Markdown 节操作（纯函数）──────────────────────

def section_append(text: str, heading: str, content: str) -> str:
    """在指定 ## heading 下追加内容。heading 不存在则追加到文件末尾。"""
    lines = text.split("\n")
    target = f"## {heading}"
    result: list[str] = []
    found = False
    i = 0

    while i < len(lines):
        result.append(lines[i])
        if lines[i].strip() == target and not found:
            found = True
            i += 1
            # 跳过 heading 后的空行
            while i < len(lines) and lines[i].strip() == "":
                result.append(lines[i])
                i += 1
            # 插入新内容
            if content:
                # 确保前后有空行分隔
                if result and result[-1] != "":
                    result.append("")
                result.append(content)
                result.append("")
            continue
        i += 1

    if not found:
        if result and result[-1] != "":
            result.append("")
        result.append(target)
        result.append("")
        result.append(content)

    return "\n".join(result)


def section_replace(text: str, heading: str, content: str) -> str:
    """替换指定 ## heading 的全部内容（从 heading 到下一个 ## 或 EOF）。"""
    lines = text.split("\n")
    target = f"## {heading}"
    result: list[str] = []
    i = 0

    while i < len(lines):
        if lines[i].strip() == target:
            result.append(lines[i])
            if content:
                result.append("")
                result.append(content)
                result.append("")
            i += 1
            # 跳过原有内容直到下一个 ## 或 EOF
            while i < len(lines) and not lines[i].startswith("## "):
                i += 1
            continue
        result.append(lines[i])
        i += 1

    return "\n".join(result)


def has_duplicate(section_content: str, new_line: str) -> bool:
    """检查节内容中是否已有相同行（忽略空白和大小写差异）。"""
    normalized_new = new_line.strip().lower()
    if not normalized_new:
        return False
    for line in section_content.split("\n"):
        if line.strip().lower() == normalized_new:
            return True
    return False
