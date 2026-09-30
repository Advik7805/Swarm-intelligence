#!/usr/bin/env python3
"""One-shot English sweep for backend/app/services/simulation_manager.py."""
import re

P = "backend/app/services/simulation_manager.py"
src = open(P, encoding="utf-8").read()

M = {
    "OASIS模拟管理器": "OASIS simulation manager",
    "管理Twitter和Reddit双平台并行模拟": "Manages parallel Twitter/Reddit dual-platform simulations.",
    "使用预设脚本 + LLM智能生成配置参数": "Uses preset scripts plus LLM-generated config parameters.",
    "模拟状态": "Simulation status",
    "模拟被手动停止": "simulation stopped manually",
    "模拟自然完成": "simulation finished naturally",
    "平台类型": "Platform type",
    "# 平台启用状态": "    # platform enablement",
    "# 状态": "    # status",
    "# 准备阶段数据": "    # prepare-stage data",
    "# 配置生成信息": "    # config generation info",
    "# 运行时数据": "    # runtime data",
    "# 时间戳": "    # timestamps",
    "# 错误信息": "    # error info",
    "完整状态字典（内部使用）": "        Full state dict (internal use).",
    "根据启用状态返回默认平台": "        Default platform based on enablement.",
    "两者都启用时保持原默认": "keep the original default when both are enabled",
    "简化状态字典（API返回使用）": "        Slim state dict (API responses).",
    "模拟管理器": "    Simulation manager.",
    "核心功能：": "    Core responsibilities:",
    "从Zep图谱读取实体并过滤": "    1. Read and filter entities from the Zep graph",
    "生成OASIS Agent Profile": "    2. Generate OASIS agent profiles",
    "使用LLM智能生成模拟配置参数": "    3. Generate simulation config parameters with the LLM",
    "准备预设脚本所需的所有文件": "    4. Prepare every file the preset scripts need",
    "# 模拟数据存储目录": "    # simulation data directory",
    "# 确保目录存在": "        # make sure the directory exists",
    "# 内存中的模拟状态缓存": "        # in-memory simulation state cache",
    "获取模拟数据目录": "        Get the simulation data directory.",
    "保存模拟状态到文件": "        Save the simulation state to file.",
    "从文件加载模拟状态": "        Load the simulation state from file.",
    "创建新的模拟": "        Create a new simulation.",
    "project_id: 项目ID": "            project_id: project id",
    "graph_id: Zep图谱ID": "            graph_id: Zep graph id",
    "enable_twitter: 是否启用Twitter模拟": "            enable_twitter: run the Twitter simulation?",
    "enable_reddit: 是否启用Reddit模拟": "            enable_reddit: run the Reddit simulation?",
    "创建模拟: {simulation_id}, project={project_id}, graph={graph_id}": "Simulation created: {simulation_id}, project={project_id}, graph={graph_id}",
    "准备模拟环境（全程自动化）": "        Prepare the simulation environment (fully automated).",
    "步骤：": "        Steps:",
    "从Zep图谱读取并过滤实体": "        1. Read and filter entities from the Zep graph",
    "为每个实体生成OASIS Agent Profile（可选LLM增强，支持并行）": "        2. Generate an OASIS profile per entity (optional LLM boost, parallel)",
    "使用LLM智能生成模拟配置参数（时间、活跃度、发言频率等）": "        3. Generate simulation config with the LLM (timing, activity, posting rates, ...)",
    "保存配置文件和Profile文件": "        4. Save the config and profile files",
    "复制预设脚本到模拟目录": "        5. Copy the preset scripts into the simulation directory",
    "simulation_id: 模拟ID": "            simulation_id: simulation id",
    "simulation_requirement: 模拟需求描述（用于LLM生成配置）": "            simulation_requirement: requirement text (drives LLM config generation)",
    "document_text: 原始文档内容（用于LLM理解背景）": "            document_text: source document (gives the LLM background)",
    "defined_entity_types: 预定义的实体类型（可选）": "            defined_entity_types: predefined entity types (optional)",
    "use_llm_for_profiles: 是否使用LLM生成详细人设": "            use_llm_for_profiles: use the LLM for detailed personas?",
    "progress_callback: 进度回调函数 (stage, progress, message)": "            progress_callback: progress callback (stage, progress, message)",
    "parallel_profile_count: 并行生成人设的数量，默认3": "            parallel_profile_count: personas generated in parallel, default 3",
    "模拟不存在: {simulation_id}": "Simulation not found: {simulation_id}",
    "阶段1: 读取并过滤实体": "stage 1: read and filter entities",
    "没有找到符合条件的实体，请检查图谱是否正确构建": "No matching entities found; check that the graph was built correctly",
    "阶段2: 生成Agent Profile": "stage 2: generate agent profiles",
    "# 传入graph_id以启用Zep检索功能，获取更丰富的上下文": "            # pass graph_id to enable Zep retrieval for richer context",
    "# 设置实时保存的文件路径（优先使用 Reddit JSON 格式）": "            # realtime output path (prefers the Reddit JSON format)",
    "传入graph_id用于Zep检索": "graph_id for Zep retrieval",
    "并行生成数量": "parallel generation count",
    "实时保存路径": "realtime output path",
    "输出格式": "output format",
    "# 保存Profile文件（注意：Twitter使用CSV格式，Reddit使用JSON格式）": "            # save profile files (Twitter uses CSV; Reddit uses JSON)",
    "# Reddit 已经在生成过程中实时保存了，这里再保存一次确保完整性": "            # Reddit was saved in real time during generation; save once more for safety",
    "# Twitter使用CSV格式！这是OASIS的要求": "                # Twitter requires CSV - an OASIS constraint",
    "阶段3: LLM智能生成模拟配置": "stage 3: LLM-generated simulation config",
    "# 保存配置文件": "            # save the config file",
    "# 注意：运行脚本保留在 backend/scripts/ 目录，不再复制到模拟目录": "        # note: runner scripts stay in backend/scripts/ and are no longer copied",
    "# 启动模拟时，simulation_runner 会从 scripts/ 目录运行脚本": "        # at launch simulation_runner executes them from the scripts/ directory",
    "# 更新状态": "        # update state",
    "模拟准备完成: {simulation_id}, ": "Simulation prepared: {simulation_id}, ",
    "模拟准备失败: {simulation_id}, error={str(e)}": "Simulation preparation failed: {simulation_id}, error={str(e)}",
    "获取模拟状态": "        Get the simulation status.",
    "列出所有模拟": "        List all simulations.",
    "# 跳过隐藏文件（如 .DS_Store）和非目录文件": "                # skip hidden files (.DS_Store) and non-directories",
    "获取模拟的Agent Profile": "        Get a simulation's agent profiles.",
    "不支持的平台: {platform}": "Unsupported platform: {platform}",
    "获取模拟配置": "        Get the simulation config.",
    "获取运行说明": "        Get run instructions.",
    "激活conda环境: conda activate HiveMind\\n": "1. Activate the conda env: conda activate HiveMind\\n",
    "运行模拟 (脚本位于 {scripts_dir}):\\n": "2. Run the simulation (scripts in {scripts_dir}):\\n",
    "单独运行Twitter: python {scripts_dir}/run_twitter_simulation.py --config {config_path}\\n": "   - Twitter only: python {scripts_dir}/run_twitter_simulation.py --config {config_path}\\n",
    "单独运行Reddit: python {scripts_dir}/run_reddit_simulation.py --config {config_path}\\n": "   - Reddit only: python {scripts_dir}/run_reddit_simulation.py --config {config_path}\\n",
    "并行运行双平台: python {scripts_dir}/run_parallel_simulation.py --config {config_path}": "   - Both in parallel: python {scripts_dir}/run_parallel_simulation.py --config {config_path}",
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
print(f"sim_manager: {ok} ok, {miss} miss, {cjk} left")
