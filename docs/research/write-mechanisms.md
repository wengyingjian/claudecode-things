# 改动写入机制：各目标类型的写入方式

## 调研日期
2026-07-29

## 结论摘要

四类目标文件的写入方式各有不同，但共享一套安全基元：

| 目标类型 | 写入策略 | 关键风险 |
|----------|----------|----------|
| **Skill prompt** (SKILL.md) | 分段追加/替换，保留 frontmatter | YAML frontmatter 完整性 |
| **CLAUDE.md** (用户/项目) | 按 `##` 节操作，追加/插入/替换 | 节边界识别，重复条目检测 |
| **Memory 文件** | 新建文件 + MEMORY.md 索引追加 | 命名冲突，索引格式 |
| **代码约定** (CLAUDE.md 子集) | 同 CLAUDE.md，定位 `## 编码风格` 节 | 需区分约定节与其他节 |

**公共安全机制**：所有写入遵循「备份 → 原子写入 → 验证」三步流程。

---

## 公共基元：SafeFileWriter

所有目标类型的写入共享同一个安全写入工具，避免重复实现。

```python
import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

class WriteError(Exception):
    """写入失败的基类异常。"""

class BackupExistsError(WriteError):
    """备份文件已存在（可能上次写入中断）。"""

class WriteVerificationError(WriteError):
    """写入后验证失败。"""


class SafeFileWriter:
    """安全文件写入器：备份 → 原子写入 → 验证。"""

    BACKUP_DIR_NAME = ".learn-backups"

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

    def read(self) -> str:
        """读取当前文件内容。"""
        if not self.file_path.exists():
            raise FileNotFoundError(f"文件不存在: {self.file_path}")
        return self.file_path.read_text(encoding="utf-8")

    def append_section(self, heading: str, content: str) -> None:
        """在指定 heading 下追加内容，如果 heading 不存在则新建节。"""
        original = self.read()
        new_content = _section_append(original, heading, content)
        self.write(new_content)

    def replace_section(self, heading: str, content: str) -> None:
        """替换指定 heading 的全部内容。"""
        original = self.read()
        new_content = _section_replace(original, heading, content)
        self.write(new_content)

    # ── 内部方法 ──────────────────────────────────

    def _ensure_dir(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _backup(self) -> None:
        """创建带时间戳的备份。"""
        if not self.file_path.exists():
            return  # 新文件无需备份

        self.backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
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
            tmp_path.replace(self.file_path)  # 原子 rename
        except Exception:
            Path(tmp.name).unlink(missing_ok=True)
            raise

    def _verify(self, expected: str) -> None:
        """验证写入内容正确。"""
        actual = self.file_path.read_text(encoding="utf-8")
        if actual != expected:
            # 尝试从备份恢复
            if self._backup_path and self._backup_path.exists():
                shutil.copy2(self._backup_path, self.file_path)
            raise WriteVerificationError(
                f"写入验证失败: {self.file_path}，已从备份恢复"
            )


# ── Markdown 节操作（纯函数）──────────────────────

def _section_append(text: str, heading: str, content: str) -> str:
    """在指定 ## heading 下追加内容。heading 不存在则追加到文件末尾。"""
    lines = text.split("\n")
    target = f"## {heading}"
    result = []
    found = False
    i = 0

    while i < len(lines):
        result.append(lines[i])
        # 找到目标 heading
        if lines[i].strip() == target and not found:
            found = True
            # 跳过 heading 后的空行
            i += 1
            while i < len(lines) and lines[i].strip() == "":
                result.append(lines[i])
                i += 1
            # 插入新内容
            if content:
                result.append("")
                result.append(content)
                result.append("")
            continue
        i += 1

    if not found:
        # heading 不存在，追加到末尾
        if result and result[-1] != "":
            result.append("")
        result.append(target)
        result.append("")
        result.append(content)

    return "\n".join(result)


def _section_replace(text: str, heading: str, content: str) -> str:
    """替换指定 ## heading 的全部内容（从 heading 到下一个 ## 或 EOF）。"""
    lines = text.split("\n")
    target = f"## {heading}"
    result = []
    i = 0

    while i < len(lines):
        # 找到目标 heading
        if lines[i].strip() == target:
            result.append(lines[i])  # 保留 heading
            if content:
                result.append("")
                result.append(content)
                result.append("")
            # 跳过原有内容直到下一个 ## 或 EOF
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                i += 1
            continue
        result.append(lines[i])
        i += 1

    return "\n".join(result)
```

---

## 目标类型 1：Skill Prompt 文件 (SKILL.md)

### 文件格式

```yaml
---
name: my-skill
description: 一句话描述
metadata:
  key: value
---

# Skill 标题

## 节1
内容...

## 节2
内容...
```

### 写入策略

| 操作 | 方法 | 说明 |
|------|------|------|
| **新建 skill** | `SafeFileWriter.write(full_content)` | 完整构建 frontmatter + body |
| **追加规则** | `SafeFileWriter.append_section("节名", content)` | 在已有节下追加 |
| **替换规则** | `SafeFileWriter.replace_section("节名", content)` | 替换整节内容 |
| **新增节** | `SafeFileWriter.append_section("新节名", content)` | 节不存在时自动创建 |

### 特殊关注

1. **Frontmatter 保护**：`append_section` / `replace_section` 基于 `read()` 返回的全文操作，天然保留 frontmatter
2. **重复检测**：追加前检查目标节是否已有相同内容，避免重复条目
3. **新增 vs 追加**：新建 skill 时需构造完整 frontmatter + body，而非仅追加内容

---

## 目标类型 2：CLAUDE.md（用户级和项目级）

### 文件结构

用户级 `~/.claude/CLAUDE.md` 和项目级 `<project>/CLAUDE.md` 结构相同：

```markdown
## 节名1
内容...

## 节名2
| 表格 | 内容 |
内容...
```

### 写入策略

| 操作 | 方法 | 说明 |
|------|------|------|
| **追加到已有节** | `append_section("节名", content)` | 在节内容后追加 |
| **新建节** | `append_section("新节名", content)` | 自动在末尾创建 |
| **替换节** | `replace_section("节名", content)` | 替换整节 |

### 特殊关注

1. **用户级 vs 项目级**：
   - 用户级文件较小且稳定，追加风险低
   - 项目级可能包含项目特定配置，需谨慎识别目标节
2. **表格内容**：CLAUE.md 中常用表格（如工具链表），追加行比替换整个节更安全——考虑提供 `append_table_row()` 方法
3. **重复条目检测**：追加前检查节内是否有内容完全相同的行（使用简单的字符串匹配）

---

## 目标类型 3：Memory 文件

### 文件格式

单个 memory 文件 `~/.claude/projects/<project>/memory/<slug>.md`：

```markdown
---
name: <kebab-case-slug>
description: <一句话摘要>
metadata:
  type: user | feedback | project | reference
  originSessionId: <uuid>  # 可选
---

<正文内容>

**Why:** <为什么有这个规则>
**How to apply:** <如何应用>
```

索引文件 `MEMORY.md`：

```markdown
# Memory Index

## Feedback
- [slug-name](slug-name.md) — 简短说明

## Project
- [another](another.md) — 另一个说明
```

### 写入策略

| 操作 | 方法 | 说明 |
|------|------|------|
| **新建 memory** | 创建新 `.md` 文件 + 追加 MEMORY.md 索引行 | 两步操作，任一失败需回滚 |
| **修改 memory** | ❌ 不建议 | 过于危险，建议由用户手动修改 |

### 特殊关注

1. **Memory 命名**：
   - slug 格式：kebab-case，仅字母、数字、连字符
   - 生成规则：英文关键词转 kebab-case，中文用拼音
   - 唯一性：创建前检查同名文件是否已存在
2. **MEMORY.md 索引格式**：
   - 格式：`- [Title](file.md) — hook`（一行一条）
   - 按 type 分节：`## Feedback`、`## Project`、`## User`、`## Reference`
   - 需在正确 type 节下追加，type 节不存在时自动创建
3. **原子性**：
   - 先写 memory 文件，成功后写 MEMORY.md
   - 如果 MEMORY.md 写入失败，删除已创建的 memory 文件
4. **去重**：如果 frontmatter `name` 已存在，提示用户而非覆盖

---

## 目标类型 4：代码约定（CLAUDE.md 子集）

### 文件位置

仅在项目级 CLAUDE.md 中操作，不涉及用户级。

常见节名变体：
- `## 编码风格`
- `## 编码规范`
- `## Code Style`
- `## Coding Conventions`

### 写入策略

与 CLAUDE.md 相同，但增加节名匹配逻辑：

```python
CODE_STYLE_HEADINGS = ["编码风格", "编码规范", "Code Style", "Coding Conventions"]

def find_code_style_section(claude_md_content: str) -> str | None:
    """在 CLAUDE.md 中查找编码风格节名。"""
    for line in claude_md_content.split("\n"):
        if line.startswith("## "):
            heading = line[3:].strip()
            if heading in CODE_STYLE_HEADINGS:
                return heading
    return None
```

### 特殊关注

1. **节名探测**：先尝试已知的节名变体，找不到则新建 `## 编码风格`
2. **内容格式**：代码约定通常是列表（`- `），追加时保持风格一致
3. **不碰其他节**：严格限定只在编码风格节操作，不扩散到其他配置

---

## 重复条目检测

所有追加操作使用同一检测逻辑：

```python
def has_duplicate(section_content: str, new_line: str) -> bool:
    """检查节内容中是否已有相同行（忽略空白和 Markdown 前缀差异）。"""
    normalized_new = new_line.strip().lower()
    for line in section_content.split("\n"):
        normalized = line.strip().lower()
        if normalized == normalized_new:
            return True
    return False
```

---

## 回滚与恢复

| 场景 | 恢复方式 |
|------|----------|
| 写入中崩溃 | `tempfile` 未 rename，原文件完整 |
| 写入后验证失败 | 自动从 `.learn-backups/` 恢复 |
| 并发写入 | `backup_path.exists()` 检测，抛异常阻止 |
| 手动恢复 | 用户从 `.learn-backups/` 选择备份文件 |

备份文件保留策略：保留最近 10 个备份，自动清理旧备份（可选功能）。

---

## 实现优先级

1. **P0** — `SafeFileWriter` 核心类 + 节操作函数
2. **P1** — SKILL.md 写入（最常用场景）
3. **P2** — CLAUDE.md 写入（用户级 + 项目级）
4. **P3** — Memory 写入（两步原子操作 + MEMORY.md 索引）
5. **P4** — 重复检测 + 备份清理
