#!/usr/bin/env python3
"""One-shot English sweep for backend/app/api/graph.py."""
import re

P = "backend/app/api/graph.py"
src = open(P, encoding="utf-8").read()

M = {
    "图谱相关API路由": "Graph API routes.",
    "采用项目上下文机制，服务端持久化状态": "Uses a project-context mechanism with server-side persisted state.",
    "# 获取日志器": "# get the loggers",
    "检查文件扩展名是否允许": "        Check whether the file extension is allowed.",
    "项目管理接口": "Project management endpoints",
    "获取项目详情": "    Get project details.",
    "列出所有项目": "    List all projects.",
    "删除项目": "    Delete a project.",
    "重置项目状态（用于重新构建图谱）": "    Reset project state (to rebuild the graph).",
    "# 重置到本体已生成状态": "        # reset to ontology-generated state",
    "接口1：上传文件并生成本体": "Endpoint 1: upload files and generate the ontology",
    "接口1：上传文件，分析生成本体定义": "    Endpoint 1: upload files and analyze them into an ontology definition.",
    "请求方式：multipart/form-data": "    Request: multipart/form-data",
    "参数：": "    Params:",
    "files: 上传的文件（PDF/MD/TXT），可多个": "        files: uploaded files (PDF/MD/TXT), multiple allowed",
    "simulation_requirement: 模拟需求描述（必填）": "        simulation_requirement: requirement text (required)",
    "project_name: 项目名称（可选）": "        project_name: project name (optional)",
    "additional_context: 额外说明（可选）": "        additional_context: extra notes (optional)",
    "=== 开始生成本体定义 ===": "=== generating ontology definition ===",
    "# 获取参数": "        # read params",
    "项目名称: {project_name}": "Project name: {project_name}",
    "模拟需求: {simulation_requirement[:100]}...": "Simulation requirement: {simulation_requirement[:100]}...",
    "# 获取上传的文件": "        # get uploaded files",
    "# 创建项目": "        # create the project",
    "创建项目: {project.project_id}": "Project created: {project.project_id}",
    "# 保存文件并提取文本": "        # save files and extract text",
    "# 保存文件到项目目录": "                # save the file into the project dir",
    "# 提取文本": "                # extract text",
    "# 保存提取的文本": "        # save the extracted text",
    "文本提取完成，共 {len(all_text)} 字符": "Text extraction done: {len(all_text)} chars",
    "# 生成本体": "        # generate the ontology",
    "调用 LLM 生成本体定义...": "Calling the LLM to generate the ontology...",
    "# 保存本体到项目": "        # store the ontology on the project",
    "本体生成完成: {entity_count} 个实体类型, {edge_count} 个关系类型": "Ontology generated: {entity_count} entity types, {edge_count} relation types",
    "=== 本体生成完成 === 项目ID: {project.project_id}": "=== ontology done === project: {project.project_id}",
    "接口2：构建图谱": "Endpoint 2: build the graph",
    "接口2：根据project_id构建图谱": "    Endpoint 2: build the graph for a given project_id.",
    "\"project_id\": \"proj_xxxx\",  // 必填，来自接口1": '"project_id": "proj_xxxx",  // required, from endpoint 1',
    "\"graph_name\": \"图谱名称\",    // 可选": '"graph_name": "Graph name",    // optional',
    "\"chunk_size\": 500,          // 可选，默认500": '"chunk_size": 500,          // optional, default 500',
    "\"chunk_overlap\": 50         // 可选，默认50": '"chunk_overlap": 50         // optional, default 50',
    "图谱构建任务已启动": "Graph build task started",
    "=== 开始构建图谱 ===": "=== building graph ===",
    "# 检查配置": "        # validate config",
    "配置错误: {errors}": "Config error: {errors}",
    "# 解析请求": "        # parse the request",
    "请求参数: project_id={project_id}": "Request params: project_id={project_id}",
    "# 获取项目": "        # fetch the project",
    "# 检查项目状态": "        # check project status",
    "强制重新构建": "force rebuild",
    "# 获取配置": "        # get config",
    "# 更新项目配置": "        # update project config",
    "# 获取提取的文本": "        # get extracted text",
    "# 获取本体": "        # get the ontology",
    "# 创建异步任务": "        # create the async task",
    "构建图谱: {graph_name}": "Build graph: {graph_name}",
    "创建图谱构建任务: task_id={task_id}, project_id={project_id}": "Graph build task created: task_id={task_id}, project_id={project_id}",
    "# 更新项目状态": "        # update project status",
    "# 启动后台任务": "        # start the background job",
    "开始构建图谱...": "starting graph build...",
    "# 创建图谱构建服务": "                # create the graph build service",
    "# 分块": "                # chunking",
    "# 创建图谱": "                    # create the graph",
    "# 设置本体": "                    # set the ontology",
    "# 添加文本（progress_callback 签名是 (msg, progress_ratio)）": "                    # add text (progress_callback signature: (msg, progress_ratio))",
    "# 等待Zep处理完成（查询每个episode的processed状态）": "                # wait for Zep ingestion (poll each episode's processed flag)",
    "# 获取图谱数据": "                # fetch graph data",
    "图谱构建完成: graph_id={graph_id}, 节点={node_count}, 边={edge_count}": "Graph built: graph_id={graph_id}, nodes={node_count}, edges={edge_count}",
    "# 更新项目状态为失败": "                # mark the project failed",
    "图谱构建失败: {str(e)}": "Graph build failed: {str(e)}",
    "# 启动后台线程": "        # start the background thread",
    "任务查询接口": "Task query endpoints",
    "查询任务状态": "    Query task status.",
    "列出所有任务": "    List all tasks.",
    "图谱数据接口": "Graph data endpoints",
    "获取图谱数据（节点和边）": "    Get graph data (nodes and edges).",
    "删除Zep图谱": "    Delete the Zep graph.",
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
print(f"graph.py: {ok} ok, {miss} miss, {cjk} left")
