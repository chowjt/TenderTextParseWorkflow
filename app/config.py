import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

# ============================================================
# 模型配置 - 从 .env 读取敏感信息
# ============================================================

MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3")
MODEL_BASE_URL = os.getenv("MODEL_BASE_URL", "https://api.siliconflow.cn/v1")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")

# 模型参数
MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.4"))
MODEL_MAX_TOKEN = int(os.getenv("MODEL_MAX_TOKEN", "8192"))

# ============================================================
# 公告类型枚举 - 一比一还原JSON中ifElseNode的4个条件分支
# ============================================================

NOTICE_TYPE_ZHAOBIAO = "招标公告"
NOTICE_TYPE_BIANGENG = "变更公告"
NOTICE_TYPE_ZHONGBIAO_HOUXUANREN = "中标候选人公示"
NOTICE_TYPE_JIEGUO = "结果公告"

SUPPORTED_NOTICE_TYPES = [
    NOTICE_TYPE_ZHAOBIAO,
    NOTICE_TYPE_BIANGENG,
    NOTICE_TYPE_ZHONGBIAO_HOUXUANREN,
    NOTICE_TYPE_JIEGUO,
]

# 不支持类型的提示回复 - 一比一还原JSON中指定回复节点
UNSUPPORTED_TYPE_MESSAGE = "不支持解析的公告类型！当前支持的公告类型为：招标公告、变更公告、中标候选人公示和结果公告。"

# ============================================================
# 日志配置
# ============================================================

LOG_DIR = _project_root / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "workflow.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-25s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> logging.Logger:
    """配置工作流日志，同时输出到控制台和轮转文件。"""
    logger = logging.getLogger("TenderTextParseWorkflow")
    logger.setLevel(logging.DEBUG)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件handler（轮转）
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
