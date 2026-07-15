"""
API日志中间件 - 记录请求头、请求体、响应体到日志文件。
数据库写入由server.py路由函数直接完成（因为中间件无法可靠读取FastAPI response_model序列化后的body）。
"""

import time
import json
import uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from app.config import setup_logging

logger = setup_logging()


class ApiLoggingMiddleware(BaseHTTPMiddleware):
    """
    API日志中间件，拦截请求和响应，记录到日志文件。
    数据库写入由路由函数中调用 save_log_to_db() 完成。
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not path.startswith("/api/v1/chat"):
            return await call_next(request)

        request_id = str(uuid.uuid4())[:12]
        start_time = time.time()

        # 请求Header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            masked_auth = f"Bearer ****{token[-4:]}" if len(token) >= 4 else "Bearer ****"
        else:
            masked_auth = auth_header[:20] + "..." if len(auth_header) > 20 else auth_header

        content_type = request.headers.get("Content-Type", "")
        logger.info(f"[{request_id}] [请求Header] Authorization={masked_auth} | Content-Type={content_type}")

        # 请求Body
        body_bytes = await request.body()
        body_json = {}
        try:
            body_json = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            pass

        chat_id = body_json.get("chatId", "")
        var_notice_type = body_json.get("variables", {}).get("noticeType", "")
        var_dup_uid = body_json.get("variables", {}).get("dupUid", "")
        var_content_len = len(body_json.get("variables", {}).get("content", "") or "")

        logger.info(
            f"[{request_id}] [请求Body] chatId={chat_id} | noticeType={var_notice_type} | "
            f"dupUid={var_dup_uid} | content长度={var_content_len}"
        )

        # 调用下游
        response = await call_next(request)
        elapsed = time.time() - start_time

        logger.info(
            f"[{request_id}] [响应] status={response.status_code} | 耗时={elapsed:.3f}s"
        )

        return response
