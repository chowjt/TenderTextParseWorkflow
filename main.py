"""
主入口 - 烟草招采公告文本解析工作流

使用方式:
1. 在项目根目录的 .env 文件中配置模型信息和API密钥

2. 启动服务:
   python main.py

3. 作为模块调用:
   from main import parse_notice
   result = parse_notice(input_data)

4. API接口:
   POST /api/v1/chat/completions
"""

import os
import json
from typing import Dict, Any

from dotenv import load_dotenv
from pathlib import Path

# 加载.env
load_dotenv(Path(__file__).resolve().parent / ".env")

from app.config import setup_logging, SUPPORTED_NOTICE_TYPES
from app.schemas import WorkflowInput
from app.workflow import run_workflow

logger = setup_logging()


def parse_notice(input_data: WorkflowInput) -> Dict[str, Any]:
    """
    解析招采公告的便捷入口函数。

    Args:
        input_data: WorkflowInput实例，包含公告类型、正文等信息

    Returns:
        解析结果字典，包含 parse_result 和 error_message
    """
    if input_data.noticeType not in SUPPORTED_NOTICE_TYPES:
        logger.warning(f"不支持的公告类型: {input_data.noticeType}")
        return {
            "parse_result": None,
            "error_message": f"不支持解析的公告类型！当前支持的公告类型为：{'、'.join(SUPPORTED_NOTICE_TYPES)}。",
        }

    return run_workflow(input_data)


def start_server():
    """启动FastAPI服务"""
    import uvicorn
    port = int(os.getenv("SERVER_PORT", "8000"))
    logger.info(f"[服务启动] 端口={port}")
    uvicorn.run(
        "app.server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    start_server()
