# =============================================================================
# Nik Project Hunter — Docker 镜像
# =============================================================================
# 基础镜像：Python 3.11 slim（保持小体积）
# 包含：FastAPI 应用 + Playwright 浏览器
# 说明：Playwright 需要安装 Chromium 浏览器，用于爬取动态页面
# =============================================================================

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ---------------------------------------------------------------------------
# 系统依赖
# Playwright 需要 Chromium 浏览器及其依赖
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright 系统依赖
    libnss3 \
    libnspr4 \
    libatk1.0-0t64 \
    libatk-bridge2.0-0t64 \
    libcups2t64 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2t64 \
    libxfixes3 \
    # 通用工具
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Python 依赖
# ---------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install -r requirements.txt

# 安装 Playwright Chromium 浏览器
RUN playwright install chromium

# ---------------------------------------------------------------------------
# 应用代码
# ---------------------------------------------------------------------------
COPY . .

# ---------------------------------------------------------------------------
# 启动
# 开发环境使用 --reload（已通过 docker-compose command 覆盖）
# 生产环境移除 --reload
# ---------------------------------------------------------------------------
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]