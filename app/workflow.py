"""
工作流核心模块 - 使用LangGraph一比一还原JSON工作流。

流程:
  工作流开始 → 判断公告类型 → 条件路由
    ├─ 招标公告       → 解析招标公告正文(DeepSeek)
    ├─ 变更公告       → 解析变更公告正文(DeepSeek)
    ├─ 中标候选人公示 → 解析中标候选人公示正文(DeepSeek)
    ├─ 结果公告       → 解析结果公告正文(DeepSeek)
    └─ 其他           → 指定回复(不支持)
"""

import json
import time
import re
from typing import Dict, Any, Annotated, TypedDict, Optional
from typing_extensions import Literal

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import (
    MODEL_NAME, MODEL_BASE_URL, MODEL_API_KEY,
    MODEL_TEMPERATURE, MODEL_MAX_TOKEN,
    NOTICE_TYPE_ZHAOBIAO, NOTICE_TYPE_BIANGENG,
    NOTICE_TYPE_ZHONGBIAO_HOUXUANREN, NOTICE_TYPE_JIEGUO,
    UNSUPPORTED_TYPE_MESSAGE,
    setup_logging,
)
from app.prompts import (
    USER_CHAT_INPUT_TEMPLATE,
    ZHAOBIAO_SYSTEM_PROMPT,
    BIANGENG_SYSTEM_PROMPT,
    ZHONGBIAO_HOUXUANREN_SYSTEM_PROMPT,
    JIEGUO_SYSTEM_PROMPT,
)
from app.schemas import (
    WorkflowInput,
    ZhaobiaoNotice,
    BiangengNotice,
    ZhongbiaoHouxuanrenNotice,
    JieguoNotice,
)
from app.middleware import WorkflowLogger, timed_node

logger = setup_logging()


# ============================================================
# 工作流状态定义
# ============================================================

class WorkflowState(TypedDict, total=False):
    """工作流状态，在各节点间传递。"""
    id: str
    dup_uid: str
    procure_method: str
    notice_type: str
    content: str
    spare1: str
    spare2: str
    spare3: str
    parse_result: Optional[Any]
    error_message: Optional[str]
    model_usage: Optional[Dict[str, Any]]


# ============================================================
# 模型初始化 - 统一使用DeepSeek模型
# ============================================================

def _create_model() -> ChatOpenAI:
    """创建统一的DeepSeek模型实例"""
    return ChatOpenAI(
        model=MODEL_NAME,
        base_url=MODEL_BASE_URL,
        api_key=MODEL_API_KEY,
        temperature=MODEL_TEMPERATURE,
        max_tokens=MODEL_MAX_TOKEN,
        timeout=600,
    )


# 懒初始化模型实例
_model: Optional[ChatOpenAI] = None


def get_model() -> ChatOpenAI:
    global _model
    if _model is None:
        logger.info(f"[模型初始化] {MODEL_NAME}")
        _model = _create_model()
    return _model


# ============================================================
# 通用解析函数
# ============================================================

def _extract_model_usage(response: Any) -> Dict[str, Any]:
    """
    从LangChain模型响应(AIMessage)中提取真实的model和usage信息。
    """
    result = {
        "model": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    response_metadata = getattr(response, "response_metadata", {}) or {}
    model_name = response_metadata.get("model_name") or getattr(response, "model", "") or ""
    result["model"] = model_name

    # 优先从 usage_metadata 读取（langchain标准）
    usage_metadata = getattr(response, "usage_metadata", None)
    if usage_metadata and isinstance(usage_metadata, dict):
        result["prompt_tokens"] = usage_metadata.get("input_tokens", 0) or 0
        result["completion_tokens"] = usage_metadata.get("output_tokens", 0) or 0
        result["total_tokens"] = usage_metadata.get("total_tokens", 0) or 0
        return result

    # 兼容从 response_metadata.token_usage 读取
    token_usage = response_metadata.get("token_usage", {}) or response_metadata.get("usage", {}) or {}
    if token_usage:
        result["prompt_tokens"] = token_usage.get("prompt_tokens", 0) or 0
        result["completion_tokens"] = token_usage.get("completion_tokens", 0) or 0
        result["total_tokens"] = token_usage.get("total_tokens", 0) or 0
        return result

    return result


def _call_model_and_parse(
    model: ChatOpenAI,
    system_prompt: str,
    user_input: str,
    pydantic_model_class: type,
    node_name: str,
) -> Any:
    """
    调用LLM模型并解析结构化输出。
    1. 使用systemPrompt + userChatInput模板构建消息
    2. 调用模型获取响应
    3. 从响应中提取JSON代码块
    4. 使用Pydantic模型验证并返回
    """
    WorkflowLogger.log_model_call(
        model_name=model.model_name,
        system_prompt_preview=system_prompt,
        user_input_preview=user_input,
        temperature=model.temperature,
    )

    start = time.time()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input),
    ]
    response = model.invoke(messages)
    elapsed = time.time() - start

    raw_text = response.content
    # 从LLM原始响应中提取model和usage信息
    resp_model_usage = _extract_model_usage(response)

    WorkflowLogger.log_model_response(
        model_name=model.model_name,
        response_preview=raw_text,
        elapsed=elapsed,
    )

    # 从响应中提取JSON代码块
    parsed_dict = _extract_json_from_response(raw_text)

    if parsed_dict is None:
        logger.warning(f"[JSON提取失败] {node_name} | 原始响应预览={raw_text[:300]}")
        return pydantic_model_class(), resp_model_usage

    try:
        result = pydantic_model_class(**parsed_dict)
        WorkflowLogger.log_parse_result(raw_text, pydantic_model_class.__name__)
        return result, resp_model_usage
    except Exception as e:
        logger.warning(f"[Pydantic验证失败] {node_name} | 错误={e} | 数据={json.dumps(parsed_dict, ensure_ascii=False)[:300]}")
        return pydantic_model_class(**parsed_dict) if parsed_dict else pydantic_model_class(), resp_model_usage


def _extract_json_from_response(text: str) -> Optional[dict]:
    """从LLM响应文本中提取JSON代码块"""
    # 尝试匹配 ```json ... ``` 代码块
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # 尝试直接解析整个文本
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 尝试找到第一个 { 和最后一个 } 之间的内容
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    return None


def _build_user_input(state: Dict[str, Any]) -> str:
    """一比一还原JSON中的userChatInput模板，将变量填充到模板中"""
    return USER_CHAT_INPUT_TEMPLATE.format(
        id=state.get("id", ""),
        dupUid=state.get("dup_uid", ""),
        procureMethod=state.get("procure_method", ""),
        noticeType=state.get("notice_type", ""),
        content=state.get("content", ""),
        spare1=state.get("spare1", ""),
        spare2=state.get("spare2", ""),
        spare3=state.get("spare3", ""),
    )


# ============================================================
# 工作流节点函数 - 一比一还原JSON中的6个节点
# ============================================================

@timed_node("判断公告类型")
def route_notice_type(state: WorkflowState) -> Dict[str, Any]:
    """
    一比一还原JSON中的 ifElseNode "判断公告类型"。
    根据noticeType字段决定路由方向。
    此节点不做实际处理，仅用于日志记录路由决策。
    """
    notice_type = state.get("notice_type", "")
    logger.info(f"[判断公告类型] noticeType={notice_type}")
    return {}


@timed_node("解析招标公告正文")
def parse_zhaobiao(state: WorkflowState) -> Dict[str, Any]:
    """解析招标公告正文，统一使用DeepSeek模型"""
    user_input = _build_user_input(state)
    result, model_usage = _call_model_and_parse(
        model=get_model(),
        system_prompt=ZHAOBIAO_SYSTEM_PROMPT,
        user_input=user_input,
        pydantic_model_class=ZhaobiaoNotice,
        node_name="解析招标公告正文",
    )
    return {"parse_result": result, "model_usage": model_usage}


@timed_node("解析变更公告正文")
def parse_biangeng(state: WorkflowState) -> Dict[str, Any]:
    """解析变更公告正文，统一使用DeepSeek模型"""
    user_input = _build_user_input(state)
    result, model_usage = _call_model_and_parse(
        model=get_model(),
        system_prompt=BIANGENG_SYSTEM_PROMPT,
        user_input=user_input,
        pydantic_model_class=BiangengNotice,
        node_name="解析变更公告正文",
    )
    return {"parse_result": result, "model_usage": model_usage}


@timed_node("解析中标候选人公示正文")
def parse_zhongbiao_houxuanren(state: WorkflowState) -> Dict[str, Any]:
    """解析中标候选人公示正文，统一使用DeepSeek模型"""
    user_input = _build_user_input(state)
    result, model_usage = _call_model_and_parse(
        model=get_model(),
        system_prompt=ZHONGBIAO_HOUXUANREN_SYSTEM_PROMPT,
        user_input=user_input,
        pydantic_model_class=ZhongbiaoHouxuanrenNotice,
        node_name="解析中标候选人公示正文",
    )
    return {"parse_result": result, "model_usage": model_usage}


@timed_node("解析结果公告正文")
def parse_jieguo(state: WorkflowState) -> Dict[str, Any]:
    """解析结果公告正文，统一使用DeepSeek模型"""
    user_input = _build_user_input(state)
    result, model_usage = _call_model_and_parse(
        model=get_model(),
        system_prompt=JIEGUO_SYSTEM_PROMPT,
        user_input=user_input,
        pydantic_model_class=JieguoNotice,
        node_name="解析结果公告正文",
    )
    return {"parse_result": result, "model_usage": model_usage}


@timed_node("指定回复")
def unsupported_type_reply(state: WorkflowState) -> Dict[str, Any]:
    """
    一比一还原JSON中 zda3vj7BvdcFPeAI 节点 "指定回复"。
    输出: "不支持解析的公告类型！当前支持的公告类型为：招标公告、变更公告、中标候选人公示和结果公告。"
    """
    return {"error_message": UNSUPPORTED_TYPE_MESSAGE}


# ============================================================
# 条件路由函数 - 一比一还原JSON中 ifElseNode 的4个条件分支
# ============================================================

def route_by_notice_type(state: WorkflowState) -> str:
    """
    一比一还原JSON中 sIT99QNwT9m3SiQM 节点的条件判断：
    IF noticeType == "招标公告"     → parse_zhaobiao
    ELSE IF noticeType == "变更公告" → parse_biangeng
    ELSE IF noticeType == "中标候选人公示" → parse_zhongbiao_houxuanren
    ELSE IF noticeType == "结果公告" → parse_jieguo
    ELSE                            → unsupported_type_reply
    """
    notice_type = state.get("notice_type", "")

    route_map = {
        NOTICE_TYPE_ZHAOBIAO: "parse_zhaobiao",
        NOTICE_TYPE_BIANGENG: "parse_biangeng",
        NOTICE_TYPE_ZHONGBIAO_HOUXUANREN: "parse_zhongbiao_houxuanren",
        NOTICE_TYPE_JIEGUO: "parse_jieguo",
    }

    target = route_map.get(notice_type, "unsupported_type_reply")
    WorkflowLogger.log_routing(notice_type, target)
    return target


# ============================================================
# 构建LangGraph工作流 - 一比一还原JSON中的edges
# ============================================================

def build_workflow() -> StateGraph:
    """
    构建LangGraph工作流图。

    一比一还原JSON中的edges:
    - 448745(工作流开始) → sIT99QNwT9m3SiQM(判断公告类型)
    - sIT99QNwT9m3SiQM → hpBjDyzAQKiDHAwx(解析招标公告正文)       [IF]
    - sIT99QNwT9m3SiQM → rAOYghkLtueUuZ15(解析变更公告正文)       [ELSE IF 1]
    - sIT99QNwT9m3SiQM → ksn44PyEpRZRitcf(解析中标候选人公示正文)  [ELSE IF 2]
    - sIT99QNwT9m3SiQM → iO6Xy8ZZgVVBI6H3(解析结果公告正文)       [ELSE IF 3]
    - sIT99QNwT9m3SiQM → zda3vj7BvdcFPeAI(指定回复)              [ELSE]
    """
    graph = StateGraph(WorkflowState)

    # 添加节点
    graph.add_node("route_notice_type", route_notice_type)
    graph.add_node("parse_zhaobiao", parse_zhaobiao)
    graph.add_node("parse_biangeng", parse_biangeng)
    graph.add_node("parse_zhongbiao_houxuanren", parse_zhongbiao_houxuanren)
    graph.add_node("parse_jieguo", parse_jieguo)
    graph.add_node("unsupported_type_reply", unsupported_type_reply)

    # 设置入口 - 一比一还原: 448745(工作流开始) → 判断公告类型
    graph.set_entry_point("route_notice_type")

    # 添加条件边 - 一比一还原: 判断公告类型 → 条件路由
    graph.add_conditional_edges(
        "route_notice_type",
        route_by_notice_type,
        {
            "parse_zhaobiao": "parse_zhaobiao",
            "parse_biangeng": "parse_biangeng",
            "parse_zhongbiao_houxuanren": "parse_zhongbiao_houxuanren",
            "parse_jieguo": "parse_jieguo",
            "unsupported_type_reply": "unsupported_type_reply",
        },
    )

    # 所有解析节点和指定回复节点 → 结束
    graph.add_edge("parse_zhaobiao", END)
    graph.add_edge("parse_biangeng", END)
    graph.add_edge("parse_zhongbiao_houxuanren", END)
    graph.add_edge("parse_jieguo", END)
    graph.add_edge("unsupported_type_reply", END)

    return graph


def compile_workflow():
    """编译工作流，返回可执行的CompiledGraph"""
    graph = build_workflow()
    compiled = graph.compile()
    logger.info("[工作流编译] 工作流已编译完成")
    return compiled


# ============================================================
# 便捷调用函数
# ============================================================

def run_workflow(input_data: WorkflowInput) -> Dict[str, Any]:
    """
    运行工作流的便捷函数。

    Args:
        input_data: 工作流输入参数（WorkflowInput模型实例）

    Returns:
        包含解析结果的字典
    """
    compiled = compile_workflow()

    # 将WorkflowInput转换为WorkflowState
    state: WorkflowState = {
        "id": input_data.id,
        "dup_uid": input_data.dupUid,
        "procure_method": input_data.procureMethod,
        "notice_type": input_data.noticeType,
        "content": input_data.content,
        "spare1": input_data.spare1,
        "spare2": input_data.spare2,
        "spare3": input_data.spare3,
        "parse_result": None,
        "error_message": None,
        "model_usage": None,
    }

    logger.info(
        f"[工作流启动] 公告类型={input_data.noticeType} | "
        f"业务主键={input_data.dupUid} | 正文长度={len(input_data.content)}"
    )

    start_time = time.time()
    result = compiled.invoke(state)
    elapsed = time.time() - start_time

    logger.info(
        f"[工作流完成] 耗时={elapsed:.3f}s | "
        f"是否有错误={result.get('error_message') is not None}"
    )

    return result
