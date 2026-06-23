# 技术文档：SQLite 持久化、FastAPI 集成、前端设计、PDF 导出

## 1. SQLite 持久化

### 数据库与 ORM

使用 SQLAlchemy 2.0 ORM + SQLite，数据库文件 `surveys.db` 在项目根目录。

```python
from sqlalchemy import create_engine
DATABASE_URL = "sqlite:///surveys.db"
engine = create_engine(DATABASE_URL, echo=False)
```

所有模型继承 `DeclarativeBase`，通过 `Base.metadata.create_all(engine)` 在模块导入时自动建表。

### 数据模型（4 张表）

```
surveys ──1:N──> papers
  │
  ├──1:N──> sections
  │
  └──1:N──> chapters
```

| 表 | 关键字段 | 说明 |
|---|---|---|
| `surveys` | id, topic, status, draft, created_at | 综述主表。status: running/done |
| `papers` | survey_id, paper_id, title, authors, year, markdown, source_type | 论文。source_type: pdf/none |
| `sections` | survey_id, sort_order, title, theme, paper_ids (JSON) | 大纲章节，paper_ids 为论文 ID 列表 |
| `chapters` | survey_id, sort_order, title, content | 各章正文 |

所有子表通过 `cascade="all, delete-orphan"` 级联删除。

### 持久化时机

**开始**：管道启动时 `create_survey(topic)` 创建 survey，status="running"，立即拿到 survey_id。

**结束**：管道完成后 `update_survey_done(survey_id, state)` 一次性批量写入：
- 更新 status="done" + draft 全文
- 写入所有 papers、sections、chapters

中间步骤不持久化——管道运行期间的中间状态仅通过 SSE 流式推送前端，不落库。

### API 查询

- `list_surveys()` — 按创建时间降序，返回 topic + draft 前 200 字预览
- `get_survey(id)` — 返回完整数据：draft 全文 + papers + sections + chapters

---

## 2. FastAPI 集成与 SSE 流式设计

### 端点一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/surveys/stream?topic=...` | SSE 流式生成（核心端点） |
| GET | `/api/surveys` | 历史列表 |
| GET | `/api/surveys/{id}` | 单篇详情 |
| GET | `/api/surveys/{id}/pdf` | PDF 下载 |
| GET | `/` | 静态前端 SPA |

### SSE 事件流架构

核心挑战是**合并两股异步事件流**：LangGraph 的 `astream_events` 和工具代码的进度回调。

```
                    ┌──────────────────┐
                    │   event_q         │
                    │  (asyncio.Queue)  │
                    └──────┬───────────┘
              ┌────────────┴────────────┐
              │                         │
     graph_producer()           progress_producer()
     (async task)               (async task, 0.3s 轮询)
              │                         │
   graph.astream_events()      progress_q (queue.Queue)
   (LangGraph 事件)                   │
                              set_progress_reporter()
                              (tools.py 回调写入)
```

**两个生产者，一个消费者**：

1. `graph_producer` — 异步迭代 `graph.astream_events(initial_state, version="v2")`，将每个事件写入 `event_q`
2. `progress_producer` — 每 0.3 秒从线程安全的 `queue.Queue`（`progress_q`）中批量取出工具进度事件，写入 `event_q`
3. 主循环 — 从 `event_q` 取出事件，按来源分发处理：
   - `"graph"` → 解析 LangGraph 事件（agent_start / token / thinking / agent_done）
   - `"progress"` → 透传为 SSE（tool_start / tool_result / pdf_start / pdf_done）

**关键设计决策**：

- **Progress reporter 回调机制**：`tools.py` 提供 `set_progress_reporter(fn)`，`api.py` 在流开始时注入 `lambda evt: progress_q.put(evt)`。工具代码通过 `_report()` 向回调推送事件，解耦了工具层和传输层
- **超时保护**：主循环用 `asyncio.wait_for(event_q.get(), timeout=1.0)` 防止死锁，同时每轮检查 `graph_task.done()` + `graph_task.exception()` 捕获异常
- **graph 完成后排空**：graph EOF 后额外 drain 一轮 `event_q`，确保残留的 progress 事件不丢失

### SSE 事件类型

| type | 来源 | 携带字段 |
|---|---|---|
| `agent_start` | graph | agent, writer_index, chapter_title, paper_titles 等 |
| `token` | graph | agent, content（LLM 输出文本） |
| `thinking` | graph | agent, content（DeepSeek 思考过程） |
| `agent_done` | graph | agent, papers/outline/chapters/issues |
| `outline` | graph | sections（章节划分结果） |
| `tool_start` | progress | tool, query/url |
| `tool_result` | progress | tool, summary, items |
| `pdf_start` | progress | total |
| `pdf_done` | progress | results（每篇成功/失败/字符数） |
| `done` | — | survey_id, has_pdf |
| `error` | — | message |

### Writer 并行路由

Writer 通过 LangGraph 的 `Send` API 并行扇出。`api.py` 维护 `writer_node_runs` 字典（run_id → writer_index）和 `chat_to_writer` 字典（chat_model_run_id → parent_chain_run_id），确保 token/thinking 事件正确路由到对应 Writer 卡片。

---

## 3. 前端设计

### 技术方案

纯静态 SPA，由 FastAPI 的 `StaticFiles` 挂载在 `/`。使用原生 EventSource API 连接 SSE 端点，无框架依赖。

### 视觉设计

| 要素 | 选择 |
|---|---|
| 背景色 | `#FAFAF9`（暖白） |
| 卡片色 | `#FFFFFF` |
| 强调色 | `#B5834A` / `#D4A574`（暖金） |
| 展示字体 | Crimson Pro（标题、Agent 标签） |
| 正文字体 | Inter（正文、UI 控件） |

### 布局结构

```
┌──────────┬─────────────────────────────────┐
│ Sidebar  │  Hero + 输入框                   │
│ 220px    ├─────────────────────────────────┤
│          │  Pipeline 卡片（纵向排列）        │
│ History  │  ┌ Searcher ──────────────────┐ │
│          │  │ activity-stream            │ │
│          │  │ pdf-progress               │ │
│          │  │ result                     │ │
│          │  └────────────────────────────┘ │
│          │  ┌ Outliner ──────────────────┐ │
│          │  └────────────────────────────┘ │
│          │  ┌─ writers-row (grid) ───────┐ │
│          │  │ Writer1 │ Writer2 │ ...    │ │
│          │  └────────────────────────────┘ │
│          │  ┌ Synthesizer ───────────────┐ │
│          │  └────────────────────────────┘ │
│          │  ┌ Critic ────────────────────┐ │
│          │  └────────────────────────────┘ │
│          ├─────────────────────────────────┤
│          │  Result（Markdown 渲染 + PDF 按钮）│
└──────────┴─────────────────────────────────┘
```

### SSE 事件处理

前端 `handleSSEEvent` 根据 `data.type` 分发：

- **`agent_start`**：创建卡片（Writer 用 `writers-row` grid，其余串行全宽）。Outliner 显示论文标题列表，Synthesizer 显示章标题列表
- **`token`**：追加文本到对应卡片的 `.agent-content`，尾部带闪烁光标
- **`thinking`**：追加到 `.thinking-box`（Searcher 除外——不展示思考过程）
- **`tool_start` / `tool_result`**：Searcher 专用，追加到 `.activity-stream` 统一活动流，按时间顺序与思考内容交错展示
- **`pdf_start`**：显示"开始下载并解析 PDF（共 N 篇）…"
- **`pdf_done`**：显示"PDF 下载解析完成: X/Y 篇成功"
- **`agent_done`**：卡片标记为完成（绿色状态点）。Searcher 显示论文列表，Synthesizer 显示全文
- **`outline`**：缓存章节信息，供后续 Writer 卡片创建
- **`done`**：获取完整 survey 数据 → 渲染 Markdown → 若 has_pdf 则显示 Download PDF 按钮
- **`error`**：显示红色错误提示

### 历史记录

侧边栏加载 `GET /api/surveys` 显示所有历史 survey（topic + 日期）。点击任一 history item 会获取详情、渲染 Markdown、并显示 PDF 下载按钮。

---

## 4. PDF 转化与导出

### 技术选型

| 方案 | 说明 |
|---|---|
| LaTeX 引擎 | [Tectonic](https://tectonic-typesetting.github.io/)（Rust 实现，不依赖系统 TeX 发行版） |
| 安装方式 | `brew install tectonic`（系统级二进制 `/opt/homebrew/bin/tectonic`） |
| 文档类 | `ctexart`（内置中文支持，无需额外配置字体） |

选择 Tectonic 的原因：tectonic 在 PyPI 上实际没有任何发布版本（空包），因此只能通过系统包管理器安装独立二进制。

### 流程

```
Synthesizer 输出的 Markdown 综述
        │
        ▼
    md2tex() 逐行转换
        │
        ▼
    LaTeX body（已转义 + 格式化）
        │
        ▼
  填入 LATEX_TEMPLATE（ctexart, 2.5cm 页边距）
        │
        ▼
   写入 output/survey_{id}.tex
        │
        ▼
  tectonic -X compile → output/survey_{id}.pdf
        │
        ▼
  GET /api/surveys/{id}/pdf → FileResponse
```

### md2tex 转换规则

| Markdown | LaTeX |
|---|---|
| `# Title` | `\section*{Title}` |
| `## Title` | `\subsection*{Title}` |
| `### Title` | `\subsubsection*{Title}` |
| `**bold**` | `\textbf{bold}` |
| `*italic*` | `\textit{italic}` |
| `## References` 后的 `[N] ...` | `\begin{enumerate}` + `\item` |

特殊字符转义覆盖：`\`, `&`, `%`, `$`, `#`, `_`, `{`, `}`, `~`, `^`。`[N]` 引用标记在转义前被保存为占位符，转义完成后恢复，避免被误转义。

### 调用方式

在 `api.py` 管道末尾通过 `asyncio.to_thread` 在线程池中执行（避免阻塞事件循环），设置了 60 秒超时。PDF 生成失败不影响综述结果——`done` 事件中 `has_pdf` 为 false，前端不显示下载按钮。

```python
pdf_path = await asyncio.to_thread(generate_pdf, survey_id, accumulated["draft"], topic)
```
