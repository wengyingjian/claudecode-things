# 分析 Session 的 Spawn 方式调研

## 调研日期
2026-07-29

## 结论摘要

推荐 **方案 A（claude CLI headless）** 作为主要方案：使用 `claude -p --tools "" --output-format json` 启动纯分析 session。理由：
1. 零额外复杂度——无需安装 SDK、无需管理 API key 生命周期
2. 天然权限隔离——`--tools ""` 禁用所有写入工具，只输出分析文本
3. 结构化输出——`--output-format json` 提供可解析的 JSON，包含结果文本、token 用量、耗时
4. Python `subprocess.run()` 即可调用，配合 `stdout` 捕获输出

**备选方案 B（Anthropic API）** 在需要更细粒度控制（自定义 system prompt、精确 token 预算、流式输出）时使用。

---

## 方案对比

| 维度 | 方案 A: claude CLI headless | 方案 B: Anthropic API |
|------|---------------------------|----------------------|
| 调用方式 | `subprocess.run(["claude", "-p", ...])` | `client.messages.create(...)` |
| 安装依赖 | 无需额外安装（claude CLI 已就绪） | `pip install anthropic` |
| 权限控制 | `--tools ""` 禁用所有工具 | 不传 `tools` 参数，天然无文件访问 |
| 输出格式 | JSON（含 result, usage, cost） | Python dict（结构化对象） |
| 成本可见性 | `total_cost_usd` 字段直接可见 | 需自行计算 `usage.input_tokens * rate` |
| 复杂度 | 低 | 中（需管理 API key、超时、重试） |
| 可控性 | 中（CLI 参数决定行为） | 高（完全控制请求参数） |

---

## 各方向详细分析

### 1. CLI headless 模式

#### 调用方式

```bash
# 无工具纯分析（推荐）
claude -p --tools "" --output-format json --model sonnet "分析指令..."

# 只允许读取文件
claude -p --tools "Read" --output-format json "分析指令..."

# 文本输出
claude -p --tools "" --output-format text "分析指令..."
```

**参数说明：**

| 参数 | 说明 |
|------|------|
| `-p` / `--print` | 非交互模式，输出结果后退出 |
| `--tools ""` | 禁用所有工具（空字符串 = 无工具），纯文本分析 |
| `--tools "Read"` | 只允许 Read 工具（可读取文件） |
| `--output-format json` | JSON 结构化输出 |
| `--output-format text` | 纯文本输出 |
| `--output-format stream-json` | 实时流式 JSON 输出 |
| `--model sonnet/opus/haiku` | 模型选择 |
| `--system-prompt "..."` | 自定义系统提示词 |
| `--max-budget-usd N` | 最大花费限制（美元） |
| `--no-session-persistence` | 不保存 session |
| `--include-partial-messages` | 流式输出中间结果（仅 stream-json） |

**来源**：`claude --help` 实测输出（2026-07-29）

#### JSON 输出格式

实测 `--output-format json` 返回结构：

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "分析结果文本...",
  "stop_reason": "end_turn",
  "duration_ms": 1071,
  "num_turns": 1,
  "total_cost_usd": 0.0115,
  "usage": {
    "input_tokens": 2211,
    "output_tokens": 19,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0
  },
  "session_id": "df661953-8178-406a-b07c-4baeddaf1aee",
  "terminal_reason": "completed"
}
```

**来源**：实测 `claude -p --tools "" --model sonnet --output-format json "Reply with EXACTLY this JSON: {\"test\": true}"`（2026-07-29）

#### 权限控制

- **`--tools ""`**（空字符串）：禁用所有工具，session 无法读写文件、执行命令、编辑代码。**这是最安全的分析模式。**
- **`--tools "Read"`**：只允许 Read 工具，分析 session 可以读取目标文件但无法修改。
- **`--tools "Read,Grep,Glob"`**：允许读取、搜索、文件匹配，但不能写入。
- **`--disallowedTools "Write,Edit,Bash"`**：黑名单模式，禁止特定工具。

**注意**：`--tools ""` 实测生效，session 确实无任何工具可用。

#### 优缺点

| 优点 | 缺点 |
|------|------|
| 零依赖，claude CLI 已安装 | CLI 版本升级可能改变行为 |
| 内置权限隔离 | 无法精确控制 system prompt（除非用 `--system-prompt`） |
| JSON 输出含 cost/usage 信息 | `--max-turns` 参数**不存在**（仅 `--max-budget-usd`） |
| `subprocess.run()` 即可调用 | 依赖 shell 环境，需确保 `claude` 在 PATH 中 |
| 自动处理认证（OAuth/API key） | 无法自定义 `temperature`/`effort` 等参数 |

---

### 2. Anthropic API 直接调用

#### 调用方式

```python
import anthropic

client = anthropic.Anthropic()  # 需要 ANTHROPIC_API_KEY 环境变量

response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=16000,
    system="你是一个代码分析专家。根据学习指令和目标文件内容，产出改进建议。",
    messages=[
        {
            "role": "user",
            "content": f"## 学习指令\n{instruction}\n\n## 目标文件\n{file_content}"
        }
    ],
)

# 提取文本
result = next(b.text for b in response.content if b.type == "text")
```

**来源**：claude-api skill（`python/claude-api/README.md`），缓存日期 2026-06-24

#### 当前模型定价

| Model | Input $/1M tokens | Output $/1M tokens |
|-------|-------------------|---------------------|
| `claude-opus-4-8` | $5.00 | $25.00 |
| `claude-sonnet-5` | $3.00 ($2.00 intro) | $15.00 ($10.00 intro) |
| `claude-haiku-4-5` | $1.00 | $5.00 |

**来源**：claude-api skill，`SKILL.md` § Current Models（缓存 2026-06-24）

#### 权限控制

- **天然隔离**：Messages API 默认无文件系统访问，只有显式传入 `tools` 参数才会给模型工具
- **不传 `tools`** = 纯文本对话，模型完全无法读写文件
- **需要读取目标文件时**：将文件内容通过 `messages[].content` 传入，模型在文本中分析
- 无需额外配置即可实现"分析 session 看不到对话全文"——只传学习指令和目标文件内容

#### 优缺点

| 优点 | 缺点 |
|------|------|
| 完全控制请求参数（model, max_tokens, system 等） | 需要安装 `anthropic` SDK（`pip install anthropic`） |
| 天然文件隔离（不传 tools 即无访问） | 需要管理 API key |
| 支持流式输出（`client.messages.stream()`） | 需自行计算 cost |
| 结构化 Python 对象，易于解析 | 需自行处理超时、重试 |
| 精确控制 input（只传需要的内容） | 需管理 HTTP 连接 |

---

### 3. 权限沙箱

| 需求 | CLI 方案 | API 方案 |
|------|---------|---------|
| 禁用文件写入 | `--tools ""` 禁用所有工具 | 不传 `tools` 参数 |
| 只读文件访问 | `--tools "Read"` 只允许读取 | 在 `messages` 中传入文件内容 |
| 只分析学习指令+目标文件 | 通过 prompt 内容控制（无会话历史） | 精确控制 `messages` 数组内容 |
| 禁止网络访问 | `--tools ""` 禁用 web_search/web_fetch | 不传入 web_search/web_fetch tool |

**结论**：两种方案都能满足安全要求。CLI 方案通过 `--tools ""` 禁用所有工具更简洁；API 方案通过不传 tools 和控制 messages 内容更精细。

---

### 4. Model 选择建议

分析任务特点：阅读学习指令 + 目标文件内容 → 产出改进建议。这是一个**中等复杂度**的推理任务，需要理解代码/配置结构并给出可操作建议。

| Model | 适用场景 | 推荐 |
|-------|---------|------|
| `sonnet` (Sonnet 5) | **默认推荐**。推理能力强，速度快，性价比高。$2/$10 per 1M（intro 价） | ✅ 首选 |
| `opus` (Opus 4.8) | 需要最强推理能力时使用。$5/$25 per 1M，成本是 Sonnet 的 2.5 倍 | 复杂分析时 |
| `haiku` (Haiku 4.5) | 简单分类/快速检查。$1/$5 per 1M | ❌ 不推荐 |

**推荐策略**：默认使用 `sonnet`，在分析结果质量不满足要求时升级到 `opus`。

**来源**：claude-api skill § Current Models + 实测经验

---

### 5. 超时处理策略

#### CLI 方案

```python
import subprocess
import json

try:
    result = subprocess.run(
        ["claude", "-p", "--tools", "", "--output-format", "json",
         "--model", "sonnet", prompt],
        capture_output=True, text=True, timeout=300  # 5分钟超时
    )
    if result.returncode == 0:
        output = json.loads(result.stdout)
    else:
        # 处理 CLI 错误
        print(f"CLI error: {result.stderr}")
except subprocess.TimeoutExpired:
    # 超时处理：kill 子进程，可考虑重试或降级
    print("Analysis timed out after 300s")
```

- `subprocess.run(timeout=N)` 超时后自动 kill 子进程，跨平台兼容（Unix `SIGTERM` → `SIGKILL`）
- 5 分钟对分析类任务通常足够
- 超时后可选择：重试（降低 model 为 haiku）、告知用户超时、降级为简单分析

#### API 方案

```python
import anthropic

client = anthropic.Anthropic(timeout=300.0)  # 5分钟

try:
    response = client.messages.create(...)
except anthropic.APITimeoutError:
    # 超时处理
    ...
```

- SDK 默认超时 10 分钟，可通过 `timeout` 参数配置（Python: 秒）
- SDK 自动重试（默认 2 次），覆盖 408/409/429/5xx
- 流式调用可避免 HTTP 超时：
  ```python
  with client.messages.stream(model=..., max_tokens=..., messages=...) as stream:
      message = stream.get_final_message()
  ```

**来源**：claude-api skill + Python `subprocess` 文档

---

### 6. 输出解析方案

#### CLI 方案解析

```python
import json
import subprocess

result = subprocess.run(
    ["claude", "-p", "--tools", "", "--output-format", "json",
     "--model", "sonnet", prompt],
    capture_output=True, text=True, timeout=300
)

if result.returncode == 0:
    data = json.loads(result.stdout)
    if data.get("is_error"):
        raise RuntimeError(f"CLI analysis error: {data.get('result')}")
    analysis_text = data["result"]
    cost = data["total_cost_usd"]
    tokens = data["usage"]
else:
    raise RuntimeError(f"CLI failed: {result.stderr}")
```

- JSON 输出结构稳定，`result` 字段是分析文本
- `is_error` 标志可检测分析失败
- `total_cost_usd` 和 `usage` 提供成本可见性

#### API 方案解析

```python
response = client.messages.create(...)

# 提取文本（排除 thinking 块）
texts = [b.text for b in response.content if b.type == "text"]
result = "\n".join(texts)

# 成本计算
input_cost = response.usage.input_tokens * 0.000003  # Sonnet 5: $3/1M
output_cost = response.usage.output_tokens * 0.000015  # Sonnet 5: $15/1M
total_cost = input_cost + output_cost
```

---

## 推荐方案

### 首选：CLI headless + `--tools ""`

```python
def run_analysis(instruction: str, target_file_content: str) -> dict:
    """启动分析 session 并返回结构化结果。"""
    system_prompt = (
        "你是一个代码改进分析专家。根据学习指令和目标文件内容，"
        "分析应该做出哪些改进。对于每条建议，请说明：\n"
        "1. 改进领域（skill prompt / CLAUDE.md / memory / 代码约定）\n"
        "2. 具体改进内容\n"
        "3. 改进理由\n"
        "4. 是新规则还是修正已有规则"
    )
    
    full_prompt = (
        f"{system_prompt}\n\n"
        f"## 学习指令\n{instruction}\n\n"
        f"## 目标文件内容\n{target_file_content}"
    )
    
    result = subprocess.run(
        ["claude", "-p", "--tools", "",
         "--output-format", "json",
         "--model", "sonnet",
         "--no-session-persistence",
         full_prompt],
        capture_output=True, text=True, timeout=300
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"CLI failed: {result.stderr}")
    
    return json.loads(result.stdout)
```

**选择理由**：
1. **零依赖**：claude CLI 已安装，无需 pip install
2. **简单可靠**：`subprocess.run()` 是 Python 标准库
3. **安全隔离**：`--tools ""` 确保无文件写入
4. **成本可见**：JSON 输出自带 `total_cost_usd`
5. **认证无感**：CLI 自动处理 OAuth/API key

### 备选：Anthropic API

在以下场景切换为 API 方案：
- 需要精确控制 system prompt（超过 CLI `--system-prompt` 限制）
- 需要流式输出来改善用户等待体验
- 需要自定义 `effort`/`max_tokens` 等参数调优
- CLI 行为变化导致解析不稳定

### 不要使用的方案

- **Claude Agent SDK**（`claude-agent-sdk`）：自带 Read/Write/Edit/Bash 等工具，权限控制复杂，不适合纯分析场景
- **Managed Agents**：过于重量级，用于单次分析不划算
