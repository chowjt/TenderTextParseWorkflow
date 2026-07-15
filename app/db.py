"""
SQLite数据库模块 - 存储每次请求的完整日志。
字段按3大类设计：请求Header、请求Body、响应Body。
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.config import setup_logging

logger = setup_logging()

# 数据库文件路径（项目根目录/data/logs.db）
DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "logs.db"


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- 基础信息
            request_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            elapsed_ms INTEGER DEFAULT 0,

            -- 一、请求Header
            auth_masked TEXT DEFAULT '',
            content_type TEXT DEFAULT '',

            -- 二、请求Body - 对话标识类
            chat_id TEXT DEFAULT '',
            response_chat_item_id TEXT DEFAULT '',

            -- 二、请求Body - 模式控制
            stream INTEGER DEFAULT 0,
            detail INTEGER DEFAULT 0,

            -- 二、请求Body - 业务变量
            var_id TEXT DEFAULT '',
            var_notice_type TEXT DEFAULT '',
            var_content TEXT DEFAULT '',
            var_spare1 TEXT DEFAULT '',
            var_spare2 TEXT DEFAULT '',
            var_spare3 TEXT DEFAULT '',

            -- 二、请求Body - 消息
            messages TEXT DEFAULT '',

            -- 三、响应Body - 元数据
            resp_id TEXT DEFAULT '',
            resp_model TEXT DEFAULT '',
            resp_prompt_tokens INTEGER DEFAULT 0,
            resp_completion_tokens INTEGER DEFAULT 0,
            resp_total_tokens INTEGER DEFAULT 0,

            -- 三、响应Body - 结果
            resp_choices TEXT DEFAULT '',

            -- 状态
            status_code INTEGER DEFAULT 0,
            error_message TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"[数据库初始化] {DB_PATH}")


def insert_log(data: Dict[str, Any]) -> int:
    """插入一条请求日志"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO request_logs (
            request_id, created_at, elapsed_ms,
            auth_masked, content_type,
            chat_id, response_chat_item_id,
            stream, detail,
            var_id, var_notice_type,
            var_content, var_spare1, var_spare2, var_spare3,
            messages,
            resp_id, resp_model,
            resp_prompt_tokens, resp_completion_tokens, resp_total_tokens,
            resp_choices,
            status_code, error_message
        ) VALUES (
            :request_id, :created_at, :elapsed_ms,
            :auth_masked, :content_type,
            :chat_id, :response_chat_item_id,
            :stream, :detail,
            :var_id, :var_notice_type,
            :var_content, :var_spare1, :var_spare2, :var_spare3,
            :messages,
            :resp_id, :resp_model,
            :resp_prompt_tokens, :resp_completion_tokens, :resp_total_tokens,
            :resp_choices,
            :status_code, :error_message
        )
    """, data)
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def query_logs(page: int = 1, page_size: int = 20, notice_type: str = "") -> Dict[str, Any]:
    """
    分页查询日志列表。
    返回摘要信息（不含var_content和resp_choices等大字段）。
    """
    conn = get_connection()
    cursor = conn.cursor()

    where = ""
    params: list = []
    if notice_type:
        where = "WHERE var_notice_type = ?"
        params.append(notice_type)

    # 总数
    cursor.execute(f"SELECT COUNT(*) FROM request_logs {where}", params)
    total = cursor.fetchone()[0]

    # 分页数据（不查大字段）
    offset = (page - 1) * page_size
    cursor.execute(f"""
        SELECT id, request_id, created_at, elapsed_ms,
               auth_masked, content_type,
               chat_id, response_chat_item_id,
               stream, detail,
               var_id, var_notice_type,
               var_spare1, var_spare2, var_spare3,
               resp_id, resp_model,
               resp_prompt_tokens, resp_completion_tokens, resp_total_tokens,
               status_code, error_message
        FROM request_logs {where}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    """, params + [page_size, offset])

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "records": rows,
    }


def query_log_detail(log_id: int) -> Optional[Dict[str, Any]]:
    """查询单条日志完整详情（含大字段）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM request_logs WHERE id = ?", (log_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def query_stats_token_usage(start_time: str, end_time: str) -> Dict[str, Any]:
    """
    统计指定时间范围内的 Token 消耗总量。
    start_time/end_time 格式: YYYY-MM-DD HH:MM:SS
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            COALESCE(SUM(resp_prompt_tokens), 0) AS prompt_tokens,
            COALESCE(SUM(resp_completion_tokens), 0) AS completion_tokens,
            COALESCE(SUM(resp_total_tokens), 0) AS total_tokens,
            COUNT(*) AS request_count
        FROM request_logs
        WHERE created_at >= ? AND created_at <= ?
        """,
        (start_time, end_time),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "request_count": 0,
    }


def query_stats_token_usage_by_type(start_time: str, end_time: str) -> List[Dict[str, Any]]:
    """按公告类型统计指定时间范围内的 Token 消耗"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            var_notice_type AS notice_type,
            COALESCE(SUM(resp_prompt_tokens), 0) AS prompt_tokens,
            COALESCE(SUM(resp_completion_tokens), 0) AS completion_tokens,
            COALESCE(SUM(resp_total_tokens), 0) AS total_tokens,
            COUNT(*) AS request_count
        FROM request_logs
        WHERE created_at >= ? AND created_at <= ?
        GROUP BY var_notice_type
        ORDER BY total_tokens DESC
        """,
        (start_time, end_time),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def query_stats_token_usage_by_month(start_time: str, end_time: str) -> List[Dict[str, Any]]:
    """按月统计指定时间范围内的 Token 消耗"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            strftime('%Y-%m', created_at) AS month,
            COALESCE(SUM(resp_prompt_tokens), 0) AS prompt_tokens,
            COALESCE(SUM(resp_completion_tokens), 0) AS completion_tokens,
            COALESCE(SUM(resp_total_tokens), 0) AS total_tokens,
            COUNT(*) AS request_count
        FROM request_logs
        WHERE created_at >= ? AND created_at <= ?
        GROUP BY strftime('%Y-%m', created_at)
        ORDER BY month ASC
        """,
        (start_time, end_time),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def query_stats_token_usage_by_year(start_time: str, end_time: str) -> List[Dict[str, Any]]:
    """按年统计指定时间范围内的 Token 消耗"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            strftime('%Y', created_at) AS year,
            COALESCE(SUM(resp_prompt_tokens), 0) AS prompt_tokens,
            COALESCE(SUM(resp_completion_tokens), 0) AS completion_tokens,
            COALESCE(SUM(resp_total_tokens), 0) AS total_tokens,
            COUNT(*) AS request_count
        FROM request_logs
        WHERE created_at >= ? AND created_at <= ?
        GROUP BY strftime('%Y', created_at)
        ORDER BY year ASC
        """,
        (start_time, end_time),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def query_stats_token_usage_by_day(start_time: str, end_time: str) -> List[Dict[str, Any]]:
    """按天统计指定时间范围内的 Token 消耗"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            strftime('%Y-%m-%d', created_at) AS day,
            COALESCE(SUM(resp_prompt_tokens), 0) AS prompt_tokens,
            COALESCE(SUM(resp_completion_tokens), 0) AS completion_tokens,
            COALESCE(SUM(resp_total_tokens), 0) AS total_tokens,
            COUNT(*) AS request_count
        FROM request_logs
        WHERE created_at >= ? AND created_at <= ?
        GROUP BY strftime('%Y-%m-%d', created_at)
        ORDER BY day ASC
        """,
        (start_time, end_time),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


# 启动时自动初始化
init_db()
