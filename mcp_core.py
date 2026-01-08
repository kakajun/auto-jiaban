# mcp_core.py - 加班提报 MCP 主控程序（Master Control Program）
import os
import sys
import json
import logging
from datetime import datetime
from config import MCPGlobalConfig
from overtime_task import OvertimeSubmitTask, TokenExpiredError

class OvertimeMCP:
    """加班提报 MCP 主控程序：统一管理加班提报任务、配置、日志、执行调度"""
    def __init__(self, enable_console_log: bool = True):
        # 1. 初始化全局配置
        self.config = MCPGlobalConfig()
        self.overtime_task = OvertimeSubmitTask()
        self._init_mcp_logger(enable_console_log)
        self._print_mcp_start_info()

    def _init_mcp_logger(self, enable_console_log: bool):
        """MCP 日志初始化：同时输出到控制台和日志文件"""
        if not os.path.exists(self.config.LOG_DIR):
            os.makedirs(self.config.LOG_DIR)

        logger = logging.getLogger("OvertimeMCP")
        logger.setLevel(getattr(logging, self.config.MCP_LOG_LEVEL))
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        file_handler = logging.FileHandler(self.config.LOG_FILE, encoding="utf-8", errors="replace")
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        if enable_console_log:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        self.logger = logger

    def _print_mcp_start_info(self):
        """MCP 启动时打印欢迎信息和配置概要"""
        self.logger.info("=" * 50)
        self.logger.info("加班提报 MCP 主控程序启动成功")
        self.logger.info(f"MCP 版本：1.0.0")
        self.logger.info(f"接口地址：{self.config.API_URL}")
        self.logger.info(f"固定加班时间：{self.config.FIXED_OVERTIME_START} - {self.config.FIXED_OVERTIME_END}")
        self.logger.info(f"日志文件路径：{self.config.LOG_FILE}")
        self.logger.info("=" * 50)

    def dispatch_overtime_task(self, overtime_date: str, overtime_content: str = None):
        """
        MCP 核心调度方法：分发加班提报子任务，统一收集结果并记录日志
        :param overtime_date: 加班日期（YYYY-MM-DD）
        :param overtime_content: 加班内容
        :return: 任务执行结果
        """
        self.logger.info(f"开始调度加班提报任务，目标日期：{overtime_date}")

        # 调度子任务执行
        task_result = self.overtime_task.execute(overtime_date, overtime_content)

        # 记录任务执行结果（MCP 核心：留存执行痕迹）
        if task_result["task_status"] == "success":
            self.logger.info(f"加班提报任务执行成功 - 响应码：{task_result.get('status_code')}")
            # 使用 repr 避免非法字符导致日志写入失败
            self.logger.debug(f"任务详细响应：{repr(task_result['data'])}")
        else:
            self.logger.error(f"加班提报任务执行失败 - 原因：{task_result['message']}")

        return task_result

    def interactive_mode(self):
        """MCP 交互模式：提供用户控制台入口，无需修改代码，手动输入参数触发任务（核心 MCP 配置入口）"""
        self.logger.info("进入 MCP 交互模式，开始接收用户输入（输入 'quit' 退出）")

        while True:
            # 1. 接收用户输入加班日期
            overtime_date = input("\n请输入加班日期（格式：YYYY-MM-DD，如 2026-01-06）：").strip()
            if overtime_date.lower() == "quit":
                self.logger.info("用户退出 MCP 交互模式")
                break
            if not overtime_date:
                self.logger.warning("加班日期不能为空，请重新输入")
                continue

            # 2. 调度任务执行（加班内容和项目信息由子任务自动从日报获取）
            self.logger.info("用户触发加班提报任务，开始执行（内容将自动从日报获取）...")
            self.dispatch_overtime_task(overtime_date, None)
            self.logger.info("本次任务调度完成，可查看日志文件获取详细结果")

def main():
    mode = os.getenv("JABANMCP_MODE")
    if mode == "mcp":
        overtime_mcp = OvertimeMCP(enable_console_log=False)

        for line in sys.stdin:
            text = line.strip()
            if not text:
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                continue

            message_id = message.get("id")
            method = message.get("method")
            params = message.get("params") or {}

            try:
                if method == "initialize":
                    overtime_mcp.overtime_task.health_check_token()
                    protocol_version = params.get("protocolVersion", "2025-06-18")
                    result = {
                        "protocolVersion": protocol_version,
                        "serverInfo": {"name": "jabanmcp", "version": "0.1.1"},
                        "capabilities": {"tools": {}},
                    }
                    response = {"jsonrpc": "2.0", "id": message_id, "result": result}
                elif method == "tools/list":
                    tools = [
                        {
                            "name": "overtime.submit",
                            "description": (
                                "根据指定日期提交加班申请。"
                                "当用户在对话中说出类似“帮我写个2025-12-25的加班单”“为2025-12-25提个加班申请”时，"
                                "应调用此工具：从用户话语中提取日期作为 date 参数；"
                                "如果未提供 content，则自动从该日期的日报中补全加班内容和项目信息。"
                            ),
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "date": {
                                        "type": "string",
                                        "description": "加班日期，格式为 YYYY-MM-DD，例如 2025-12-25",
                                    },
                                    "content": {
                                        "type": "string",
                                        "description": "可选，加班内容，通常省略以便自动从日报读取",
                                    },
                                },
                                "required": ["date"],
                            },
                        }
                    ]
                    response = {
                        "jsonrpc": "2.0",
                        "id": message_id,
                        "result": {"tools": tools},
                    }
                elif method == "tools/call":
                    name = params.get("name")
                    arguments = params.get("arguments") or {}
                    if name != "overtime.submit":
                        error = {"code": -32601, "message": "Unknown tool name"}
                        response = {"jsonrpc": "2.0", "id": message_id, "error": error}
                    else:
                        date = arguments.get("date")
                        content = arguments.get("content")
                        task_result = overtime_mcp.dispatch_overtime_task(date, content)
                        text_content = json.dumps(task_result, ensure_ascii=False)
                        result = {
                            "content": [
                                {"type": "text", "text": text_content},
                            ]
                        }
                        response = {"jsonrpc": "2.0", "id": message_id, "result": result}
                else:
                    error = {"code": -32601, "message": "Unknown method"}
                    response = {"jsonrpc": "2.0", "id": message_id, "error": error}
            except TokenExpiredError:
                error = {"code": -40100, "message": "Token过期，请重新登录或更新 OVERTIME_API_TOKEN"}
                response = {"jsonrpc": "2.0", "id": message_id, "error": error}
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
                break
            except Exception as e:
                error = {"code": -32000, "message": str(e)}
                response = {"jsonrpc": "2.0", "id": message_id, "error": error}

            if message_id is not None:
                # 使用 ensure_ascii=True 确保输出纯 ASCII 字符，避免 stdout 编码错误
                sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
                sys.stdout.flush()
        return

    overtime_mcp = OvertimeMCP(enable_console_log=True)
    overtime_mcp.interactive_mode()


if __name__ == "__main__":
    main()
