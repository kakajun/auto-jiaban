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
        try:
            if sys.version_info >= (3, 11):
                from importlib.metadata import version
                self.package_version = version("jabanmcp")
            else:
                try:
                    import tomllib
                    with open("pyproject.toml", "rb") as f:
                        data = tomllib.load(f)
                        self.package_version = data["project"]["version"]
                except ImportError:
                    self.package_version = "Unknown (Dev)"
                except FileNotFoundError:
                    self.package_version = "Unknown (Installed)"
        except Exception:
            self.package_version = "Unknown"
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
            console_handler = logging.StreamHandler(stream=sys.stderr)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        self.logger = logger

    def _print_mcp_start_info(self):
        """MCP 启动时打印欢迎信息和配置概要"""
        self.logger.info("=" * 50)
        self.logger.info("加班提报 MCP 主控程序启动成功")

        self.logger.info(f"MCP 版本：{self.package_version}")
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
    mcp_mode = (mode == "mcp") or (not sys.stdin.isatty())
    if mcp_mode:
        overtime_mcp = OvertimeMCP(enable_console_log=True)

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
                    ok = overtime_mcp.overtime_task.health_check_token()
                    if not ok:
                        overtime_mcp.logger.warning("初始化阶段令牌健康检查失败（网络异常或非401），继续启动 MCP")
                    protocol_version = params.get("protocolVersion", "2025-06-18")
                    result = {
                        "protocolVersion": protocol_version,
                        "serverInfo": {"name": "jabanmcp", "version": overtime_mcp.package_version},
                        "capabilities": {"tools": {}},
                    }
                    response = {"jsonrpc": "2.0", "id": message_id, "result": result}
                elif method == "tools/list":
                    tools = [
                        {
                            "name": "daily.get",
                            "description": "获取指定日期的日报内容。建议在调用 overtime.submit 之前先调用此工具获取日报，利用模型能力将日报内容润色为正式的加班申请理由。",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "date": {
                                        "type": "string",
                                        "description": "日期，格式为 YYYY-MM-DD",
                                    }
                                },
                                "required": ["date"],
                            },
                        },
                        {
                            "name": "overtime.submit",
                            "description": (
                                "根据指定日期提交加班申请。"
                                "如果用户提供了content参数，请先用模型能力对其进行润色，然后将润色后的内容作为content参数传入。"
                                "如果用户未提供content参数，建议先调用 daily.get 获取日报内容，经模型润色后，将润色好的内容作为 content 参数传入。"
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
                                        "description": "可选，经过模型润色后的加班内容。建议提供此参数以获得更好的提报质量。不要出现'工作内容润色：依据','加班时间','提报目的','根据','日报','项目编号'等字眼。这就是个简短加班内容, 主要为了修改bug才加班",
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

                    if name == "daily.get":
                        date = arguments.get("date")
                        daily_info = overtime_mcp.overtime_task.get_daily_report(date)
                        text_content = json.dumps(daily_info, ensure_ascii=False)
                        result = {
                            "content": [{"type": "text", "text": text_content}]
                        }
                        response = {"jsonrpc": "2.0", "id": message_id, "result": result}
                    elif name == "overtime.submit":
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
                        error = {"code": -32601, "message": "Unknown tool name"}
                        response = {"jsonrpc": "2.0", "id": message_id, "error": error}
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
                sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
                sys.stdout.flush()
    else:
        om = OvertimeMCP(enable_console_log=True)
        om.interactive_mode()


if __name__ == "__main__":
    main()
