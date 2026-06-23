在对文件做任何修改前，先说明要改什么，等用户确认后再执行。

## 项目概述

基于 LangGraph 的科研文献综述助手，CS 专业课设。目标用户是想系统入门某个 CS 领域的开发者（非研究员）。场景定位为入门型——帮助用户找到并阅读一个领域的经典必读论文，而非追踪前沿进展。

## 需求分析

两种综述场景的区分：

- **入门型**：数量少（10-30 篇），重质不重量，论文间有演进关系，来源靠人类 curation（课程大纲、awesome-list、survey 论文等）
- **前沿型**：数量大（50-200+ 篇），按子方向分类，来源靠 API 关键词搜索 + 引用图扩散
- 本系统聚焦入门型

## 文献获取调研结论

### 信息源设计

- **Tavily Search + Tavily Extract**：搜 reading list、survey 论文、课程大纲、awesome 仓库，获取经过人类 curation 的论文列表
- **PDF 获取**：对每篇论文标题用 Tavily Search 搜 `"{标题} PDF"`，优先选择 .edu 域名或作者主页的 PDF 链接
- **PDF 解析**：下载后使用 Docling 解析为 Markdown

### Semantic Scholar 调研

优势：结构化数据、免费、CS 领域覆盖好。

关于"按引用量/影响力排序"的局限：高引用 ≠ 适合入门。一篇被引 5000 次的论文可能是极其专精的定理证明，对初学者毫无意义。在入门型场景中，Semantic Scholar 的正确角色是**元数据补全工具**，而非论文发现工具。发现"该读什么"应该由人类 curated 的来源完成。

问题：永远返回 429 限流，完全不可用。

### arXiv 调研

本质是预印本仓库，搜索功能设计目标是"找到那篇论文"而非"发现该读哪些论文"。没有 citation count，没有影响因子，排序基本靠时间。

问题：预印本仓库压根没有收录经典论文。

## 多 Agent 架构

### 整体流程

```
Searcher → Outliner → [Writer × K] → Synthesizer ⇄ Critic → 输出
```

| Agent | 数量 | 职责 |
|---|---|---|
| **Searcher** | 1 | Web Search + Extract 搜 reading list → Web Search 根据论文标题搜 PDF 链接 → 下载并解析 PDF |
| **Outliner** | 1 | 读所有论文的前 xx 字（覆盖摘要），LLM 自行聚类并划分章节，分配论文到各章，产出综述大纲 |
| **Writer** | K（并行） | 每个负责一章，读该章关联论文的全文 Markdown，做跨论文比较分析，产出该章正文 |
| **Synthesizer** | 1 | 汇总各章，写 Introduction 和 Conclusion，消除跨章重复，统一文风 |
| **Critic** | 1 | 审读全文，发现问题退回 Synthesizer 修改，直到通过或达到最大轮数 |

### 关键设计决策

- **Outliner 用 LLM 读摘要聚类，不用 K-means**：入门型论文少（10-30 篇），LLM 直接读摘要聚类并划分大纲更简单直接
- **Writer 并行为 K 个**：每章一个 Writer，各自只关注该章关联的 3-7 篇论文，质量更高
- **Synthesizer 与 Critic 博弈**：整个流程只有一个回环。Clusterer 和 Writer 跑一遍就结束，Synthesizer 拼装初稿后 Critic 审，有问题退回 Synthesizer 改，改完再审，直到通过
- **Searcher 负责完整的信息获取**：包括 PDF 下载和 Docling 解析，产出干净的 Markdown。Writer 面对的是干净文本，不需要关心 PDF 格式问题
- **PDF 全文是加分项而非必须项**：如 PDF 无法获取或解析失败，Writer 退回到仅用标题工作

## 工具选型

Searcher 是唯一需要外部工具的 Agent，其他 Agent 纯靠 LLM 推理。

Tavily Search、Tavily Extract、Dacling

## API 与模型

使用 **DeepSeek V4 Flash** 作为所有 Agent 的底层模型，开启思考模式。

- OpenAI 兼容接口：`base_url="https://api.deepseek.com"`，可直接使用 `openai` SDK 或 LangChain 的 `ChatOpenAI`
- 思考模式：`reasoning_effort="high"` + `extra_body={"thinking": {"type": "enabled"}}`
- 上下文窗口 1M tokens，Flash 更快更便宜，适合批量 Agent 调用
- Searcher 需开启 tool calling
