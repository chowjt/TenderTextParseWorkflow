"""
FastAPI服务主体 - 暴露POST接口，接收入参并返回出参。

接口路径: POST /api/v1/chat/completions
入参: 对标FastGPT工作流调用格式
出参: 对标OpenAI Chat Completions格式
"""

import time
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.auth import verify_authorization
from app.api_logger import ApiLoggingMiddleware
from app.log_api import router as log_router
from app.db import insert_log
from app.config import setup_logging, SUPPORTED_NOTICE_TYPES, UNSUPPORTED_TYPE_MESSAGE
from app.schemas import WorkflowInput
from app.workflow import run_workflow

logger = setup_logging()

# ============================================================
# FastAPI应用实例
# ============================================================

app = FastAPI(
    title="烟草招采公告文本解析工作流",
    description="解析招标公告、变更公告、中标候选人公示、结果公告，返回结构化JSON",
    version="1.0.0",
)

# 注册日志中间件（仅记录日志文件）
app.add_middleware(ApiLoggingMiddleware)

# 注册日志查询API路由
app.include_router(log_router)


# ============================================================
# 入参模型 - 一比一还原用户请求示例
# ============================================================

class VariableInput(BaseModel):
    """业务变量"""
    id: str = Field(default="", description="业务单据ID")
    dupUid: str = Field(default="", description="业务唯一去重ID")
    procureMethod: str = Field(default="", description="采购方式")
    noticeType: str = Field(description="公告类型")
    content: str = Field(description="原始招标公告全文")
    spare1: str = Field(default="", description="预留扩展字段1")
    spare2: str = Field(default="", description="预留扩展字段2")
    spare3: str = Field(default="", description="预留扩展字段3")


class ChatMessage(BaseModel):
    """对话消息"""
    role: str = Field(description="角色: user/assistant")
    content: str = Field(default="", description="消息内容")


class ChatRequest(BaseModel):
    """聊天请求 - 对标FastGPT工作流调用格式"""
    chatId: str = Field(default="", description="对话ID，更换相当于重新创建对话")
    stream: bool = Field(default=False, description="false非流式返回，true流式返回")
    detail: bool = Field(default=False, description="扩展详情开关")
    responseChatItemId: str = Field(default="", description="单轮对话消息唯一ID")
    variables: VariableInput = Field(description="业务核心变量")
    messages: List[ChatMessage] = Field(default_factory=list, description="对话消息列表")


# ============================================================
# 出参模型 - 一比一还原用户响应示例
# ============================================================

class UsageInfo(BaseModel):
    """Token消耗统计"""
    prompt_tokens: int = Field(default=0, description="输入token")
    completion_tokens: int = Field(default=0, description="输出token")
    total_tokens: int = Field(default=0, description="总token")


class MessageOutput(BaseModel):
    """消息输出"""
    role: str = Field(default="assistant", description="角色")
    content: str = Field(default="", description="消息内容")


class ChoiceItem(BaseModel):
    """选择项"""
    message: MessageOutput = Field(description="消息")
    finish_reason: str = Field(default="stop", description="结束原因")
    index: int = Field(default=0, description="索引")


class ChatResponse(BaseModel):
    """聊天响应 - 对标OpenAI Chat Completions格式"""
    id: str = Field(description="响应唯一ID")
    model: str = Field(default="", description="模型标识")
    usage: UsageInfo = Field(default_factory=UsageInfo, description="Token消耗")
    choices: List[ChoiceItem] = Field(description="结果列表")


# ============================================================
# 数据库日志写入辅助函数
# ============================================================

def _save_log_to_db(
    request: Request,
    chat_request: ChatRequest,
    response: ChatResponse,
    elapsed_ms: int,
):
    """将请求和响应的完整数据写入SQLite数据库"""
    # 请求Header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        masked_auth = f"Bearer ****{token[-4:]}" if len(token) >= 4 else "Bearer ****"
    else:
        masked_auth = auth_header[:20] + "..." if len(auth_header) > 20 else auth_header

    content_type = request.headers.get("Content-Type", "")

    # 请求Body
    variables = chat_request.variables
    messages_list = [{"role": m.role, "content": m.content} for m in chat_request.messages]

    # 响应Body - 直接从response对象获取，确保choices完整
    choices_list = []
    for c in response.choices:
        choices_list.append({
            "message": {"role": c.message.role, "content": c.message.content},
            "finish_reason": c.finish_reason,
            "index": c.index,
        })

    try:
        insert_log({
            "request_id": response.id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_ms": elapsed_ms,
            "auth_masked": masked_auth,
            "content_type": content_type,
            "chat_id": chat_request.chatId,
            "response_chat_item_id": chat_request.responseChatItemId,
            "stream": 1 if chat_request.stream else 0,
            "detail": 1 if chat_request.detail else 0,
            "var_id": variables.id,
            "var_notice_type": variables.noticeType,
            "var_content": variables.content or "",
            "var_spare1": variables.spare1,
            "var_spare2": variables.spare2,
            "var_spare3": variables.spare3,
            "messages": json.dumps(messages_list, ensure_ascii=False),
            "resp_id": response.id,
            "resp_model": response.model,
            "resp_prompt_tokens": response.usage.prompt_tokens,
            "resp_completion_tokens": response.usage.completion_tokens,
            "resp_total_tokens": response.usage.total_tokens,
            "resp_choices": json.dumps(choices_list, ensure_ascii=False),
            "status_code": 200,
            "error_message": "",
        })
    except Exception as e:
        logger.error(f"[{response.id}] 日志写入数据库失败: {e}")


# ============================================================
# POST接口
# ============================================================

@app.post("/api/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    chat_request: ChatRequest,
    request: Request,
    token: str = Depends(verify_authorization),
):
    """
    烟草招采公告文本解析接口。

    接收公告文本和类型，返回结构化解析结果。
    """
    request_id = chat_request.chatId or str(uuid.uuid4())[:12]
    start_time = time.time()

    # 校验公告类型
    notice_type = chat_request.variables.noticeType
    if notice_type not in SUPPORTED_NOTICE_TYPES:
        logger.warning(f"[{request_id}] 不支持的公告类型: {notice_type}")
        response = ChatResponse(
            id=request_id,
            model="",
            usage=UsageInfo(),
            choices=[
                ChoiceItem(
                    message=MessageOutput(role="assistant", content=UNSUPPORTED_TYPE_MESSAGE),
                    finish_reason="stop",
                    index=0,
                )
            ],
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        _save_log_to_db(request, chat_request, response, elapsed_ms)
        return response

    # 构造工作流输入
    workflow_input = WorkflowInput(
        id=chat_request.variables.id,
        dupUid=chat_request.variables.dupUid,
        procureMethod=chat_request.variables.procureMethod,
        noticeType=chat_request.variables.noticeType,
        content=chat_request.variables.content,
        spare1=chat_request.variables.spare1,
        spare2=chat_request.variables.spare2,
        spare3=chat_request.variables.spare3,
    )

    # 运行工作流
    try:
        result = run_workflow(workflow_input)
    except Exception as e:
        logger.error(f"[{request_id}] 工作流执行异常: {e}", exc_info=True)
        response = ChatResponse(
            id=request_id,
            model="",
            usage=UsageInfo(),
            choices=[
                ChoiceItem(
                    message=MessageOutput(role="assistant", content=f"工作流执行异常: {str(e)}"),
                    finish_reason="stop",
                    index=0,
                )
            ],
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        _save_log_to_db(request, chat_request, response, elapsed_ms)
        return response

    elapsed = time.time() - start_time

    # 构造响应
    parse_result = result.get("parse_result")
    error_message = result.get("error_message")
    model_usage = result.get("model_usage") or {}

    # 从DeepSeek响应中提取真实的model和usage
    resp_model = model_usage.get("model", "")
    resp_prompt_tokens = model_usage.get("prompt_tokens", 0)
    resp_completion_tokens = model_usage.get("completion_tokens", 0)
    resp_total_tokens = model_usage.get("total_tokens", 0)

    if error_message:
        content_text = error_message
    elif parse_result:
        if hasattr(parse_result, "model_dump"):
            result_dict = parse_result.model_dump()
        elif hasattr(parse_result, "dict"):
            result_dict = parse_result.dict()
        else:
            result_dict = str(parse_result)
        content_text = "```json\n" + json.dumps(result_dict, ensure_ascii=False, indent=2) + "\n```"
    else:
        content_text = ""

    response = ChatResponse(
        id=request_id,
        model=resp_model,
        usage=UsageInfo(
            prompt_tokens=resp_prompt_tokens,
            completion_tokens=resp_completion_tokens,
            total_tokens=resp_total_tokens,
        ),
        choices=[
            ChoiceItem(
                message=MessageOutput(role="assistant", content=content_text),
                finish_reason="stop",
                index=0,
            )
        ],
    )

    logger.info(
        f"[{request_id}] [接口响应] 耗时={elapsed:.3f}s | "
        f"公告类型={notice_type} | 是否有错误={error_message is not None}"
    )

    # 写入数据库（包含完整choices内容）
    elapsed_ms = int(elapsed * 1000)
    _save_log_to_db(request, chat_request, response, elapsed_ms)

    return response


@app.get("/api/v1/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok"}


@app.get("/api/v1/logs", response_class=HTMLResponse)
async def logs_page():
    """日志前端展示页面"""
    html_path = Path(__file__).resolve().parent / "templates" / "logs.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
