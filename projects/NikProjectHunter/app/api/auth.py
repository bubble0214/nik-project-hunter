"""
Nik Project Hunter — API Key 认证中间件

职责：
1. 保护所有 /api/v1/* 端点，要求 X-API-Key 头
2. 健康检查端点 /health 无需认证
3. 根路径 / 无需认证
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings

settings = get_settings()

# 不需要认证的路径前缀
PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    API Key 认证中间件

    请求头 X-API-Key 必须与配置的 API_KEY 匹配。
    如果未配置 API_KEY，则跳过认证（开发模式）。
    """

    async def dispatch(self, request: Request, call_next):
        # 未配置 API_KEY 时跳过认证
        if not settings.API_KEY:
            return await call_next(request)

        # 公开路径跳过认证
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith("/health"):
            return await call_next(request)

        # OPTIONS 请求（CORS 预检）跳过认证
        if request.method == "OPTIONS":
            return await call_next(request)

        # 检查 API Key
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if api_key != settings.API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key. Provide X-API-Key header or api_key query parameter."},
            )

        return await call_next(request)