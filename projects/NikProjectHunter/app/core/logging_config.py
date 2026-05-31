"""
Nik Project Hunter — 日志系统

职责：
1. 配置 Loguru 日志，分文件输出
2. 支持按模块分离日志文件：
   - logs/crawler.log
   - logs/analyzer.log
   - logs/notifier.log
   - logs/scheduler.log
   - logs/app.log (全量)
3. 自动创建日志目录
"""

import os
import sys
from loguru import logger

from app.config import get_settings

settings = get_settings()


def setup_logging():
    """
    配置 Loguru 日志系统

    日志文件：
    - logs/crawler.log: 爬虫模块
    - logs/analyzer.log: AI 分析模块
    - logs/notifier.log: 通知模块
    - logs/scheduler.log: 定时任务模块
    - logs/app.log: 全量日志

    日志格式：
    - 控制台: 彩色输出，适合开发调试
    - 文件: 结构化，适合日志分析
    """
    log_dir = settings.LOG_DIR

    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)

    # 移除默认的日志处理器
    logger.remove()

    # =============================================================================
    # 控制台日志（彩色输出）
    # =============================================================================
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=False,
    )

    # =============================================================================
    # 全量日志文件（保留 7 天，每天轮转）
    # =============================================================================
    logger.add(
        os.path.join(log_dir, "app.log"),
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        ),
        level="INFO",
        rotation="1 day",
        retention="7 days",
        compression="gz",
        encoding="utf-8",
        backtrace=True,
    )

    # =============================================================================
    # 模块专用日志文件
    # =============================================================================
    _add_module_logger("crawler", "crawler.log")
    _add_module_logger("analyzer", "analyzer.log")
    _add_module_logger("notifier", "notifier.log")
    _add_module_logger("scheduler", "scheduler.log")

    # =============================================================================
    # 错误日志（仅 ERROR 及以上，用于告警）
    # =============================================================================
    logger.add(
        os.path.join(log_dir, "error.log"),
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        ),
        level="ERROR",
        rotation="1 week",
        retention="30 days",
        compression="gz",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    logger.info(f"日志系统已初始化，日志目录: {os.path.abspath(log_dir)}")


def _add_module_logger(module_name: str, filename: str):
    """
    添加模块级日志文件

    过滤规则：只记录包含 [ModuleName] 标签的日志
    """
    log_dir = settings.LOG_DIR
    capitalized = module_name.capitalize()

    def module_filter(record):
        return f"[{capitalized}]" in record["message"]

    logger.add(
        os.path.join(log_dir, filename),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="INFO",
        filter=module_filter,
        rotation="1 day",
        retention="7 days",
        compression="gz",
        encoding="utf-8",
    )