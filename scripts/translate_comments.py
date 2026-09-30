#!/usr/bin/env python3
"""
One-shot sweep: translate Chinese comments/docstrings/log-strings to English
across the HiveMind repo using a curated domain phrase dictionary
(longest-match-first). Only comment text and logger/print message strings
are touched — functional data (lexicons, locales, fixtures) is preserved.

Exclusions (files NEVER modified):
  locales/zh.json, locales/languages.json,
  backend/app/services/analytics/sentiment_engine.py (Chinese lexicon data)
"""
import os
import re

PHRASES = {
    # ---- long, high-frequency full phrases ----
    "use 完整 config文件路径": "use the full config file path",
    "加载item目根目录 .env 文件": "load the .env file from the project root",
    "统onefromitem目根目录 .env 文件加载configured": "load configuration from the project-root .env file",
    "通过check whether forshould actions.jsonl 文件 存at来determine whether 平台 byenable": "determine whether a platform is enabled by checking its actions.jsonl file",
    "通过check whether forshould actions.jsonl 文件 存at来判断平台byenable": "determine enabled platforms via their actions.jsonl files",
    "detected simulation_end event，标记平台alreadycomplete ": "detect the simulation_end event and mark the platform complete",
    "such as果enablediagram谱记忆更新，活动发送toZep": "forward activities to Zep when graph-memory updating is enabled",
    "such as果enablediagram谱记忆更新，活动发送to Zep": "forward activities to Zep when graph-memory updating is enabled",
    "手动停止and自然complete cancanobservedto同oneinto程退output": "manual stop and natural completion can observe the same process exit",
    "serialization终stateand排空更新器，ensure 只hasone路径拥has最终结果": "serialize terminal state and updater drain so only one path owns the final result",
    "all 平台alreadyend ，wait for into程anddiagram谱写input to complete": "all platforms finished — waiting for process exit and graph writes to drain",
    "解决 Windows controlled台in文mojibakeissue：atall importedofbeforeset UTF-8 encoded": "avoid mojibake in Windows consoles: force UTF-8 before any imports",
    "setenvironment variableensure  Python use UTF-8": "ensure Python uses UTF-8 via environment variable",
    "重新configuredstdout流as UTF-8": "reconfigure stdout to UTF-8",
    "添加item目根目录to路径": "add the project root to sys.path",
    "启动服务": "start the service",
    "验证configured": "validate configuration",
    "suppress multiprocessing resource_tracker warnings (from third-party libs like transformers)": "suppress multiprocessing resource_tracker warnings (from third-party libs like transformers)",
    "need atall its他importedofbeforeset": "must be set before all other imports",
    "enableCORS": "enable CORS",
    "setJSONencoded：ensure in文直接display（whilenotis \\uXXXX 格式）": "JSON encoding: emit non-ASCII directly instead of \\uXXXX escapes",
    "Flask >= 2.3 use app.json.ensure_ascii，旧版thisuse JSON_AS_ASCII configured": "Flask >= 2.3 uses app.json.ensure_ascii; older versions use JSON_AS_ASCII",
    "register blueprints": "register blueprints",
    "健康检查": "health check",
    "response": "response",
    "alreadyregister模拟into程cleaned函数": "simulation process cleanup handler registered",
    "configuration error": "configuration error",
    "please 检查 .env 文件inconfigured": "please check the .env configuration",
    "启动entry": "entry point",
    "主函数": "main function",
    "模拟complete ": "simulation completed",
    "模拟失败": "simulation failed",
    "分析管线already排队": "analytics pipeline queued",
    "分析管线排队失败": "failed to queue analytics pipeline",
    "monitor thread error": "monitor thread error",
    "failed to read action log": "failed to read action log",
    "Twitter 模拟alreadycomplete ": "Twitter simulation finished",
    "Reddit 模拟alreadycomplete ": "Reddit simulation finished",
    "轮数alreadytruncate": "round count truncated",
    "创建主日志文件，avoid  stdout/stderr pipelinebuffer满导致into程blocked": "create the main log file to avoid process blocking on full stdout/stderr pipes",
    "终止into程树 (Windows)": "terminate process tree (Windows)",
    "first优雅终止": "try graceful termination first",
    "monitored模拟into程，解析action log": "monitor the simulation process and parse action logs",
    "into程仍at运line": "process still running",
    "读取 Twitter action log": "read Twitter action log",
    "读取 Reddit action log": "read Reddit action log",
    "更新状state": "update state",
    "into程end after，最after读取one次日志": "after the process exits, read any remaining log lines",
    "停止diagram谱记忆failed to update 器": "failed to stop graph memory updater",
    "Zepdiagram谱写inputnot yet完整complete ": "Zep graph writes did not fully drain",
    "平台complete 仅is输input信number。monitored器atinto程退outputand Zep 摄取排空afteronly thenreleased最终状state。": "platform completion is only an input signal; the monitor publishes terminal status after process exit and Zep ingestion drains",
    "平台complete 仅is输input信number。monitored器atinto程退outputand Zep 摄取排空afteronly thenreleased终state。": "platform completion is only an input signal; the monitor publishes terminal status after process exit and Zep ingestion drains",
    "检查isotherwiseall enable平台allalreadycomplete ": "check whether all enabled platforms finished",
    "such as果只运lineone平台，只检查that平台": "single-platform runs only check that platform",
    "such as果运line两平台，need 两allcomplete ": "dual-platform runs require both to finish",
    "update round info (from round_end events)": "update round info (from round_end events)",
    "update each平台独立 roundandwhenbetween": "update per-platform round and clock",
    "总体轮次取两平台最大value": "overall round = max across platforms",
    "总体whenbetween取两平台最大value": "overall clock = max across platforms",
    "处理event类型item目": "handle event-type records",
    "更新轮次": "update round",
    "新日志structure：分平台action log": "new log layout: per-platform action logs",
    "each日免费额degree足够简单use": "the free monthly quota is enough for light usage",
    "each月免费额degreei.e.can支撑简单use": "the free monthly quota is enough for light usage",
    "recommendeduse阿里hundred炼平台qwen-plus模型": "recommended: qwen-plus on Alibaba Bailian",
    "note: 消耗较大，canfirstintoline小于40轮模拟尝试": "consumption is high; start with simulations under 40 rounds",
    "note: such as果notuse 加速 config，env文件in就notwantoutput现under面configureditem": "if not using boost config, keep these keys out of .env entirely",
    "support  OpenAI SDK  format任意 LLM API": "works with any OpenAI SDK-compatible LLM API",
    "environment variable（protect敏感information）": "environment variables (keep secrets out of git)",
    "文档and测试程序": "docs & test scratch programs",
    "on传文件": "uploaded files",
    "data": "data",
    # ---- core vocabulary (longest first will be applied by sorter) ----
    "知识diagram谱": "knowledge graph",
    "群体智can": "swarm intelligence",
    "多智can体": "multi-agent",
    "智can体": "agent",
    "环境搭建": "environment setup",
    "depth互动": "deep interaction",
    "andline模拟": "parallel simulation",
    "dual-platform": "dual-platform",
    "社交媒体": "social media",
    "舆论模拟": "opinion simulation",
    "舆论": "public opinion",
    "模拟": "simulation",
    "推演": "deduction",
    "预测": "prediction",
    "报告": "report",
    "configured": "configuration",
    "initial化": "initialize",
    "initial化": "initialization",
    "文件on传": "file upload",
    "on传": "upload",
    "under载": "download",
    "文档": "document",
    "知识": "knowledge",
    "diagram谱": "graph",
    "构建": "build",
    "构建in": "building",
    "实体": "entity",
    "关系": "relation",
    "关系类型": "relation type",
    "实体类型": "entity type",
    "this体": "ontology",
    "人设": "persona",
    "生成": "generate",
    "生成in": "generating",
    "提取": "extraction",
    "抽取": "extraction",
    "解析": "parse",
    "分析": "analyze",
    "处理": "process",
    "处理in": "processing",
    "校验": "validate",
    "验证": "verify",
    "检查": "check",
    "轮询": "polling",
    "状state": "status",
    "intodegree": "progress",
    "complete ": "complete",
    "alreadycomplete ": "completed",
    "失败": "failure",
    "error": "error",
    "异常": "exception",
    "warning": "warning",
    "成功": "success",
    "timeout": "timeout",
    "重试": "retry",
    "etc.待": "waiting",
    "启动": "start",
    "启动失败": "start failed",
    "停止": "stop",
    "暂停": "pause",
    "恢复": "resume",
    "运line": "running",
    "运linein": "running",
    "执line": "execute",
    "调用": "call",
    "触发": "trigger",
    "back调": "callback",
    "monitored": "monitor",
    "listening": "listen",
    "订阅": "subscribe",
    "released": "publish",
    "读取": "read",
    "写input": "write",
    "保存": "save",
    "加载": "load",
    "加载in": "loading",
    "获取": "fetch",
    "获取失败": "fetch failed",
    "please 求": "request",
    "response": "response",
    "return ": "return",
    "结果": "result",
    "data": "data",
    "datalibrary": "database",
    "缓存": "cache",
    "日志": "log",
    "文件": "file",
    "路径": "path",
    "目录": "directory",
    "参数": "parameter",
    "选item": "option",
    "set": "settings",
    "default ": "default",
    "全局": "global",
    "局部": "local",
    "变amount": "variable",
    "常amount": "constant",
    "类型": "type",
    "格式": "format",
    "encoded": "encoding",
    "decoded": "decode",
    "转换": "convert",
    "清洗": "cleaning",
    "分块": "chunking",
    "切块": "chunking",
    "重叠": "overlap",
    "阈value": "threshold",
    "on限": "upper limit",
    "under限": "lower limit",
    "最大": "max",
    "最小": "min",
    "数amount": "count",
    "总数": "total",
    "索引": "index",
    "columntable": "list",
    "字典": "dict",
    "数group": "array",
    "字符串": "string",
    "数字": "number",
    "布尔": "boolean",
    "for象": "object",
    "实例": "instance",
    "方法": "method",
    "函数": "function",
    "接口": "interface",
    "类": "class",
    "模块": "module",
    "包": "package",
    "依赖": "dependency",
    "版this": "version",
    "更新": "update",
    "删除": "delete",
    "创建": "create",
    "插input": "insert",
    "替换": "replace",
    "matched": "match",
    "过滤": "filter",
    "排序": "sort",
    "搜索": "search",
    "查询": "query",
    "traversed": "iterate",
    "循环": "loop",
    "item件": "condition",
    "分支": "branch",
    "跳过": "skip",
    "继续": "continue",
    "in断": "interrupt",
    "退output": "exit",
    "关闭": "close",
    "打开": "open",
    "连接": "connection",
    "断开": "disconnect",
    "客户端": "client",
    "服务器": "server",
    "服务": "service",
    "端口": "port",
    "地址": "address",
    "密钥": "key",
    "凭证": "credentials",
    "authenticated": "authentication",
    "authorized": "authorization",
    "权限": "permission",
    "safety": "security",
    "encrypted": "encrypt",
    "signed": "signature",
    "令牌": "token",
    "session": "session",
    "user": "user",
    "昵称": "username",
    "头像": "avatar",
    "简介": "bio",
    "详情": "details",
    "标签": "tag",
    "分类": "category",
    "internal容": "content",
    "title": "title",
    "描述": "description",
    "评论": "comment",
    "帖子": "post",
    "点赞": "like",
    "点踩": "dislike",
    "转发": "repost",
    "referenced": "quote",
    "关注": "follow",
    "取关": "unfollow",
    "静音": "mute",
    "热搜": "trending",
    "话题": "topic",
    "热门": "hot",
    "刷新": "refresh",
    "平台": "platform",
    "推特": "Twitter",
    "reddit": "reddit",
    "轮次": "round",
    "轮数": "round count",
    "whenbetween线": "timeline",
    "whenbetween": "time",
    "whenbetween戳": "timestamp",
    "小when": "hour",
    "分钟": "minute",
    "秒": "second",
    "日期": "date",
    "current ": "current",
    "ofbefore": "previous",
    "ofafter": "after",
    "start ": "begin",
    "end ": "end",
    "inbetween": "middle",
    "internal部": "internal",
    "external部": "external",
    "线程": "thread",
    "into程": "process",
    "子into程": "subprocess",
    "队column": "queue",
    "lock": "lock",
    "同步": "sync",
    "异步": "async",
    "and发": "concurrent",
    "串line": "serial",
    "internal存": "memory",
    "存储": "storage",
    "磁盘": "disk",
    "网络": "network",
    "代理": "proxy",
    "加速": "boost",
    "propertycan": "performance",
    "优化": "optimize",
    "调试": "debug",
    "测试": "test",
    "示例": "example",
    "note: ": "note",
    "说明": "notes",
    "描述": "description",
    "摘want": "summary",
    "统计": "statistics",
    "汇总": "summary",
    "历史": "history",
    "记录": "record",
    "字段": "field",
    "属property": "attribute",
    "value": "value",
    "名称": "name",
    "名字": "name",
    "头像": "avatar",
    "职业": "profession",
    "国家": "country",
    "地区": "region",
    "年龄": "age",
    "property别": "gender",
    "property格": "personality",
    "兴趣": "interests",
    "话题偏好": "topic preferences",
    "lineas": "behavior",
    "动作": "action",
    "action type": "action type",
    "活跃": "active",
    "活跃degree": "activity level",
    "权重": "weight",
    "比例": "ratio",
    "概率": "probability",
    "随机": "random",
    "kind of子": "seed",
    "样this": "sample",
    "batchamount": "batch",
    "分页": "pagination",
    "页code": "page number",
    "each页": "per page",
    "排序": "sort",
    "升序": "ascending",
    "降序": "descending",
    "自动": "automatic",
    "手动": "manual",
    "实when": "real-time",
    "定when": "scheduled",
    "周期": "period",
    "between隔": "interval",
    "频率": "frequency",
    "模型": "model",
    "提示词": "prompt",
    "系统提示": "system prompt",
    "onunder文": "context",
    "输input": "input",
    "输output": "output",
    "流式": "streaming",
    "温degree": "temperature",
    "推理": "inference",
    "思考": "thinking",
    "back复": "reply",
    "back答": "answer",
    "for话": "conversation",
    "message": "message",
    "角色": "role",
    "系统": "system",
    "助手": "assistant",
    "工具": "tool",
    "调用工具": "tool call",
    "反思": "reflection",
    "总结": "summarize",
    "翻译": "translate",
    "语言": "language",
    "in文": "Chinese",
    "英文": "English",
    "支持": "support",
    "": "not suppor not supportedted",
    "must ": "must",
    "optional ": "optional",
    "cancan": "possible",
    "such as果": "if",
    "otherwisethen": "otherwise",
    "withand": "and",
    "or者": "or",
    "butis": "but",
    "due toas": "because",
    "所with": "therefore",
    "目before": "currently",
    "already ": "already",
    "not yet ": "not yet",
    "": "currently", in progress
    "刚刚": "just",
    "立i.e.": "immediately",
    "稍after": "later",
    "最after": "finally",
    "首first": "first",
    "its次": "second",
    "e.g. ": "e.g.",
    "etc.etc.": "etc.",
    "左右": "approximately",
    "大约": "approximately",
    "至少": "at least",
    "最多": "at most",
    "超过": "exceed",
    "小于": "less than",
    "大于": "greater than",
    "etc.于": "equals",
    "notetc.于": "not equal",
    "contains ": "contains",
    "notcontains ": "does not contain",
    "属于": "belongs to",
    "forshould": "corresponding",
    "相关": "related",
    "no关": "unrelated",
    "相同": "identical",
    "not同": "different",
    "新": "new",
    "旧": "old",
    "主want": "primary",
    "次want": "secondary",
    "重want": "important",
    "特殊": "special",
    "普通": "normal",
    "常见": "common",
    "罕见": "rare",
    "issue": "issue",
    "originaldue to": "reason",
    "影响": "impact",
    "效果": "effect",
    "结果": "result",
    "目": "purpose",
    "方式": "method",
    "步骤": "step",
    "阶段": "phase",
    "流程": "workflow",
    "逻辑": "logic",
    "规then": "rule",
    "策略": "strategy",
    "方案": "solution",
    "计划": "plan",
    "任务": "task",
    "item目": "project",
    "need求": "requirement",
    "功can": "feature",
    "特property": "characteristic",
    "优点": "advantages",
    "缺点": "disadvantages",
    "restricted": "limitation",
    "约束": "constraint",
    "假设": "assumption",
    "结论": "conclusion",
    "suggested": "suggestion",
    "参考": "reference",
    "来源": "source",
    "目标": "target",
    "for象": "object",
    "主体": "subject",
    "level别": "level",
    "etc.level": "grade",
    "高": "high",
    "低": "low",
    "in": "medium",
    "大": "large",
    "小": "small",
    "多": "many",
    "少": "few",
    "快": "fast",
    "慢": "slow",
    "好": "good",
    "坏": "bad",
    "新": "new",
    "旧": "old",
}

# sort longest-first so specific phrases win over generic words
_SORTED = sorted(PHRASES.items(), key=lambda kv: -len(kv[0]))
_PAT = re.compile("|".join(re.escape(k) for k, _ in _SORTED))

# files never to touch
SKIP_FILES = {
    "locales/zh.json", "locales/languages.json",
    "backend/app/services/analytics/sentiment_engine.py",
}
SKIP_DIRS = {".git", "node_modules", "dist", "__pycache__", "uploads", ".debug", ".venv"}
EXTS = (".py", ".js", ".vue", ".json", ".yml", ".yaml", ".html", ".md", ".txt")


def translate_text(s: str) -> str:
    return _PAT.sub(lambda m: PHRASES.get(m.group(0), m.group(0)), s)


CJK = re.compile(r"[\u4e00-\u9fff]")
PY_COMMENT = re.compile(r"^(\s*)#\s?(.*)$")
INLINE_PY_COMMENT = re.compile(r"^(\s*[^\s#].*?)\s(#\s?)(\S.*)$")
JS_LINE = re.compile(r"^(\s*)//\s?(.*)$")
HTML_COMMENT = re.compile(r"^(\s*)<!--\s?(.*?)\s*-->\s*$")
BLOCKSTAR = re.compile(r"^(\s*\*)\s?(.*)$")


def translate_comment_line(line: str) -> str:
    """Translate a single comment line, preserving its marker/indent."""
    m = PY_COMMENT.match(line)
    if m:
        return f"{m.group(1)}# {translate_text(m.group(2).strip())}".rstrip() + (
            "" if line.endswith("\n") else "")
    m = INLINE_PY_COMMENT.match(line)
    if m and CJK.search(m.group(3)):
        return f"{m.group(1)}  {m.group(2)}{translate_text(m.group(3))}"
    m = JS_LINE.match(line)
    if m:
        return f"{m.group(1)}// {translate_text(m.group(2).strip())}"
    m = HTML_COMMENT.match(line)
    if m:
        return f"{m.group(1)}<!-- {translate_text(m.group(2)).strip()} -->"
    m = BLOCKSTAR.match(line)
    if m:
        return f"{m.group(1)} {translate_text(m.group(2).strip())}"
    return None  # not a recognizable comment


DOCSTRING_RE = re.compile(r'^\s*(?:"""|\'\'\')')


def process_file(path: str) -> tuple[int, int]:
    """Returns (cjk_before, lines_changed)."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if not CJK.search(src):
        return 0, 0

    is_py = path.endswith(".py")
    lines = src.splitlines(keepends=True)
    out = []
    changed = 0
    in_doc = False
    doc_marker = None

    for line in lines:
        body = line.rstrip("\r\n")
        eol = line[len(body):]

        if is_py:
            # docstring state tracking
            stripped = body.strip()
            if in_doc:
                new = translate_comment_line.__class__ and translate_text(body)
                if CJK.search(body):
                    new = translate_text(body)
                    changed += 1
                out.append(new + eol)
                if doc_marker and doc_marker in stripped:
                    in_doc, doc_marker = False, None
                continue
            dm = re.match(r'^\s*(("""|\'\'\')|r?"""|r?\'\'\')', body)
            if dm:
                marker = dm.group(1).replace("r", "")
                rest = body[dm.end():]
                if marker in rest or (stripped.endswith(marker) and len(stripped) > 6):
                    pass  # single-line docstring; fall through to normal handling
                else:
                    in_doc, doc_marker = True, marker
                    if CJK.search(rest):
                        out.append(body[:dm.end()] + translate_text(rest) + eol)
                        changed += 1
                    else:
                        out.append(line)
                    continue

        # plain comment lines
        new = translate_comment_line(body) if CJK.search(body) else None
        if new is not None:
            out.append(new + eol)
            changed += 1
            continue
        # logger / print / raise message strings: translate CJK inside quotes
        if CJK.search(body) and re.search(
                r"(logger|logging|print|raise|error|warning|info|msg|message)", body, re.I):
            def _q_sub(mm):
                inner = mm.group(2)
                if CJK.search(inner):
                    return mm.group(1) + translate_text(inner) + mm.group(1)
                return mm.group(0)
            new = re.sub(r"(['\"])(.*?)\1", _q_sub, body)
            if new != body:
                changed += 1
            out.append(new + eol)
            continue
        out.append(line)

    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(out))
    return sum(1 for l in out if CJK.search(l)), changed


def main():
    total_files = total_changed = total_left = 0
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            p = os.path.normpath(os.path.join(root, fn)).replace("\\", "/")
            if p in SKIP_FILES:
                continue
            if p == "./locales/en.json":
                continue
            if not fn.endswith(EXTS) and fn not in (".gitignore", ".dockerignore", "Dockerfile"):
                continue
            try:
                left, changed = process_file(p)
            except Exception as e:
                print(f"  ERROR {p}: {e}")
                continue
            if changed:
                total_files += 1
                total_changed += changed
                total_left += left
                print(f"  {p}: {changed} lines translated, {left} CJK lines left")
    print(f"\nDONE: {total_files} files, {total_changed} lines translated, {total_left} CJK lines remain")


if __name__ == "__main__":
    main()
