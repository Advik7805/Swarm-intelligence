#!/usr/bin/env python3
"""English sweeps for utils: retry.py, logger.py, file_parser.py."""
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


sweep("backend/app/utils/retry.py", {
    "API调用重试机制": "API call retry helpers",
    "用于处理LLM等外部API调用的重试逻辑": "Retry logic for external API calls such as the LLM.",
    "带指数退避的重试装饰器": "    Retry decorator with exponential backoff.",
    "max_retries: 最大重试次数": "        max_retries: max attempts",
    "initial_delay: 初始延迟（秒）": "        initial_delay: first delay (seconds)",
    "max_delay: 最大延迟（秒）": "        max_delay: delay cap (seconds)",
    "backoff_factor: 退避因子": "        backoff_factor: backoff multiplier",
    "jitter: 是否添加随机抖动": "        jitter: add random jitter?",
    "exceptions: 需要重试的异常类型": "        exceptions: exception types worth retrying",
    "on_retry: 重试时的回调函数 (exception, retry_count)": "        on_retry: retry callback (exception, retry_count)",
    "函数 {func.__name__} 在 {max_retries} 次重试后仍失败: {str(e)}": "Function {func.__name__} still failed after {max_retries} retries: {str(e)}",
    "异步函数 {func.__name__} 在 {max_retries} 次重试后仍失败: {str(e)}": "Async function {func.__name__} still failed after {max_retries} retries: {str(e)}",
    "API调用在 {self.max_retries} 次重试后仍失败: {str(e)}": "API call still failed after {self.max_retries} retries: {str(e)}",
    "# 计算延迟": "                    # compute the delay",
    "函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {str(e)}, ": "Function {func.__name__} attempt {attempt + 1} failed: {str(e)}, ",
    "异步函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {str(e)}, ": "Async function {func.__name__} attempt {attempt + 1} failed: {str(e)}, ",
    "API调用第 {attempt + 1} 次尝试失败: {str(e)}, ": "API call attempt {attempt + 1} failed: {str(e)}, ",
    "秒后重试...": "s; retrying...",
    "异步版本的重试装饰器": "    Async variant of the retry decorator.",
    "可重试的API客户端封装": "    Retryable API client wrapper.",
    "执行函数调用并在失败时重试": "        Run a call and retry on failure.",
    "func: 要调用的函数": "            func: function to call",
    "*args: 函数参数": "            *args: positional args",
    "**kwargs: 函数关键字参数": "            **kwargs: keyword args",
    "函数返回值": "            The function return value.",
    "批量调用并对每个失败项单独重试": "        Process a batch, retrying each failed item individually.",
    "items: 要处理的项目列表": "            items: items to process",
    "process_func: 处理函数，接收单个item作为参数": "            process_func: handler taking a single item",
    "continue_on_failure: 单项失败后是否继续处理其他项": "            continue_on_failure: keep going after one item fails?",
    "(成功结果列表, 失败项列表)": "            (successful results, failed items)",
    "处理第 {idx + 1} 项失败: {str(e)}": "Failed to process item {idx + 1}: {str(e)}",
}, "retry.py")

sweep("backend/app/utils/logger.py", {
    "日志配置模块": "Logging configuration",
    "提供统一的日志管理，同时输出到控制台和文件": "Unified logging to both console and file.",
    "确保 stdout/stderr 使用 UTF-8 编码": "    Force UTF-8 on stdout/stderr.",
    "解决 Windows 控制台中文乱码问题": "    Avoids garbled CJK text on Windows consoles.",
    "# Windows 下重新配置标准输出为 UTF-8": "        # reconfigure stdout to UTF-8 on Windows",
    "# 日志目录": "# log directory",
    "设置日志器": "    Configure a logger.",
    "name: 日志器名称": "        name: logger name",
    "level: 日志级别": "        level: log level",
    "配置好的日志器": "        The configured logger.",
    "# 确保日志目录存在": "    # make sure the log directory exists",
    "# 创建日志器": "    # create the logger",
    "# 阻止日志向上传播到根 logger，避免重复输出": "    # stop propagation to the root logger (no duplicate lines)",
    "# 如果已经有处理器，不重复添加": "    # do not add handlers twice",
    "# 日志格式": "    # log format",
    "# 1. 文件处理器 - 详细日志（按日期命名，带轮转）": "    # 1. file handler - detailed log (dated name, rotated)",
    "# 2. 控制台处理器 - 简洁日志（INFO及以上）": "    # 2. console handler - concise log (INFO and above)",
    "# 确保 Windows 下使用 UTF-8 编码，避免中文乱码": "    # UTF-8 on Windows to avoid garbled CJK",
    "# 添加处理器": "    # attach handlers",
    "获取日志器（如果不存在则创建）": "    Get a logger (created on first use).",
    "日志器实例": "        The logger instance.",
    "# 创建默认日志器": "# default logger",
    "# 便捷方法": "# convenience helpers",
}, "logger.py")

sweep("backend/app/utils/file_parser.py", {
    "文件解析工具": "File parsing utilities",
    "支持PDF、Markdown、TXT文件的文本提取": "Extracts text from PDF, Markdown, and TXT files.",
    "读取文本文件，UTF-8失败时自动探测编码。": "    Read a text file, auto-detecting the encoding if UTF-8 fails.",
    "采用多级回退策略：": "    Fallback chain:",
    "首先尝试 UTF-8 解码": "    1. try UTF-8 decoding",
    "使用 charset_normalizer 检测编码": "    2. detect the encoding with charset_normalizer",
    "回退到 chardet 检测编码": "    3. fall back to chardet",
    "最终使用 UTF-8 + errors='replace' 兜底": "    4. last resort: UTF-8 + errors='replace'",
    "file_path: 文件路径": "        file_path: file path",
    "解码后的文本内容": "        The decoded text.",
    "# 首先尝试 UTF-8": "    # try UTF-8 first",
    "# 尝试使用 charset_normalizer 检测编码": "    # try charset_normalizer detection",
    "# 回退到 chardet": "    # fall back to chardet",
    "# 最终兜底：使用 UTF-8 + replace": "    # last resort: UTF-8 + replace",
    "文件解析器": '    """File parser."""',
    "检查文件是否为支持的格式": "        Check whether the file format is supported.",
    "如果文件格式受支持则返回 True": "        True when the format is supported.",
    "从文件中提取文本": "        Extract text from a file.",
    "提取的文本内容": "        The extracted text.",
    "文件不存在: {file_path}": "File not found: {file_path}",
    "不支持的文件格式: {suffix}": "Unsupported file format: {suffix}",
    "无法处理的文件格式: {suffix}": "Unhandled file format: {suffix}",
    "从PDF提取文本": '        """Extract text from a PDF."""',
}, "file_parser.py")
