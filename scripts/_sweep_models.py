#!/usr/bin/env python3
"""English sweeps for backend/app/models/project.py and task.py."""
import re


def sweep(path, M, label):
    src = open(path, encoding="utf-8").read()
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
            print(f"MISS {label} {i+1}: {body.strip()[:70]}")
        lines[i] = body + "\n"
    open(path, "w", encoding="utf-8").write("".join(lines))
    cjk = sum(1 for l in lines if re.search(r"[\u4e00-\u9fff]", l))
    print(f"{label}: {ok} ok, {miss} miss, {cjk} left")


sweep("backend/app/models/project.py", {
    "项目上下文管理": "Project context management",
    "用于在服务端持久化项目状态，避免前端在接口间传递大量数据": "Persists project state server-side so the frontend does not pass large payloads between endpoints.",
    "项目状态": "Project status",
    "刚创建，文件已上传": "just created; files uploaded",
    "本体已生成": "ontology generated",
    "图谱构建中": "graph building",
    "图谱构建完成": "graph completed",
    "失败": "failed",
    "项目数据模型": "Project data model.",
    "# 文件信息": "    # file info",
    "# 本体信息（接口1生成后填充）": "    # ontology info (filled by endpoint 1)",
    "# 图谱信息（接口2完成后填充）": "    # graph info (filled by endpoint 2)",
    "# 配置": "    # config",
    "# 错误信息": "    # error info",
    "转换为字典": '        """Convert to a dict."""',
    "从字典创建": '        """Build from a dict."""',
    "项目管理器 - 负责项目的持久化存储和检索": "Project manager - persists and retrieves projects.",
    "# 项目存储根目录": "    # project storage root",
    "确保项目目录存在": '        """Make sure the project directory exists."""',
    "获取项目目录路径": '        """Get the project directory path."""',
    "获取项目元数据文件路径": '        """Get the metadata file path."""',
    "获取项目文件存储目录": '        """Get the file storage directory."""',
    "获取项目提取文本存储路径": '        """Get the extracted-text storage path."""',
    "创建新项目": "        Create a new project.",
    "name: 项目名称": "            name: project name",
    "新创建的Project对象": "            The new Project object.",
    "# 创建项目目录结构": "        # create the directory layout",
    "# 保存项目元数据": "        # save the metadata",
    "保存项目元数据": '        """Save the project metadata."""',
    "获取项目": "        Get a project.",
    "project_id: 项目ID": "            project_id: project id",
    "Project对象，如果不存在返回None": "            The Project object, or None if missing.",
    "列出所有项目": "        List all projects.",
    "limit: 返回数量限制": "            limit: max items to return",
    "项目列表，按创建时间倒序": "            Projects sorted by created_at, newest first.",
    "# 按创建时间倒序排序": "        # sort newest first",
    "删除项目及其所有文件": "        Delete a project and all its files.",
    "是否删除成功": "            Whether the delete succeeded.",
    "保存上传的文件到项目目录": "        Save an uploaded file into the project directory.",
    "file_storage: Flask的FileStorage对象": "            file_storage: a Flask FileStorage object",
    "original_filename: 原始文件名": "            original_filename: original file name",
    "文件信息字典 {filename, path, size}": "            File info dict {filename, path, size}",
    "# 生成安全的文件名": "        # generate a safe file name",
    "# 保存文件": "        # save the file",
    "# 获取文件大小": "        # file size",
    "保存提取的文本": '        """Save the extracted text."""',
    "获取提取的文本": '        """Get the extracted text."""',
    "获取项目的所有文件路径": '        """Get all file paths of a project."""',
}, "project.py")

sweep("backend/app/models/task.py", {
    "任务状态管理": "Task status management",
    "用于跟踪长时间运行的任务（如图谱构建）": "Tracks long-running tasks (e.g. graph builds).",
    "任务状态枚举": "Task status enum",
    "等待中": "waiting",
    "处理中": "processing",
    "已完成": "done",
    "任务数据类": "Task dataclass.",
    "总进度百分比 0-100": "overall progress 0-100",
    "状态消息": "status message",
    "任务结果": "task result",
    "错误信息": "error info",
    "额外元数据": "extra metadata",
    "详细进度信息": "detailed progress",
    "任务管理器": "    Task manager.",
    "线程安全的任务状态管理": "    Thread-safe task status tracking.",
    "单例模式": '        """Singleton access."""',
    "创建新任务": "        Create a new task.",
    "task_type: 任务类型": "            task_type: task type",
    "任务ID": "            The task id.",
    "获取任务": '        """Get a task."""',
    "更新任务状态": "        Update task status.",
    "task_id: 任务ID": "            task_id: task id",
    "status: 新状态": "            status: new status",
    "progress: 进度": "            progress: progress",
    "message: 消息": "            message: message",
    "result: 结果": "            result: result",
    "error: 错误信息": "            error: error info",
    "progress_detail: 详细进度信息": "            progress_detail: detailed progress",
    "标记任务完成": '        """Mark the task completed."""',
    "标记任务失败": '        """Mark the task failed."""',
    "列出任务": '        """List tasks."""',
    "清理旧任务": '        """Clean up old tasks."""',
}, "task.py")
