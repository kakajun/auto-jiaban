import os
import sys
import json
import time
import subprocess

def run():
    env = os.environ.copy()
    env["JABANMCP_MODE"] = "mcp"
    env["MCP_SIMULATE"] = "1"
    env.setdefault("OVERTIME_API_URL", "http://127.0.0.1:9")
    env.setdefault("OVERTIME_API_TOKEN", "dummy")
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_core"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    def send_recv(msg, timeout=5):
        line = json.dumps(msg) + "\n"
        proc.stdin.write(line)
        proc.stdin.flush()
        start = time.time()
        while time.time() - start < timeout:
            r = proc.stdout.readline()
            if r:
                try:
                    return json.loads(r)
                except Exception:
                    return {"raw": r}
            time.sleep(0.05)
        return None

    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "TestClient", "version": "0.0.1"},
        },
    }
    tools_list = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    call_submit = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "overtime.submit", "arguments": {"date": "2026-01-07", "content": "仿真提交测试"}},
    }

    res_init = send_recv(init)
    res_tools = send_recv(tools_list)
    res_submit = send_recv(call_submit)

    print("initialize:", json.dumps(res_init, ensure_ascii=False))
    print("tools/list:", json.dumps(res_tools, ensure_ascii=False))
    print("overtime.submit(sim):", json.dumps(res_submit, ensure_ascii=False))
    init_ok = isinstance(res_init, dict) and ("result" in (res_init or {}))
    tools = ((res_tools or {}).get("result") or {}).get("tools") or []
    tools_ok = any((t or {}).get("name") == "overtime.submit" for t in tools)
    submit_ok = False
    try:
        submit_txt = (((res_submit or {}).get("result") or {}).get("content") or [{}])[0].get("text")
        submit_json = json.loads(submit_txt or "{}")
        submit_ok = submit_json.get("task_status") == "success"
    except Exception:
        submit_ok = False
    print("CONCLUSION:", "TEST PASSED" if (init_ok and tools_ok and submit_ok) else "TEST FAILED")

    try:
        proc.terminate()
    except Exception:
        pass

if __name__ == "__main__":
    run()
