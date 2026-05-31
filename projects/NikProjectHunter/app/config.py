"""
Nik Project Hunter — 集中配置管理（第三阶段）

设计思路：
- 所有配置集中管理，不散落在各模块
- 使用 pydantic-settings 从环境变量自动加载
- 支持 .env 文件（通过 python-dotenv）
- 所有配置项有默认值，零配置也能启动
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # 应用基础配置
    # ------------------------------------------------------------------
    APP_NAME: str = "Nik Project Hunter"
    APP_VERSION: str = "0.3.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ------------------------------------------------------------------
    # 数据库
    # ------------------------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://nik:nik_secret_2026@localhost:5432/nik_project_hunter"

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"

    # ------------------------------------------------------------------
    # LLM API（默认 DeepSeek，可替换为 OpenAI / Claude）
    # ------------------------------------------------------------------
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"

    # ------------------------------------------------------------------
    # 爬虫配置
    # ------------------------------------------------------------------
    CRAWL_INTERVAL_MINUTES: int = 1440  # 每天爬取一次（6:00 CST 触发）
    CRAWL_CRON_EXPR: str = ""          # 可选 cron 表达式，优先级高于间隔

    # ------------------------------------------------------------------
    # 通知 Webhook（企业微信机器人）
    # ------------------------------------------------------------------
    WECHAT_WEBHOOK_URL: str = ""       # 企业微信机器人 Webhook URL

    # ------------------------------------------------------------------
    # 日志配置
    # ------------------------------------------------------------------
    LOG_DIR: str = "logs"              # 日志文件目录

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # 允许 .env 中有额外字段（如 POSTGRES_DB 等 Docker 变量）


@lru_cache()
def get_settings() -> Settings:
    """获取全局单例配置"""
    return Settings()