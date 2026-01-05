# config.py - MCP 全局配置类，统一维护所有参数，便于扩展
import os
from dotenv import load_dotenv

# 加载.env配置，MCP 启动时先加载全局配置
load_dotenv()

class MCPGlobalConfig:
    """MCP 主控程序全局配置"""
    # 接口相关配置（来自.env）
    API_TOKEN = os.getenv("OVERTIME_API_TOKEN")
    API_URL = os.getenv("OVERTIME_API_URL")
    DAILY_TEMPLATE_ID = os.getenv("DAILY_TEMPLATE_ID", "1876523888959934464")
    REQUEST_TIMEOUT = int(os.getenv("MCP_TIMEOUT", 30))

    # 加班固定参数（MCP 统一维护，可直接在这修改，无需动任务代码）
    FIXED_OVERTIME_START = "18:30:00"
    FIXED_OVERTIME_END = "20:30:00"

    # MCP 日志配置
    LOG_DIR = "./logs"
    LOG_FILE = f"{LOG_DIR}/overtime_mcp.log"
    MCP_LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO")
    DATE_FORMAT = "%Y-%m-%d"  # 加班日期格式规范
    OVERTIME_CONTENT_DEFAULT = "项目研发推进，完成既定工作任务"  # 默认加班内容
