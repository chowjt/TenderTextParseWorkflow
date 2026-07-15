"""
API鉴权模块 - 验证请求头中的Bearer Token。
"""

from fastapi import Header, HTTPException, Depends
from app.config import setup_logging

logger = setup_logging()

# 从环境变量读取允许的API Key（多个以逗号分隔）
import os
_API_KEYS_STR = os.getenv("API_KEYS", "")
ALLOWED_API_KEYS = [k.strip() for k in _API_KEYS_STR.split(",") if k.strip()]


async def verify_authorization(authorization: str = Header(..., alias="Authorization")) -> str:
    """
    验证 Authorization 请求头。
    格式: Bearer <api_key>
    日志中脱敏处理，只保留key后4位。
    """
    if not authorization.startswith("Bearer "):
        logger.warning(f"[鉴权失败] Authorization格式错误: {authorization[:20]}...")
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected: Bearer <api_key>")

    token = authorization[7:].strip()

    # 脱敏日志：只保留后4位
    masked = "****" + token[-4:] if len(token) >= 4 else "****"
    logger.info(f"[鉴权校验] token后4位={masked}")

    if not ALLOWED_API_KEYS:
        logger.warning("[鉴权配置] 未配置API_KEYS环境变量，拒绝所有请求")
        raise HTTPException(status_code=500, detail="API_KEYS not configured on server")

    if token not in ALLOWED_API_KEYS:
        logger.warning(f"[鉴权失败] 无效token: {masked}")
        raise HTTPException(status_code=401, detail="Invalid API key")

    logger.info(f"[鉴权通过] token={masked}")
    return token
