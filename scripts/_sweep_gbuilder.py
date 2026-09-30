#!/usr/bin/env python3
"""One-shot English sweep for backend/app/services/graph_builder.py."""
import re

P = "backend/app/services/graph_builder.py"
src = open(P, encoding="utf-8").read()

M = {
    "图谱构建服务": "Graph build service",
    "接口2：使用Zep API构建Standalone Graph": "Endpoint 2: build a Standalone Graph with the Zep API.",
    "图谱信息": "Graph information.",
    "图谱构建服务": "    Graph build service.",
    "负责调用Zep API构建知识图谱": "    Builds the knowledge graph through the Zep API.",
    "ZEP_API_KEY 未配置": "ZEP_API_KEY not configured",
    "异步构建图谱": "        Build the graph asynchronously.",
    "text: 输入文本": "            text: input text",
    "ontology: 本体定义（来自接口1的输出）": "            ontology: ontology definition (endpoint-1 output)",
    "graph_name: 图谱名称": "            graph_name: graph name",
    "chunk_size: 文本块大小": "            chunk_size: text chunk size",
    "chunk_overlap: 块重叠大小": "            chunk_overlap: chunk overlap",
    "batch_size: 每批发送的块数量": "            batch_size: chunks sent per batch",
    "任务ID": "            The task id.",
    "# 创建任务": "        # create the task",
    "# 在后台线程中执行构建": "        # run the build on a background thread",
    "图谱构建工作线程": '        """Graph build worker thread."""',
    "# 1. 创建图谱": "            # 1. create the graph",
    "# 2. 设置本体": "            # 2. set the ontology",
    "# 3. 文本分块已在 Cloud mutation 前完成并验证": "            # 3. chunking was validated before the Cloud mutations",
    "# 4. 分批发送数据": "            # 4. send data in batches",
    "# 5. 等待Zep处理完成": "            # 5. wait for Zep ingestion",
    "# 6. 获取图谱信息": "            # 6. fetch graph info",
    "# 完成": "            # done",
    "设置图谱本体（公开方法）": '        """Set the graph ontology (public method)."""',
    "# 抑制 Pydantic v2 关于 Field(default=None) 的警告": "        # silence Pydantic v2 warnings about Field(default=None)",
    "# 这是 Zep SDK 要求的用法，警告来自动态类创建，可以安全忽略": "        # the Zep SDK requires this; the warnings come from dynamic class creation and are safe",
    "将保留名称转换为安全名称": '            """Convert reserved names to safe names."""',
    "# 动态创建实体类型": "        # create entity types dynamically",
    "# 创建属性字典和类型注解（Pydantic v2 需要）": "            # build the attrs dict and type annotations (Pydantic v2)",
    "使用安全名称": "safe name",
    "# Zep API 需要 Field 的 description，这是必需的": "                # the Zep API requires the Field description",
    "类型注解": "type annotation",
    "# 动态创建类": "            # create the class dynamically",
    "# 动态创建边类型": "        # create edge types dynamically",
    "# 创建属性字典和类型注解": "            # attrs dict and type annotations",
    "# 边属性用str类型": "edge attributes use str",
    "# 构建source_targets": "        # build source_targets",
    "# 调用Zep API设置本体": "        # set the ontology through the Zep API",
    "等待所有 episode 处理完成（通过查询每个 episode 的 processed 状态）": '        """Wait for all episodes to process (poll each episode processed flag)."""',
    "# 检查每个 episode 的处理状态": "            # check each episode's processed status",
    "每3秒检查一次": "poll every 3s",
    "获取图谱信息": '        """Fetch graph info."""',
    "# 获取节点（分页）": "        # nodes (paginated)",
    "# 获取边（分页）": "        # edges (paginated)",
    "# 统计实体类型": "        # count entity types",
    "获取完整图谱数据（包含详细信息）": "        Get full graph data (with details).",
    "包含nodes和edges的字典，包括时间信息、属性等详细数据": "            Dict with nodes and edges incl. timestamps, attributes, etc.",
    "# 创建节点映射用于获取节点名称": "        # node map for name lookups",
    "# 获取创建时间": "            # created at",
    "# 获取时间信息": "            # time info",
    "# 获取 episodes": "            # episodes",
    "# 获取 fact_type": "            # fact_type",
    "删除图谱": '        """Delete the graph."""',
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
print(f"gbuilder: {ok} ok, {miss} miss, {cjk} left")
