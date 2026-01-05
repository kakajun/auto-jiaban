# mcp_core.py - 加班提报 MCP 主控程序（Master Control Program）
import os
import logging
from datetime import datetime
from config import MCPGlobalConfig
from overtime_task import OvertimeSubmitTask

class OvertimeMCP:
    """加班提报 MCP 主控程序：统一管理加班提报任务、配置、日志、执行调度"""
    def __init__(self):
        # 1. 初始化全局配置
        self.config = MCPGlobalConfig()
        # 2. 初始化子任务实例
        self.overtime_task = OvertimeSubmitTask()
        # 3. 初始化 MCP 日志系统（核心：记录任务执行结果，便于排查问题）
        self._init_mcp_logger()
        # 4. 打印 MCP 启动信息
        self._print_mcp_start_info()

    def _init_mcp_logger(self):
        """MCP 日志初始化：同时输出到控制台和日志文件"""
        # 创建日志目录
        if not os.path.exists(self.config.LOG_DIR):
            os.makedirs(self.config.LOG_DIR)

        # 配置日志格式
        logger = logging.getLogger("OvertimeMCP")
        logger.setLevel(getattr(logging, self.config.MCP_LOG_LEVEL))
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # 文件处理器
        file_handler = logging.FileHandler(self.config.LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)

        # 添加处理器
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

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
            self.logger.debug(f"任务详细响应：{task_result['data']}")
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

if __name__ == "__main__":
    # 启动 MCP 主控程序
    overtime_mcp = OvertimeMCP()

    # 进入交互模式（用户手动触发任务，也可添加定时调度方法）
    overtime_mcp.interactive_mode()
