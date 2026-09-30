#!/usr/bin/env python3
"""One-shot English sweep for backend/app/services/simulation_ipc.py."""
import re

P = "backend/app/services/simulation_ipc.py"
src = open(P, encoding="utf-8").read()

M = {
    "模拟IPC通信模块": "Simulation IPC module",
    "用于Flask后端和模拟脚本之间的进程间通信": "Inter-process communication between the Flask backend and simulation scripts.",
    "通过文件系统实现简单的命令/响应模式：": "A simple command/response pattern over the filesystem:",
    "Flask写入命令到 commands/ 目录": "1. Flask writes commands into the commands/ directory",
    "模拟脚本轮询命令目录，执行命令并写入响应到 responses/ 目录": "2. the sim script polls for commands, runs them, and writes responses to responses/",
    "Flask轮询响应目录获取结果": "3. Flask polls the responses directory for results",
    "命令类型": "Command types",
    "单个Agent采访": "single-agent interview",
    "批量采访": "batch interview",
    "关闭环境": "close environment",
    "命令状态": "Command status",
    "IPC命令": "An IPC command.",
    "IPC响应": "An IPC response.",
    "模拟IPC客户端（Flask端使用）": "    Simulation IPC client (Flask side).",
    "用于向模拟进程发送命令并等待响应": "    Sends commands to the simulation process and waits for responses.",
    "初始化IPC客户端": "        Initialize the IPC client.",
    "simulation_dir: 模拟数据目录": "            simulation_dir: simulation data directory",
    "# 确保目录存在": "        # make sure the directory exists",
    "发送命令并等待响应": "        Send a command and wait for its response.",
    "command_type: 命令类型": "            command_type: command type",
    "args: 命令参数": "            args: command arguments",
    "timeout: 超时时间（秒）": "            timeout: seconds",
    "poll_interval: 轮询间隔（秒）": "            poll_interval: polling interval in seconds",
    "TimeoutError: 等待响应超时": "            TimeoutError: response wait timed out",
    "# 写入命令文件": "        # write the command file",
    "发送IPC命令: {command_type.value}, command_id={command_id}": "IPC command sent: {command_type.value}, command_id={command_id}",
    "# 等待响应": "        # wait for the response",
    "# 清理命令和响应文件": "                    # clean up command and response files",
    "收到IPC响应: command_id={command_id}, status={response.status.value}": "IPC response received: command_id={command_id}, status={response.status.value}",
    "解析响应失败: {e}": "Failed to parse the response: {e}",
    "# 超时": "        # timed out",
    "等待IPC响应超时: command_id={command_id}": "IPC response wait timed out: command_id={command_id}",
    "# 清理命令文件": "        # clean up the command file",
    "等待命令响应超时 ({timeout}秒)": "Command response wait timed out ({timeout}s)",
    "发送单个Agent采访命令": "        Send a single-agent interview command.",
    "prompt: 采访问题": "            prompt: interview question",
    "platform: 指定平台（可选）": "            platform: optional platform",
    "- None: 双平台模拟时同时采访两个平台，单平台模拟时采访该平台": "                - None: both platforms on dual-platform runs, else that run's platform",
    "timeout: 超时时间": "            timeout: seconds",
    "IPCResponse，result字段包含采访结果": "            IPCResponse whose result holds the interview outcome",
    "发送批量采访命令": "        Send a batch-interview command.",
    "发送关闭环境命令": "        Send the close-environment command.",
    "检查模拟环境是否存活": "        Check whether the simulation environment is alive.",
    "通过检查 env_status.json 文件来判断": "        Decided by checking the env_status.json file.",
    "模拟IPC服务器（模拟脚本端使用）": "    Simulation IPC server (simulation-script side).",
    "轮询命令目录，执行命令并返回响应": "    Polls the command directory, executes commands, returns responses.",
    "初始化IPC服务器": "        Initialize the IPC server.",
    "# 环境状态": "        # environment status",
    "标记服务器为运行状态": '        """Mark the server as running."""',
    "标记服务器为停止状态": '        """Mark the server as stopped."""',
    "更新环境状态文件": '        """Update the environment status file."""',
    "轮询命令目录，返回第一个待处理的命令": "        Poll the command directory; return the first pending command.",
    "IPCCommand 或 None": "            IPCCommand or None",
    "# 按时间排序获取命令文件": "        # command files sorted by time",
    "读取命令文件失败: {filepath}, {e}": "Failed to read command file: {filepath}, {e}",
    "发送响应": "        Send a response.",
    "response: IPC响应": "            response: the IPC response",
    "# 删除命令文件": "        # delete the command file",
    "发送成功响应": '        """Send a success response."""',
    "发送错误响应": '        """Send an error response."""',
}

keys = sorted(M.keys(), key=len, reverse=True)
lines = src.splitlines(keepends=True)
ok = miss = 0
for i, line in enumerate(lines):
    if not re.search(r"[\u4e00-\u9fff]", line):
        continue
    body = line.rstrip("\n")
    for zh in keys:
        if zh in body:
            body = body.replace(zh, M[zh])
            ok += 1
            break
    else:
        miss += 1
        print(f"MISS {i+1}: {body.strip()[:70]}")
    lines[i] = body + "\n"
open(P, "w", encoding="utf-8").write("".join(lines))
cjk = sum(1 for l in lines if re.search(r"[\u4e00-\u9fff]", l))
print(f"ipc: {ok} ok, {miss} miss, {cjk} left")
