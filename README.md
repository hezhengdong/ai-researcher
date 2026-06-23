AI Researcher

基于 LangGraph 多 Agent 流水线的科研文献综述生成器。（太原理工大学软件工程 2023 级大三下人工智能II方向课设）

相关文档

- [research-notes.md](https://github.com/hezhengdong/ai-researcher/blob/main/research-notes.md) — 程序作者人工撰写的过程记录与思考
- [CLAUDE.md](https://github.com/hezhengdong/ai-researcher/blob/main/CLAUDE.md) — AI 为本项目撰写的技术文档

**如何启动？**

1. 科学上网（Tavily API 需要）

2. 复制 `.env.example` 为 `.env`，填入自己的 LLM 与搜索工具 API Key：

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_API_KEY=你的Key

TAVILY_API_KEY=你的Key
```

`LLM_BASE_URL` / `LLM_MODEL` 可换成任意 OpenAI 兼容接口。

3. Python 3.13+，通过 uv 管理依赖：

```bash
uv sync
uv run uvicorn api:app
```

打开 `http://127.0.0.1:8000` 使用。

4. （可选）PDF 导出需系统安装 [Tectonic](https://tectonic-typesetting.github.io/)（`brew install tectonic`）。未安装时综述正常生成，仅无法下载 PDF。
