# 分析 Session 的 Spawn 方式调研

## 调研日期
2026-07-29

## 结论摘要

推荐使用 **Anthropic API (Messages API)** 方案从 Python 脚本启动"仅做分析"的 Claude 会话。
API 方案天然无文件系统访问、输出为结构化 JSON、成本可控（可按需选择模型级别）、无需处理 CLI 子进程的超时和权限沙箱问题。如果短期需要快速验证，CLI `--print` 模式配合 `--tools ""` 也能实现只读分析，但输出解析和权限控制的稳定性不如 API 方案。

## 方案对比

### 方案 A: claude CLI headless

- **调用方式**: `claude -p "prompt" --output-format json --tools "" --no-session-persistence`
- **权限控制**: 通过 `--allowedTools` / `--disallowedTools` / `--tools ""` 限制工具集
- **成本**: 与交互式使用相同，由当前配置的 model 决定
- **优缺点**:
  - 优点: 零设置成本，直接用现有 CLI；system prompt、skills 复用已有配置
  - 缺点: 输出文本嵌入在 JSON 的 `result` 字段中，需二次解析；子进程超时管理复杂；权限沙箱依赖 CLI 参数组合

### 方案 B: Anthropic API

- **调用方式**: Python `anthropic` SDK → `client.messages.create()`
- **权限控制**: 默认无文件系统访问，不传 `tools` 参数即为纯文本分析
- **成本**: 按 token 计费，可自由选择模型：Sonnet 5 ($3/$15 每百万 token)、Haiku 4.5 ($1/$5)
- **优缺点**:
  - 优点: 天然只读隔离；输出为结构化 Pydantic 模型；完全控制 system prompt 和 model；支持 prompt caching 降低重复分析成本
  - 缺点: 需要 API key；需自行管理 prompt 模板和上下文拼接

## 各方向详细分析

### 1. CLI headless 模式

**调用方式**（主源：`claude --help` 实测输出，v2.1.210）:

```bash
# 非交互模式，JSON 输出
echo "input" | claude -p "Your prompt" --output-format json --no-session-persistence

# 或直接传入 prompt
claude -p "分析文件" --output-format json
```

**关键参数**:

| 参数 | 说明 | 分析用途 |
|------|------|----------|
| `-p, --print` | 非交互模式，打印结果后退出 | 核心参数，用于脚本化调用 |
| `--output-format json` | JSON 格式输出（可选: text, json, stream-json） | 结构化的机器可读输出 |
| `--no-session-persistence` | 不保存会话到磁盘 | 分析任务的会话无需持久化 |
| `--tools ""` | 禁用所有内置工具 | 实现只读分析的关键参数 |
| `--allowedTools, --allowed-tools <tools...>` | 允许的工具列表（如 "Read"） | 白名单模式，限制工具集 |
| `--disallowedTools, --disallowed-tools <tools...>` | 禁用的工具列表（如 "Edit,Write"） | 黑名单模式 |
| `--system-prompt <prompt>` | 自定义 system prompt | 定制分析行为 |
| `--model <model>` | 指定模型 | 选择推理能力级别 |
| `--max-budget-usd <amount>` | API 调用最大花费 | 成本上限保护（仅 --print 模式） |
| `--safe-mode` | 禁用所有自定义配置 | 干净环境排查问题 |
| `--permission-mode <mode>` | 权限模式（acceptEdits/auto/bypassPermissions/manual/dontAsk/plan） | 控制写入行为 |
| `--json-schema <schema>` | JSON Schema 输出验证 | 约束输出格式 |

**实测验证**（2026-07-29）:

1. **`--tools ""` 禁用所有工具** — 实测通过，模型仅输出文本，无工具调用
2. **`--allowedTools Read` 限制只读** — 实测通过，无 permission_denials
3. **`--disallowedTools Edit,Write` 黑名单模式** — 实测通过，Edit/Write 被禁用
4. **JSON 输出格式** — 实测返回结构包含 `result`, `usage`, `total_cost_usd`, `is_error`, `permission_denials` 等字段
5. **`--output-format stream-json` 需要 `--verbose`** — 否则报错

**限制**: 没有"纯只读模式"的一键开关；输出中的 `result` 是纯文本，如模型输出思考过程需自行过滤。

### 2. API 直接调用

**调用方式**（主源：claude-api skill `python/claude-api/README.md`）:

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=16000,
    system="你是一个代码分析专家...",
    messages=[{
        "role": "user",
        "content": f"请分析以下文件内容:\n\n{file_content}"
    }],
    thinking={"type": "adaptive", "display": "omitted"},
    # 不传 tools → 零文件系统访问
)
```

**当前模型 ID 和定价**（主源：claude-api skill，缓存 2026-06-24）:

| 模型 | Model ID | Context | Input $/1M token | Output $/1M token |
|------|----------|---------|------------------|-------------------|
| Claude Fable 5 | `claude-fable-5` | 1M | $10.00 | $50.00 |
| Claude Opus 4.8 | `claude-opus-4-8` | 1M | $5.00 | $25.00 |
| Claude Sonnet 5 | `claude-sonnet-5` | 1M | $3.00 ($2.00 试用) | $15.00 ($10.00 试用) |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | $1.00 | $5.00 |

**分析任务典型成本估算**（5000 input tokens + 2000 output tokens）:

| 模型 | 单次成本 |
|------|---------|
| Haiku 4.5 | ~$0.015 |
| Sonnet 5 | ~$0.045 |
| Opus 4.8 | ~$0.075 |

**对比总结**:

| 维度 | CLI (`-p` 模式) | API (Messages API) |
|------|----------------|-------------------|
| 调用方式 | `subprocess.run(["claude", "-p", ...])` | `client.messages.create(...)` |
| 文件系统访问 | 默认有（需手动禁用） | 默认无（不传 tools 即隔离） |
| system prompt | 可自定义 (`--system-prompt`) | 完全控制，支持多行模板 |
| tools 控制 | 白名单/黑名单组合 | 不传 tools 即零工具 |
| 输出格式 | JSON 外壳 + 纯文本 `result` | 结构化 `response.content` (按 block 分离) |
| 结构化输出 | `--json-schema` 参数可用 | `messages.parse()` + Pydantic 强类型 |
| 成本 | 按 CLI 配置的模型计费 | 按 API 调用 token 计费 |
| 超时处理 | subprocess timeout + 手动 kill | SDK 内置超时和自动重试 |
| prompt caching | CLI 自动处理 | 需手动配置 `cache_control` |
| 复杂度 | 中等（子进程管理） | 低（SDK 调用） |

### 3. 权限沙箱

**CLI 方案权限控制**（主源：`claude --help` + 实测）:

多层权限控制机制：
1. **工具白名单** (`--allowedTools`): 如 `--allowedTools Read`
2. **工具黑名单** (`--disallowedTools`): 如 `--disallowedTools Edit,Write`
3. **完全禁用工具** (`--tools ""`): 禁用所有内置工具
4. **权限模式** (`--permission-mode`): `acceptEdits` / `auto` / `bypassPermissions` / `manual` / `dontAsk` / `plan`
5. **安全模式** (`--safe-mode`): 禁用 CLAUDE.md、skills、plugins、hooks

**API 方案权限隔离**（主源：claude-api skill）:

API 方案的 Messages API 默认**不提供任何文件系统访问**。不传 tools 即 100% 只读。分析 session 只需将"学习指令 + 目标文件内容"拼接为 user message 传入。

```python
# 天然只读，无需任何权限配置
response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=16000,
    system="你是一个代码分析专家...",
    messages=[{"role": "user", "content": f"分析以下代码:\n\n{code}"}],
    # 不传 tools → 无任何文件操作能力
)
```

**安全隔离对比**:

| 维度 | CLI `--tools ""` | API 不传 tools |
|------|------------------|-----------------|
| 文件写入 | 依赖参数正确配置 | 物理不可能 |
| 文件读取 | 依赖参数正确配置 | 物理不可能 |
| 命令执行 | 依赖 `Bash` 被禁用 | 物理不可能 |
| prompt 注入风险 | 存在（内容经 CLI 系统处理） | 低（纯 API 调用） |
| 配置隔离 | 依赖 CLI 参数组合 | 天然隔离 |
| 验证难度 | 中等 | 低（不传 tools 即可） |

### 4. Model 选择建议

**分析任务特点**: 阅读文件内容 + 应用学习指令 -> 产出改进建议。需要一定推理能力，但不如复杂编程任务高。

| 模型 | 推理能力 | Context | 适用场景 | Input/Output 每百万 token |
|------|---------|---------|---------|--------------------------|
| Opus 4.8 | 最强 | 1M | 最复杂分析、长链推理 | $5 / $25 |
| Sonnet 5 | 强 | 1M | 代码分析、Review、建议 | $3 ($2 试用) / $15 ($10 试用) |
| Haiku 4.5 | 中 | 200K | 简单分类、快速分析 | $1 / $5 |

**推荐**: **Sonnet 5** 是分析/建议类任务的最佳性价比选择：
- 推理能力足够处理代码分析和改进建议
- 成本是 Opus 的 60%（试用期仅 40%）
- 1M context window，可一次传入大量文件内容
- 支持 adaptive thinking

对于学习指令理解 + 改进建议产出的场景，**不建议使用 Haiku**，因为该任务需要理解抽象概念并对比分析，对推理能力有一定要求。

### 5. 超时处理策略

**subprocess.run() timeout 行为**（主源：macOS + Python 3.12 实测）:

实测确认 macOS 上 `subprocess.run()` 超时后子进程被 SIGKILL 终止（returncode=-9），需在 `except TimeoutExpired` 中手动调用 `p.kill()`。

**跨平台兼容性**:
- Unix (Linux/macOS): `p.kill()` 发送 SIGKILL 强制终止
- Windows: `p.kill()` 调用 `TerminateProcess`
- 推荐做法: 始终手动 kill + wait

**API 方案超时处理**（主源：claude-api skill）:

```python
# SDK 默认 10 分钟超时, 2 次自动重试
client = anthropic.Anthropic(timeout=120.0, max_retries=2)
```

**超时建议**:
- 分析任务通常 2-5 分钟可完成
- 超过 5 分钟说明可能输入过大或模型在过深的思考中
- 超时后策略：降 effort 重试 → 降级模型 → 拆分输入

### 6. 输出解析方案

**CLI `--output-format json` 模式**（主源：实测 v2.1.210）:

实测 JSON 输出包含 `result`, `usage`, `total_cost_usd`, `is_error`, `permission_denials`, `stop_reason` 等字段。`result` 是单一大文本，如模型思考和答案混在一起需自行过滤。

**API 方案输出解析**（主源：claude-api skill）:

API 响应是结构化对象，content 按 block 类型分离：

```python
for block in response.content:
    if block.type == "text":
        print(block.text)       # 最终答案
    elif block.type == "thinking":
        # 仅在 display="summarized" 时有文本
        print(f"[思考] {block.thinking}")
```

- `thinking={"type": "adaptive", "display": "omitted"}` 隐藏思维链
- 支持 `messages.parse()` + Pydantic 进行结构化输出（CLI 方案的 `--json-schema` 仅做验证，不够方便）

## 推荐方案

### 首选：Anthropic API (Messages API)

**理由**:

1. **安全隔离最彻底**: 不传 tools 参数即物理上不可能写入文件或执行命令
2. **输出解析最简单**: 结构化 Python 对象，thinking 和 text 天然分离
3. **成本最可控**: 可选用 Sonnet 5 (~$0.045/次) 或 Haiku 4.5 (~$0.015/次)
4. **可扩展性强**: 支持 structured outputs、prompt caching、streaming
5. **无需子进程管理**: 避免 CLI 方案的超时、kill、跨平台兼容性问题

**实现模板**:

```python
import anthropic
from pathlib import Path
from typing import Optional

ANALYSIS_SYSTEM_PROMPT = """\
你是一个代码分析和改进建议专家。你的任务是：
1. 仔细阅读提供的文件内容，理解其设计意图和结构
2. 对照已有的学习指令（设计模式、最佳实践），分析文件中存在的问题
3. 给出具体、可操作的改进建议

输出格式：
- 先给出总体评价（2-3 句）
- 然后逐条列出问题和建议，每条包含：问题描述、严重程度(高/中/低)、改进建议
- 只分析，不修改代码。不要输出具体代码实现，仅说明改进方向。
"""

ANALYSIS_MODEL = "claude-sonnet-5"
ANALYSIS_TIMEOUT = 120  # 秒


def analyze_file(
    file_path: str,
    learning_instructions: Optional[str] = None,
) -> str:
    """分析单个文件并返回改进建议。"""
    content = Path(file_path).read_text(encoding="utf-8")
    client = anthropic.Anthropic(timeout=ANALYSIS_TIMEOUT, max_retries=2)

    system_prompt = ANALYSIS_SYSTEM_PROMPT
    if learning_instructions:
        system_prompt += f"\n\n## 参考学习指令\n{learning_instructions}"

    response = client.messages.create(
        model=ANALYSIS_MODEL,
        max_tokens=8000,
        system=system_prompt,
        thinking={"type": "adaptive", "display": "omitted"},
        messages=[{
            "role": "user",
            "content": f"请分析以下文件 ({file_path}):\n\n```\n{content}\n```"
        }],
    )

    texts = [b.text for b in response.content if b.type == "text"]
    return "\n".join(texts)
```

### 备选：CLI `--print` 模式

**适用场景**: 快速原型验证、已有 CLI 配置需复用、不能使用 API key 的环境。

```python
import json
import subprocess
from pathlib import Path
from typing import Optional


def analyze_file_cli(
    file_path: str,
    learning_instructions: Optional[str] = None,
    timeout: int = 300,
) -> dict:
    """通过 CLI --print 模式分析文件。"""
    content = Path(file_path).read_text(encoding="utf-8")

    prompt = "分析以下文件的设计问题和改进方向，给出具体建议。只分析不修改代码。"
    if learning_instructions:
        prompt += f"\n\n参考以下学习指令:\n{learning_instructions}"
    prompt += f"\n\n目标文件:\n```\n{content}\n```"

    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--output-format", "json",
                "--tools", "",
                "--no-session-persistence",
            ],
            capture_output=True, text=True, timeout=timeout,
        )
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"is_error": True, "result": "", "error": f"Timeout ({timeout}s)"}
    except json.JSONDecodeError:
        return {"is_error": True, "result": "", "error": "JSON parse failed"}
```

## 待测实验证项

1. **CLI `--tools ""` 的长期稳定性**: 升级后是否可能引入 bypass 工具限制的边缘情况？
2. **API response 中 thinking block 的存在条件**: `display: "omitted"` 后 thinking block 是否仍在数组中但 text 为空？
3. **Haiku 4.5 在复杂代码分析上的表现**: 是否能准确理解抽象的设计模式概念？建议对代表性文件进行 A/B 测试
4. **Prompt caching 在分析 session 中的实际收益**: 共享 system prompt 能实际降低多少成本？
5. **大文件分析的成本**: 目标文件超过 50KB 时，是否需要在分析前对文件进行分块处理？
