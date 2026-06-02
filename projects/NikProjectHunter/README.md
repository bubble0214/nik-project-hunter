# Nik Project Hunter

企业级 AI 项目情报系统 — 自动发现、AI 分析、评分、推送招投标项目信息。

Enterprise AI-powered procurement intelligence system — automated discovery, AI analysis, scoring, and notification of government bidding projects.

---

## 功能特性 / Features

### 核心功能
- **多源爬虫** — 自动抓取多个政府采购网站的项目信息（中国政府采购网、北京/天津/河北公共资源交易平台等）
- **AI 智能分析** — 集成 LLM（DeepSeek / OpenAI / Claude），对项目进行自动分析和商机评分
- **语义过滤** — 基于向量相似度和 AI 判断的智能项目筛选
- **企业信号 Intelligence** — 监听企业招聘、新闻、高管变动、政策动态等多维度信号
- **销售辅助** — 客户关系图谱、跟进策略推荐、报价策略生成
- **定时调度** — 支持 cron 表达式和固定间隔的自动爬取
- **多渠道通知** — 企业微信机器人推送
- **完整 REST API** — 基于 FastAPI 的 RESTful 接口

### 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI (Python 3.11+) |
| 数据库 | PostgreSQL 17 + pgvector |
| 缓存 | Redis 7 |
| 浏览器自动化 | Playwright (Chromium) |
| AI 集成 | OpenAI SDK（兼容 DeepSeek / Claude 等） |
| 任务调度 | APScheduler |
| 容器化 | Docker Compose |
| 日志 | Loguru |

---

## 快速开始 / Quick Start

### 前置条件 / Prerequisites

- Docker & Docker Compose
- LLM API Key（DeepSeek / OpenAI / Claude）

### 一键启动 / One-Click Start

```bash
# 1. 克隆仓库
git clone https://github.com/bubble0214/nik-project-hunter.git
cd nik-project-hunter

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少设置：
#   - LLM_API_KEY
#   - POSTGRES_PASSWORD
#   - PGADMIN_PASSWORD（开发环境）

# 3. 启动所有服务
docker compose up -d

# 4. 查看日志
docker compose logs -f app
```

启动后访问 http://localhost:8000 即可看到 API 根路径，访问 http://localhost:8000/docs 查看 Swagger 文档。

### 开发模式

```bash
# 无需 Docker，直接运行
pip install -r requirements.txt
playwright install chromium

# 确保 PostgreSQL 和 Redis 已启动，配置好 .env 后：
python -m app.main
```

---

## 环境变量 / Environment Variables

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | 是 | PostgreSQL 连接地址 |
| `LLM_API_KEY` | 是 | LLM API 密钥 |
| `POSTGRES_PASSWORD` | 是 | 数据库密码（Docker 环境） |
| `PGADMIN_PASSWORD` | 是 | pgAdmin 密码（开发环境） |
| `API_KEY` | 否 | API 认证密钥，生产环境建议设置 |
| `CORS_ORIGINS` | 否 | 允许的 CORS 来源，逗号分隔 |
| `REDIS_URL` | 否 | Redis 连接地址 |
| `WECHAT_WEBHOOK_URL` | 否 | 企业微信机器人 Webhook |
| `LLM_API_BASE` | 否 | LLM API 地址（默认 DeepSeek） |
| `LLM_MODEL` | 否 | LLM 模型名（默认 deepseek-chat） |
| `CRAWL_INTERVAL_MINUTES` | 否 | 爬取间隔（分钟，默认 60） |

完整配置项见 [.env.example](.env.example) 和 [app/config.py](app/config.py)。

---

## API 概览 / API Overview

| 路径 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 根路径，返回 API 信息和端点列表 |
| `/health` | GET | 基础健康检查 |
| `/health/detail` | GET | 详细健康检查（各依赖服务状态） |
| `/api/v1/projects` | GET | 项目列表（支持关键词搜索、分页） |
| `/api/v1/projects/{id}` | GET | 项目详情 |
| `/api/v1/crawl/start` | POST | 手动触发爬取 |
| `/api/v1/crawl/status` | GET | 爬取状态 |
| `/api/v1/dashboard/stats` | GET | Dashboard 统计 |
| `/api/v1/dashboard/intelligence` | GET | 情报分析 |
| `/api/v1/signals` | GET | 企业信号列表 |
| `/api/v1/signals/dashboard` | GET | 信号 Dashboard |
| `/api/v1/dashboard/sales` | GET | 销售辅助数据 |

完整 API 文档在 `/docs` 或 `/redoc`。

---

## 项目结构 / Project Structure

```
nik-project-hunter/
├── app/
│   ├── api/              # API 路由层
│   │   ├── auth.py       # API Key 认证中间件
│   │   ├── deps.py       # 依赖注入
│   │   └── v1/           # API v1 端点
│   ├── core/             # 核心模块
│   │   ├── ai_client.py  # LLM 客户端封装
│   │   └── logging_config.py
│   ├── models/           # SQLAlchemy 数据模型
│   ├── schemas/          # Pydantic 请求/响应模型
│   ├── services/         # 业务逻辑层
│   │   ├── analyzer.py   # AI 项目分析
│   │   ├── crawler.py    # 爬虫编排
│   │   ├── notifier.py   # 消息通知
│   │   ├── scorer.py     # 商机评分
│   │   └── semantic_filter.py  # 语义过滤
│   ├── spiders/          # 爬虫实现
│   │   ├── base/         # 爬虫基类
│   │   ├── manager.py    # 爬虫管理器
│   │   ├── china_zfcg.py # 中国政府采购网
│   │   ├── beijing_ggzy.py   # 北京公共资源
│   │   ├── tianjin_zfcg.py   # 天津政府采购
│   │   └── hebei_zfcg.py     # 河北政府采购
│   ├── pipeline/         # 数据管道
│   ├── signals/          # 企业信号 Intelligence（第五阶段）
│   │   ├── spiders/      # 信号爬虫（招聘、新闻、高管、政策）
│   │   └── services/     # 信号分析服务
│   ├── sales/            # 销售辅助模块
│   ├── scheduler.py      # 定时任务调度
│   ├── database.py       # 数据库连接
│   ├── config.py         # 配置管理
│   └── main.py           # FastAPI 入口
├── alembic/              # 数据库迁移
├── scripts/              # 运维脚本
├── docker-compose.yml    # Docker Compose 编排
├── Dockerfile            # 应用镜像
└── .env.example          # 环境变量模板
```

---

## 架构概览 / Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  爬虫引擎     │───▶│  数据管道      │───▶│  PostgreSQL  │
│  (Playwright)│    │  (清洗/过滤)   │    │  + pgvector  │
└─────────────┘    └──────────────┘    └──────┬──────┘
                                              │
┌─────────────┐    ┌──────────────┐           │
│  定时调度器   │───▶│  AI 分析/评分  │◀──────────┘
│  (APScheduler)│   │  (LLM)       │
└─────────────┘    └──────┬───────┘
                          │
                   ┌──────▼───────┐    ┌─────────────┐
                   │  通知服务     │───▶│  企业微信     │
                   │  销售辅助     │    │  Dashboard   │
                   └──────────────┘    └─────────────┘
```

---

## 开发路线图 / Roadmap

- ✅ **第一阶段** — 基础爬虫 + 项目存储 + API
- ✅ **第二阶段** — AI 分析 + 商机评分 + 语义过滤
- ✅ **第三阶段** — 定时调度 + 通知推送 + Dashboard
- ✅ **第四阶段** — 安全加固 + Docker 优化 + Alembic
- ✅ **第五阶段** — 企业信号 Intelligence + 销售辅助

---

## License

MIT