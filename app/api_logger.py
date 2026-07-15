"""
API日志中间件 - 记录请求头、请求体、响应体的全量信息。
按用户要求的3大类（请求头、请求体、响应体）详细记录。
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
    API日志中间件，拦截所有请求和响应，记录：
    - 请求Header：Authorization(脱敏)、Content-Type
    - 请求Body：chatId、stream、detail、responseChatItemId、variables、messages
    - 响应Body：id、model、usage、choices
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过非API路径（如/docs、/openapi.json）
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # ========== 一、请求Header记录 ==========
        auth_header = request.headers.get("Authorization", "")
        # 脱敏：只保留Bearer后key的后4位
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            masked_auth = f"Bearer ****{token[-4:]}" if len(token) >= 4 else "Bearer ****"
        else:
            masked_auth = auth_header[:20] + "..." if len(auth_header) > 20 else auth_header

        content_type = request.headers.get("Content-Type", "")

        logger.info(
            f"[{request_id}] [请求Header] Authorization={masked_auth} | Content-Type={content_type}"
        )

        # ========== 二、请求Body记录 ==========
        body_bytes = await request.body()
        body_json = {}
        try:
            body_json = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            pass

        # 对话标识类
        chat_id = body_json.get("chatId", "")
        response_chat_item_id = body_json.get("responseChatItemId", "")
        # 模式控制
        stream = body_json.get("stream", False)
        detail = body_json.get("detail", False)
        # 业务变量
        variables = body_json.get("variables", {})
        # 消息
        messages = body_json.get("messages", [])

        # variables子字段逐一记录
        var_id = variables.get("id", "")
        var_dup_uid = variables.get("dupUid", "")
        var_procure_method = variables.get("procureMethod", "")
        var_notice_type = variables.get("noticeType", "")
        var_content_len = len(variables.get("content", "") or "")
        var_spare1 = variables.get("spare1", "")
        var_spare2 = variables.get("spare2", "")
        var_spare3 = variables.get("spare3", "")

        logger.info(
            f"[{request_id}] [请求Body-对话标识] chatId={chat_id} | responseChatItemId={response_chat_item_id}"
        )
        logger.info(
            f"[{request_id}] [请求Body-模式控制] stream={stream} | detail={detail}"
        )
        logger.info(
            f"[{request_id}] [请求Body-业务变量] id={var_id} | dupUid={var_dup_uid} | "
            f"procureMethod={var_procure_method} | noticeType={var_notice_type} | "
            f"content长度={var_content_len} | spare1={var_spare1} | spare2={var_spare2} | spare3={var_spare3}"
        )
        logger.info(
            f"[{request_id}] [请求Body-消息] messages={json.dumps(messages, ensure_ascii=False)[:500]}"
        )

        # 调用下游
        response = await call_next(request)

        elapsed = time.time() - start_time

        # ========== 三、响应Body记录 ==========
        # 对于非流式响应，尝试读取响应体
        resp_body = b""
        if isinstance(response, StreamingResponse):
            # 流式响应不读取body（会消耗掉），只记录状态
            logger.info(
                f"[{request_id}] [响应] 流式响应 | status_code={response.status_code} | 耗时={elapsed:.3f}s"
            )
        else:
            # 非流式响应，读取body后重新构造response
            resp_body = getattr(response, "body", b"")
            if resp_body:
                try:
                    resp_json = json.loads(resp_body.decode("utf-8"))
                    resp_id = resp_json.get("id", "")
                    resp_model = resp_json.get("model", "")
                    resp_usage = resp_json.get("usage", {})
                    resp_choices = resp_json.get("choices", [])

                    logger.info(
                        f"[{request_id}] [响应Body-元数据] id={resp_id} | model={resp_model} | "
                        f"usage={json.dumps(resp_usage, ensure_ascii=False)}"
                    )
                    # choices内容可能很长，截取前500字符
                    choices_str = json.dumps(resp_choices, ensure_ascii=False)
                    choices_preview = choices_str[:500] + "..." if len(choices_str) > 500 else choices_str
                    logger.info(
                        f"[{request_id}] [响应Body-结果] choices={choices_preview}"
                    )
                except Exception:
                    logger.info(
                        f"[{request_id}] [响应Body] 原始长度={len(resp_body)} | 耗时={elapsed:.3f}s"
                    )

        logger.info(
            f"[{request_id}] [请求完成] status_code={response.status_code} | 耗时={elapsed:.3f}s"
        )

        return response
