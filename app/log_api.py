"""
日志查询API - 提供分页查询、详情查询、Token统计接口，供前端页面调用。
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from typing import Optional, Literal

from app.db import (
    query_logs,
    query_log_detail,
    query_stats_token_usage,
    query_stats_token_usage_by_type,
    query_stats_token_usage_by_month,
    query_stats_token_usage_by_year,
    query_stats_token_usage_by_day,
    query_stats_token_usage_by_hour,
)

router = APIRouter(prefix="/api/v1/logs", tags=["日志查询"])


def _range_time(range_type: Literal["1d", "7d", "30d", "month", "year", "all"]):
    """根据范围类型计算起始和结束时间，格式：YYYY-MM-DD HH:MM:SS"""
    now = datetime.now()
    end_time = now.strftime("%Y-%m-%d %H:%M:%S")

    if range_type == "1d":
        start_time = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    elif range_type == "7d":
        start_time = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    elif range_type == "30d":
        start_time = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    elif range_type == "month":
        # 本年度1月1日 至 现在
        start_time = now.replace(month=1, day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
    elif range_type == "year":
        # 全部历史
        start_time = "1970-01-01 00:00:00"
    elif range_type == "all":
        # 全部历史
        start_time = "1970-01-01 00:00:00"
    else:
        # 默认7天
        start_time = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    return start_time, end_time


@router.get("/list")
async def list_logs(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    notice_type: str = Query(default="", description="公告类型筛选"),
):
    """分页查询日志列表（不含大字段，用于列表展示）"""
    return query_logs(page=page, page_size=page_size, notice_type=notice_type)


@router.get("/detail/{log_id}")
async def get_log_detail(log_id: int):
    """查询单条日志完整详情（含完整content和choices）"""
    detail = query_log_detail(log_id)
    if not detail:
        return {"error": "not found", "message": f"日志ID {log_id} 不存在"}
    return detail


@router.get("/stats")
async def get_logs_stats(
    range_type: Literal["1d", "7d", "30d", "month", "year", "all"] = Query(default="7d", description="统计范围：1d近1天、7d近一周、30d近一月、month本年度按月、year全部按年、all全部总量"),
):
    """
    Token消耗统计接口。
    返回：
      - summary: 总量统计
      - by_type: 按公告类型统计
      - by_month: 按月统计
      - by_year: 按年统计
      - range: 查询的时间范围
    """
    start_time, end_time = _range_time(range_type)

    summary = query_stats_token_usage(start_time, end_time)
    by_type = query_stats_token_usage_by_type(start_time, end_time)
    by_month = query_stats_token_usage_by_month(start_time, end_time)
    by_year = query_stats_token_usage_by_year(start_time, end_time)
    by_day = query_stats_token_usage_by_day(start_time, end_time)
    by_hour = query_stats_token_usage_by_hour(start_time, end_time)

    return {
        "summary": summary,
        "by_type": by_type,
        "by_month": by_month,
        "by_year": by_year,
        "by_day": by_day,
        "by_hour": by_hour,
        "range": {
            "type": range_type,
            "start_time": start_time,
            "end_time": end_time,
        },
    }
