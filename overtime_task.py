# overtime_task.py - 加班提报子任务，MCP 不直接处理接口，只调度该任务
import requests
import json
import base64
from datetime import datetime
from config import MCPGlobalConfig

class TokenExpiredError(Exception):
    pass

class OvertimeSubmitTask:
    """加班提报子任务（MCP 下属执行单元）"""
    def __init__(self):
        self.config = MCPGlobalConfig()
        self.headers = self._build_request_headers()
        raw_base_url = (self.config.API_URL or "").strip().rstrip("/")
        if raw_base_url and not raw_base_url.startswith(("http://", "https://")):
            raw_base_url = "https://" + raw_base_url.lstrip("/")
        self.base_url = raw_base_url
        self.valid_exist_url = f"{self.base_url}/mis/hf/common/v1/validExist"
        self.start_flow_url = f"{self.base_url}/runtime/instance/v1/start"
        self.daily_list_url = f"{self.base_url}/form/dataTemplate/v1/listJson"

    def _is_simulate(self) -> bool:
        v = getattr(self.config, "SIMULATE", "0")
        return str(v).lower() in ("1", "true", "yes")

    def _build_request_headers(self):
        """构建请求头（子任务内部辅助方法，被 MCP 调度时自动调用）"""
        return {
            "Authorization": f"Bearer {self.config.API_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "OvertimeMCP/1.0.0"
        }

    def _validate_overtime_date(self, overtime_date: str) -> bool:
        """校验加班日期格式（MCP 任务执行前的参数校验）"""
        try:
            datetime.strptime(overtime_date, self.config.DATE_FORMAT)
            return True
        except ValueError:
            return False

    def _build_datetime_range(self, overtime_date: str):
        start_time = f"{overtime_date} {self.config.FIXED_OVERTIME_START}"
        end_time = f"{overtime_date} {self.config.FIXED_OVERTIME_END}"
        return start_time, end_time

    def _handle_response(self, response):
        if getattr(response, "status_code", None) == 401:
            raise TokenExpiredError("Token 已过期")
        response.raise_for_status()

    def health_check_token(self) -> bool:
        if self._is_simulate():
            return True
        body = {
            "templateId": self.config.DAILY_TEMPLATE_ID,
            "queryFilter": {
                "pageBean": {"page": 1, "pageSize": 1},
                "querys": [],
                "sorter": [],
            },
        }
        try:
            response = requests.post(
                url=self.daily_list_url,
                json=body,
                headers=self.headers,
                timeout=self.config.REQUEST_TIMEOUT,
            )
            self._handle_response(response)
            return True
        except TokenExpiredError:
            raise
        except requests.exceptions.RequestException:
            return False

    def _request_valid_exist(self, start_time: str, end_time: str):
        if self._is_simulate():
            return {"state": False, "value": None}
        request_data = {
            "businessKey": "jbsqb",
            "id": None,
            "status": ["0", "-1"],
            "startTime": start_time,
            "endTime": end_time,
            "userId": "1044",
        }
        response = requests.post(
            url=self.valid_exist_url,
            json=request_data,
            headers=self.headers,
            timeout=self.config.REQUEST_TIMEOUT,
        )
        self._handle_response(response)
        return response.json()

    def get_daily_report(self, overtime_date: str) -> dict:
        """获取指定日期的日报内容（供 MCP 工具 daily.get 使用）"""
        if not self._validate_overtime_date(overtime_date):
            return {"error": "Invalid date format"}

        body = {
            "templateId": self.config.DAILY_TEMPLATE_ID,
            "queryFilter": {
                "pageBean": {"page": 1, "pageSize": 80},
                "querys": [],
                "sorter": [],
            },
        }
        try:
            response = requests.post(
                url=self.daily_list_url,
                json=body,
                headers=self.headers,
                timeout=self.config.REQUEST_TIMEOUT,
            )
            self._handle_response(response)
            data = response.json()
        except TokenExpiredError:
            raise
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

        rows = data.get("rows") or []
        for row in rows:
            if row.get("DATE_") == overtime_date:
                content = row.get("content") or row.get("CONTENT_")
                project_name = self.config.PROJECT_NAME
                project_id = self.config.PROJECT_ID
                return {
                    "content": content,
                    "project_name": project_name,
                    "project_id": project_id,
                }
        return {"content": None, "message": "No daily report found for this date"}

    def _build_auto_overtime_from_daily(self, overtime_date: str):
        # 复用 get_daily_report 逻辑，保持原有行为
        info = self.get_daily_report(overtime_date)
        base_content = info.get("content")
        if not base_content:
            return None

        overtime_content = f"{base_content}, 修改其bug"
        return {
            "content": overtime_content,
            "project_name": info.get("project_name"),
            "project_id": info.get("project_id"),
        }

    def _build_start_process_data(self, overtime_date: str, start_time: str, end_time: str, overtime_content: str, project_name: str = None, project_id: str = None) -> str:
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        submit_year = int(overtime_date.split("-")[0])
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        overtime_duration = int((end_dt - start_dt).total_seconds() // 3600)
        project_name_value = project_name or self.config.PROJECT_NAME
        project_id_value = project_id or self.config.PROJECT_ID
        payload = {
            "jbsqb": {
                "UPDATE_BY_ID_": "1044",
                "APPROVER_TIME_": "",
                "OVERTIME_DATE_": overtime_date,
                "DEPT_ID_": "1875170026625798144",
                "APPLICATION_TIME_": now_str,
                "UPDATE_BY_": "马军",
                "OVERTIME_DURATION_": overtime_duration,
                "EMPLOYEE_NAME_": "马军",
                "APPROVER_STATUS_": "0",
                "CREATE_TIME_": now_str,
                "SUBMIT_DATE": submit_year,
                "OVERTIME_REASON_": overtime_content,
                "PROJECT_NAME_": project_name_value,
                "CREATE_ORG_": "研发部",
                "UPDATE_TIME_": now_str,
                "CREATE_ORG_ID_": "1875170026625798144",
                "DEPT_NAME_": "研发部",
                "START_TIME_": start_time,
                "CREATE_BY_ID_": "1044",
                "CREATE_BY_": "马军",
                "EMPLOYEE_ID_": "",
                "END_TIME_": end_time,
                "APPROVER_ID_": "",
                "PROJECT_ID_": project_id_value,
                "initData": {},
            }
        }
        json_str = json.dumps(payload, ensure_ascii=False)
        return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

    def _start_overtime_process(self, data_base64: str):
        if self._is_simulate():
            class Resp:
                def __init__(self):
                    self.status_code = 200
                def json(self):
                    return {"state": True, "message": "流程启动成功(仿真)", "instId": f"SIM-{int(datetime.now().timestamp())}"}
            return Resp()
        request_data = {
            "defId": "1882365832407658496",
            "data": data_base64,
            "formType": "inner",
            "supportMobile": 0,
        }
        response = requests.post(
            url=self.start_flow_url,
            json=request_data,
            headers=self.headers,
            timeout=self.config.REQUEST_TIMEOUT,
        )
        self._handle_response(response)
        return response

    def execute(self, overtime_date: str, overtime_content: str = None) -> dict:
        """
        子任务执行入口（MCP 主控程序调用该方法触发加班提报）
        :param overtime_date: 加班日期（YYYY-MM-DD）
        :param overtime_content: 加班内容，不传则使用默认值
        :return: 任务执行结果（供 MCP 记录日志）
        """
        if not self.base_url or not self.base_url.startswith(("http://", "https://")):
            return {
                "task_status": "failed",
                "task_type": "overtime_submit",
                "message": "接口基础地址配置错误，请检查环境变量 OVERTIME_API_URL",
                "data": None,
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        if not self._validate_overtime_date(overtime_date):
            return {
                "task_status": "failed",
                "task_type": "overtime_submit",
                "message": f"日期格式错误，需符合 {self.config.DATE_FORMAT} 规范",
                "data": None,
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        start_time, end_time = self._build_datetime_range(overtime_date)
        project_name = None
        project_id = None
        if overtime_content is None:
            auto_data = self._build_auto_overtime_from_daily(overtime_date)
            if auto_data:
                overtime_content = auto_data["content"]
                project_name = auto_data.get("project_name")
                project_id = auto_data.get("project_id")
            else:
                overtime_content = self.config.OVERTIME_CONTENT_DEFAULT

        if self._is_simulate():
            data_base64 = self._build_start_process_data(
                overtime_date, start_time, end_time, overtime_content, project_name, project_id
            )
            inst_id = f"SIM-{int(datetime.now().timestamp())}"
            return {
                "task_status": "success",
                "task_type": "overtime_submit",
                "message": "仿真模式：加班流程启动模拟成功",
                "data": {
                    "state": True,
                    "message": "流程启动成功(仿真)",
                    "instId": inst_id,
                    "inst": {"id": inst_id, "subject": f"仿真加班-{overtime_date}"},
                    "data_base64": data_base64,
                },
                "status_code": 200,
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        try:
            valid_exist_result = self._request_valid_exist(start_time, end_time)
            if valid_exist_result.get("state") and valid_exist_result.get("value"):
                return {
                    "task_status": "skipped",
                    "task_type": "overtime_submit",
                    "message": "已存在未完成的加班记录，本次提报被跳过",
                    "data": valid_exist_result,
                    "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

            data_base64 = self._build_start_process_data(
                overtime_date,
                start_time,
                end_time,
                overtime_content,
                project_name,
                project_id,
            )
            response = self._start_overtime_process(data_base64)

            return {
                "task_status": "success",
                "task_type": "overtime_submit",
                "message": "加班流程启动成功",
                "data": response.json(),
                "status_code": response.status_code,
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except requests.exceptions.RequestException as e:
            return {
                "task_status": "failed",
                "task_type": "overtime_submit",
                "message": f"接口调用失败：{str(e)}",
                "data": None,
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
