"""
日志中间件模块 - 使用LangChain middleware hooks实现详细日志记录。
记录工作流每个节点的进入/退出、模型调用、耗时、输入输出等关键信息。
"""

import time
import json
import logging
from typing import Any, Dict, Optional

from app.config import setup_logging

logger = setup_logging()


class WorkflowLogger:
    """
    工作流日志记录器。
    在LangGraph节点函数中手动调用，记录每个节点的详细执行信息。
    """

    @staticmethod
    def log_node_enter(node_name: str, state: Dict[str, Any]) -> None:
        """记录节点进入"""
        notice_type = state.get("notice_type", "未知")
        dup_uid = state.get("dup_uid", "未知")
        content_length = len(state.get("content", "") or "")
        logger.info(
            f"[节点进入] {node_name} | "
            f"公告类型={notice_type} | 业务主键={dup_uid} | "
            f"正文长度={content_length}"
        )

    @staticmethod
    def log_node_exit(node_name: str, state: Dict[str, Any], elapsed: float) -> None:
        """记录节点退出"""
        result = state.get("parse_result", "")
        result_type = type(result).__name__ if result else "None"
        result_preview = ""
        if result:
            try:
                result_str = json.dumps(
                    result if isinstance(result, dict) else result.__dict__,
                    ensure_ascii=False,
                )
                result_preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
            except Exception:
                result_preview = str(result)[:200]

        logger.info(
            f"[节点退出] {node_name} | 耗时={elapsed:.3f}s | "
            f"结果类型={result_type} | 结果预览={result_preview}"
        )

    @staticmethod
    def log_model_call(
        model_name: str,
        system_prompt_preview: str,
        user_input_preview: str,
        temperature: float,
    ) -> None:
        """记录模型调用"""
        logger.debug(
            f"[模型调用] 模型={model_name} | temperature={temperature} | "
            f"系统提示词预览={system_prompt_preview[:100]}... | "
            f"用户输入预览={user_input_preview[:100]}..."
        )

    @staticmethod
    def log_model_response(model_name: str, response_preview: str, elapsed: float) -> None:
        """记录模型响应"""
        logger.debug(
            f"[模型响应] 模型={model_name} | 耗时={elapsed:.3f}s | "
            f"响应预览={response_preview[:200]}..."
        )

    @staticmethod
    def log_routing(notice_type: str, target_node: str) -> None:
        """记录条件路由"""
        logger.info(f"[条件路由] 公告类型={notice_type} → 目标节点={target_node}")

    @staticmethod
    def log_error(node_name: str, error: Exception) -> None:
        """记录错误"""
        logger.error(
            f"[节点错误] {node_name} | 错误类型={type(error).__name__} | "
            f"错误信息={str(error)}",
            exc_info=True,
        )

    @staticmethod
    def log_parse_result(raw_text: str, parsed_model: str) -> None:
        """记录解析结果（原始文本 → 结构化模型）"""
        logger.debug(
            f"[解析结果] 原始文本长度={len(raw_text)} | "
            f"结构化模型={parsed_model}"
        )


def timed_node(node_name: str):
    """
    节点执行计时装饰器。
    自动记录节点进入/退出时间和耗时。
    """
    def decorator(func):
        def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            WorkflowLogger.log_node_enter(node_name, state)
            start = time.time()
            try:
                result = func(state)
                elapsed = time.time() - start
                # result是partial state dict，合并到state后记录
                merged = {**state, **result} if isinstance(result, dict) else state
                WorkflowLogger.log_node_exit(node_name, merged, elapsed)
                return result
            except Exception as e:
                elapsed = time.time() - start
                WorkflowLogger.log_error(node_name, e)
                raise
        return wrapper
    return decorator
