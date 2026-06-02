# Nik Project Hunter

企业级 AI 项目情报系统 — 自动发现、AI 分析、评分、推送招投标项目信息。

Enterprise AI-powered procurement intelligence system — automated discovery, AI analysis, scoring, and notification of government bidding projects.

---

项目代码位于 [`projects/NikProjectHunter/`](./projects/NikProjectHunter/)，请进入该目录查看完整文档。

The project source code is located in [`projects/NikProjectHunter/`](./projects/NikProjectHunter/). Please navigate there for full documentation.

---

## 快速启动 / Quick Start

```bash
cd projects/NikProjectHunter
cp .env.example .env
# 编辑 .env 配置 LLM_API_KEY 和 POSTGRES_PASSWORD
docker compose up -d
```

## 技术栈 / Tech Stack

**FastAPI + PostgreSQL (pgvector) + Redis + Playwright + LLM (DeepSeek/OpenAI/Claude)**

详见 [完整 README](./projects/NikProjectHunter/README.md)。
