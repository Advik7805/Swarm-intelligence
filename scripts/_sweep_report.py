#!/usr/bin/env python3
"""One-shot English sweep for backend/app/api/report.py."""
import re

P = "backend/app/api/report.py"
src = open(P, encoding="utf-8").read()

M = {
    "Report API路由": "Report API routes.",
    "提供模拟报告生成、获取、对话等接口": "Endpoints for report generation, retrieval, and Report Agent chat.",
    "报告生成接口": "Report generation endpoint",
    "生成模拟分析报告（异步任务）": "    Generate the simulation analysis report (async task).",
    "这是一个耗时操作，接口会立即返回task_id，": "    Long-running: the endpoint returns a task_id immediately;",
    "使用 GET /api/report/generate/status 查询进度": "    poll GET /api/report/generate/status for progress.",
    "请求（JSON）：": "    Request (JSON):",
    "\"simulation_id\": \"sim_xxxx\",    // 必填，模拟ID": '"simulation_id": "sim_xxxx",    // required: simulation id',
    "\"force_regenerate\": false        // 可选，强制重新生成": '"force_regenerate": false        // optional: force regeneration',
    "返回：": "    Returns:",
    "报告生成任务已启动": "Report generation task started",
    "# 获取模拟信息": "        # fetch simulation info",
    "# 获取项目信息": "        # fetch project info",
    "# 提前生成 report_id，以便立即返回给前端": "        # pre-generate report_id so it can be returned immediately",
    "报告生成失败: {str(e)}": "Report generation failed: {str(e)}",
    "启动报告生成任务失败: {str(e)}": "Failed to start report generation task: {str(e)}",
    "查询报告生成任务进度": "    Query report generation task progress.",
    "\"task_id\": \"task_xxxx\",         // 可选，generate返回的task_id": '"task_id": "task_xxxx",         // optional: task_id returned by generate',
    "\"simulation_id\": \"sim_xxxx\"     // 可选，模拟ID": '"simulation_id": "sim_xxxx"     // optional: simulation id',
    "# 如果提供了simulation_id，先检查是否已有完成的报告": "        # with a simulation_id, check for an existing finished report first",
    "查询任务状态失败: {str(e)}": "Failed to query task status: {str(e)}",
    "报告获取接口": "Report retrieval endpoints",
    "获取报告详情": "    Get report details.",
    "获取报告失败: {str(e)}": "Failed to get the report: {str(e)}",
    "根据模拟ID获取报告": "    Get the report for a simulation id.",
    "列出所有报告": "    List all reports.",
    "Query参数：": "    Query params:",
    "simulation_id: 按模拟ID过滤（可选）": "        simulation_id: filter by simulation id (optional)",
    "limit: 返回数量限制（默认50）": "        limit: max items to return (default 50)",
    "列出报告失败: {str(e)}": "Failed to list reports: {str(e)}",
    "下载报告（Markdown格式）": "    Download the report (Markdown).",
    "返回Markdown文件": "    Returns the Markdown file.",
    "# 如果MD文件不存在，生成一个临时文件": "            # generate a temp file if the Markdown is missing",
    "下载报告失败: {str(e)}": "Failed to download the report: {str(e)}",
    "删除报告": '        """Delete a report."""',
    "删除报告失败: {str(e)}": "Failed to delete the report: {str(e)}",
    "Report Agent对话接口": "Report Agent chat endpoints",
    "与Report Agent对话": "    Chat with the Report Agent.",
    "Report Agent可以在对话中自主调用检索工具来回答问题": "    The agent autonomously calls retrieval tools while answering.",
    "\"simulation_id\": \"sim_xxxx\",        // 必填，模拟ID": '"simulation_id": "sim_xxxx",        // required: simulation id',
    "\"message\": \"请解释一下舆情走向\",    // 必填，用户消息": '"message": "Explain how sentiment is trending",    // required: user message',
    "\"chat_history\": [                   // 可选，对话历史": '"chat_history": [                   // optional: chat history',
    "\"response\": \"Agent回复...\",": '"response": "Agent reply...",',
    "\"tool_calls\": [调用的工具列表],": '"tool_calls": [tools invoked],',
    "\"sources\": [信息来源]": '"sources": [information sources]',
    "# 获取模拟和项目信息": "        # fetch simulation and project info",
    "# 创建Agent并进行对话": "        # create the agent and chat",
    "对话失败: {str(e)}": "Chat failed: {str(e)}",
    "报告进度与分章节接口": "Report progress and per-section endpoints",
    "获取报告生成进度（实时）": "    Get report generation progress (real time).",
    "正在生成章节: 关键发现": "Generating section: key findings",
    "\"current_section\": \"关键发现\",": '"current_section": "Key findings",',
    "\"completed_sections\": [\"执行摘要\", \"模拟背景\"],": '"completed_sections": ["Executive summary", "Simulation background"],',
    "获取报告进度失败: {str(e)}": "Failed to get report progress: {str(e)}",
    "获取已生成的章节列表（分章节输出）": "    List the sections generated so far (section-by-section output).",
    "前端可以轮询此接口获取已生成的章节内容，无需等待整个报告完成": "    The frontend can poll this for finished sections without waiting for the full report.",
    "\"content\": \"## 执行摘要": '"content": "## Executive summary',
    "# 获取报告状态": "        # fetch the report status",
    "获取章节列表失败: {str(e)}": "Failed to list sections: {str(e)}",
    "获取单个章节内容": "    Get one section's content.",
    "获取章节内容失败: {str(e)}": "Failed to get section content: {str(e)}",
    "报告状态检查接口": "Report status check endpoint",
    "检查模拟是否有报告，以及报告状态": "    Check whether a simulation has a report and its status.",
    "用于前端判断是否解锁Interview功能": "    The frontend uses this to unlock the Interview feature.",
    "# 只有报告完成后才解锁interview": "        # interviews unlock only when the report is complete",
    "检查报告状态失败: {str(e)}": "Failed to check report status: {str(e)}",
    "Agent 日志接口": "Agent log endpoints",
    "获取 Report Agent 的详细执行日志": "    Get detailed Report Agent execution logs.",
    "实时获取报告生成过程中的每一步动作，包括：": "    Streams every step of report generation:",
    "- 报告开始、规划开始/完成": "    - report start, planning start/finish",
    "- 每个章节的开始、工具调用、LLM响应、完成": "    - per-section start, tool calls, LLM responses, completion",
    "- 报告完成或失败": "    - report finished or failed",
    "from_line: 从第几行开始读取（可选，默认0，用于增量获取）": "        from_line: line to start reading from (optional, default 0; incremental)",
    "\"section_title\": \"执行摘要\",": '"section_title": "Executive summary",',
    "获取Agent日志失败: {str(e)}": "Failed to get agent logs: {str(e)}",
    "获取完整的 Agent 日志（一次性获取全部）": "    Get the full agent log (all at once).",
    "控制台日志接口": "Console log endpoints",
    "获取 Report Agent 的控制台输出日志": "    Get the Report Agent console output.",
    "实时获取报告生成过程中的控制台输出（INFO、WARNING等），": "    Streams console output (INFO, WARNING, ...) during generation;",
    "这与 agent-log 接口返回的结构化 JSON 日志不同，": "    unlike agent-log (structured JSON),",
    "是纯文本格式的控制台风格日志。": "    this is plain console-style text.",
    "搜索完成: 找到 15 条相关事实": "Search done: found 15 relevant facts",
    "图谱搜索: graph_id=xxx, query=...": "Graph search: graph_id=xxx, query=...",
    "获取控制台日志失败: {str(e)}": "Failed to get console logs: {str(e)}",
    "获取完整的控制台日志（一次性获取全部）": "    Get the full console log (all at once).",
    "工具调用接口（供调试使用）": "Tool invocation endpoints (debug)",
    "图谱搜索工具接口（供调试使用）": "    Graph search tool endpoint (debug).",
    "\"query\": \"搜索查询\",": '"query": "search query",',
    "图谱搜索失败: {str(e)}": "Graph search failed: {str(e)}",
    "图谱统计工具接口（供调试使用）": "    Graph stats tool endpoint (debug).",
    "获取图谱统计失败: {str(e)}": "Failed to get graph stats: {str(e)}",
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
print(f"report.py: {ok} ok, {miss} miss, {cjk} left")
