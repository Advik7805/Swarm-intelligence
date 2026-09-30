#!/usr/bin/env python3
"""One-shot English sweep for backend/app/services/zep_entity_reader.py."""
import re

P = "backend/app/services/zep_entity_reader.py"
src = open(P, encoding="utf-8").read()

M = {
    "Zep实体读取与过滤服务": "Zep entity read-and-filter service",
    "从Zep图谱中读取节点，筛选出符合预定义实体类型的节点": "Reads nodes from the Zep graph and keeps those matching predefined entity types.",
    "# 用于泛型返回类型": "# for generic return types",
    "实体节点数据结构": "Entity node data structure.",
    "# 相关的边信息": "    # related edge info",
    "# 相关的其他节点信息": "    # related other-node info",
    "获取实体类型（排除默认的Entity标签）": "        Entity types (the default Entity label excluded).",
    "过滤后的实体集合": "A filtered entity collection.",
    "Zep实体读取与过滤服务": "    Zep entity read-and-filter service.",
    "主要功能：": "    Main functions:",
    "从Zep图谱读取所有节点": "    1. Read every node in the Zep graph",
    "筛选出符合预定义实体类型的节点（Labels不只是Entity的节点）": "    2. Keep nodes matching predefined entity types (labels beyond Entity)",
    "获取每个实体的相关边和关联节点信息": "    3. Fetch each entity's related edges and neighbor nodes",
    "ZEP_API_KEY 未配置": "ZEP_API_KEY not configured",
    "带重试机制的Zep API调用": "        Zep API call with retries.",
    "func: 要执行的函数（无参数的lambda或callable）": "            func: zero-arg lambda/callable to run",
    "operation_name: 操作名称，用于日志": "            operation_name: name used in logs",
    "max_retries: 最大重试次数（默认3次，即最多尝试3次）": "            max_retries: retry cap (default 3 attempts total)",
    "initial_delay: 初始延迟秒数": "            initial_delay: first backoff delay in seconds",
    "API调用结果": "            The API call result.",
    "获取图谱的所有节点（分页获取）": "        Get all nodes of a graph (paginated).",
    "graph_id: 图谱ID": "            graph_id: graph id",
    "节点列表": "            The node list.",
    "获取图谱 {graph_id} 的所有节点...": "Fetching all nodes of graph {graph_id}...",
    "共获取 {len(nodes_data)} 个节点": "Fetched {len(nodes_data)} nodes",
    "获取图谱的所有边（分页获取）": "        Get all edges of a graph (paginated).",
    "边列表": "            The edge list.",
    "获取图谱 {graph_id} 的所有边...": "Fetching all edges of graph {graph_id}...",
    "共获取 {len(edges_data)} 条边": "Fetched {len(edges_data)} edges",
    "获取指定节点的相关边。": "        Get a node's related edges.",
    "Zep Cloud 3.25 的 ``graph.node.get_edges`` 实测只返回节点作为": "        On Zep Cloud 3.25, ``graph.node.get_edges`` empirically returns only",
    "source 的边，尽管文档将其描述为“all edges”。需要完整上下文时必须": "        edges where the node is the source, despite docs saying \"all edges\".",
    "提供 graph_id，以全图分页后同时筛选 incoming 和 outgoing 边。": "        For full context pass graph_id: paginate the whole graph and filter",
    "both incoming and outgoing edges.": "both incoming and outgoing edges.",
    "node_uuid: 节点UUID": "            node_uuid: node UUID",
    "graph_id: 图谱ID；提供时保证返回双向完整关系": "            graph_id: graph id; when given, both directions are returned",
    "# 使用重试机制调用Zep API": "            # call the Zep API with retries",
    "获取节点边(node={node_uuid[:8]}...)": "get node edges(node={node_uuid[:8]}...)",
    "获取节点 {node_uuid} 的边失败: {str(e)}": "Failed to get edges for node {node_uuid}: {str(e)}",
    "筛选出符合预定义实体类型的节点": "        Keep only nodes matching the predefined entity types.",
    "筛选逻辑：": "        Filter logic:",
    "如果节点的Labels只有一个\"Entity\"，说明这个实体不符合我们预定义的类型，跳过": '        - a node whose only label is "Entity" fits no predefined type: skip it',
    "如果节点的Labels包含除\"Entity\"和\"Node\"之外的标签，说明符合预定义类型，保留": '        - labels beyond "Entity"/"Node" mean a predefined type: keep it',
    "defined_entity_types: 预定义的实体类型列表（可选，如果提供则只保留这些类型）": "            defined_entity_types: whitelist of types (optional; only these kept)",
    "enrich_with_edges: 是否获取每个实体的相关边信息": "            enrich_with_edges: also fetch each entity's related edges?",
    "FilteredEntities: 过滤后的实体集合": "            FilteredEntities: the filtered collection",
    "开始筛选图谱 {graph_id} 的实体...": "Filtering entities of graph {graph_id}...",
    "# 获取所有节点": "        # get all nodes",
    "# 获取所有边（用于后续关联查找）": "        # get all edges (for lookups later)",
    "# 构建节点UUID到节点数据的映射": "        # map node UUID -> node data",
    "# 筛选符合条件的实体": "        # filter matching entities",
    "# 筛选逻辑：Labels必须包含除\"Entity\"和\"Node\"之外的标签": '            # logic: labels must include something beyond "Entity"/"Node"',
    "# 只有默认标签，跳过": "                # default label only: skip",
    "# 如果指定了预定义类型，检查是否匹配": "            # with a whitelist, check the type matches",
    "# 创建实体节点对象": "            # build the EntityNode",
    "# 获取相关边和节点": "            # fetch related edges and nodes",
    "# 获取关联节点的基本信息": "                # neighbor node basic info",
    "筛选完成: 总节点 {total_count}, 符合条件 {len(filtered_entities)}, ": "Filtering done: {total_count} nodes total, {len(filtered_entities)} matched, ",
    "实体类型: {entity_types_found}": "entity types: {entity_types_found}",
    "获取单个实体及其完整上下文（边和关联节点，带重试机制）": "        Get one entity with full context (edges + neighbors, with retries).",
    "entity_uuid: 实体UUID": "            entity_uuid: entity UUID",
    "EntityNode或None": "            EntityNode or None",
    "# 使用重试机制获取节点": "            # fetch the node with retries",
    "获取节点详情(uuid={entity_uuid[:8]}...)": "get node detail(uuid={entity_uuid[:8]}...)",
    "# 获取节点的边": "            # fetch the node's edges",
    "# 获取所有节点用于关联查找": "            # fetch all nodes for neighbor lookups",
    "# 处理相关边和节点": "            # process related edges and nodes",
    "# 获取关联节点信息": "                # neighbor node info",
    "获取实体 {entity_uuid} 失败: {str(e)}": "Failed to get entity {entity_uuid}: {str(e)}",
    "获取指定类型的所有实体": "        Get all entities of a given type.",
    "entity_type: 实体类型（如 \"Student\", \"PublicFigure\" 等）": '            entity_type: type name (e.g. "Student", "PublicFigure")',
    "实体列表": "            The entity list.",
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
print(f"zereader: {ok} ok, {miss} miss, {cjk} left")
