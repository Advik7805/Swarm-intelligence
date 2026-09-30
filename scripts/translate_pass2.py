#!/usr/bin/env python3
"""Pass 2: pattern-rule + iterative phrase translation. Drives remaining CJK
in comments/log-strings toward English-only output."""
import os
import re

SKIP_FILES = {
    "locales/zh.json", "locales/languages.json",
    "backend/app/services/analytics/sentiment_engine.py",
}
SKIP_DIRS = {".git", "node_modules", "dist", "__pycache__", "uploads", ".debug", ".venv"}
CJK = re.compile(r"[\u4e00-\u9fff]")

RULES = [
    (r"failed to fetch (.{1,18}?)", r"failed to fetch \1"),
    (r"failed to load (.{1,18}?)", r"failed to load \1"),
    (r"failed to read (.{1,18}?)", r"failed to read \1"),
    (r"failed to write (.{1,18}?)", r"failed to write \1"),
    (r"failed to save (.{1,18}?)", r"failed to save \1"),
    (r"failed to create (.{1,18}?)", r"failed to create \1"),
    (r"failed to update (.{1,18}?)", r"failed to update \1"),
    (r"failed to delete (.{1,18}?)", r"failed to delete \1"),
    (r"failed to start (.{1,18}?)", r"failed to start \1"),
    (r"failed to stop (.{1,18}?)", r"failed to stop \1"),
    (r"failed to connect (.{1,18}?)", r"failed to connect \1"),
    (r"failed to parse (.{1,18}?)", r"failed to parse \1"),
    (r"failed to execute (.{1,18}?)", r"failed to execute \1"),
    (r"failed to upload (.{1,18}?)", r"failed to upload \1"),
    (r"failed to send (.{1,18}?)", r"failed to send \1"),
    (r"failed to call (.{1,18}?)", r"failed to call \1"),
    (r"initialization failed", r"initialization failed"),
    (r"(.{1,10}) polling failed", r"\1 polling failed"),
    (r"check whether (.{1,20}?) ", r"check whether \1 "),
    (r"determine whether (.{1,20}?) ", r"determine whether \1 "),
    (r"isotherwise(存at|成功|complete |enable|has效)", r"is \1"),
    (r"fetch (.{1,16}?) info", r"fetch \1 info"),
    (r"fetch (.{1,16}?) list", r"fetch \1 list"),
    (r"fetch (.{1,16}?) config", r"fetch \1 config"),
    (r"fetch (.{1,16}?) status", r"fetch \1 status"),
    (r"fetch (.{1,16}?) data", r"fetch \1 data"),
    (r"fetch (.{1,16}?) result", r"fetch \1 result"),
    (r"load (.{1,16}?) config", r"load \1 config"),
    (r"read (.{1,16}?) config", r"read \1 config"),
    (r"parse (.{1,16}?) config", r"parse \1 config"),
    (r"generate (.{1,16}?) config", r"generate \1 config"),
    (r"generate (.{1,14}?) report", r"generate \1 report"),
    (r"build (.{1,16}?) request", r"build \1 request"),
    (r"build (.{1,16}?) prompt", r"build \1 prompt"),
    (r"send (.{1,16}?) request", r"send \1 request"),
    (r"handle (.{1,16}?) request", r"handle \1 request"),
    (r"handle (.{1,16}?) response", r"handle \1 response"),
    (r"handle (.{1,16}?) error", r"handle \1 error"),
    (r"log (.{1,16}?)", r"log \1"),
    (r"write (.{1,16}?) log", r"write \1 log"),
    (r"output (.{1,16}?) log", r"output \1 log"),
    (r"monitor (.{1,16}?) status", r"monitor \1 status"),
    (r"monitor (.{1,16}?) progress", r"monitor \1 progress"),
    (r"update (.{1,14}?) status", r"update \1 status"),
    (r"update (.{1,14}?) progress", r"update \1 progress"),
    (r"update (.{1,14}?) round", r"update \1 round"),
    (r"extract (.{1,14}?) entities", r"extract \1 entities"),
    (r"extract (.{1,14}?) relations", r"extract \1 relations"),
    (r"extract (.{1,16}?) seeds", r"extract \1 seeds"),
    (r"inject (.{1,14}?) memory", r"inject \1 memory"),
    (r"build (.{1,14}?) graph", r"build \1 graph"),
    (r"use default (.{1,10})", r"use default \1"),
    (r"use (.{1,12}) config", r"use \1 config"),
    (r"(.{1,14})", r" not supported\1 not supported"),
    (r"only (.{1,14})", r" supportedonly \1 supported"),
    (r"if (.{1,22}) then", r"if \1 then"),
    (r"for (.{1,20})", r"for \1"),
    (r"because (.{1,20})", r"because \1"),
    (r"ensure (.{1,20})", r"ensure \1"),
    (r"guarantee (.{1,20})", r"guarantee \1"),
    (r"avoid (.{1,20})", r"avoid \1"),
    (r"prevent (.{1,20})", r"prevent \1"),
    (r"support (.{1,14}) format", r"support \1 format"),
    (r"wait for (.{1,16}) to complete", r"wait for \1 to complete"),
    (r"wait for (.{1,16}) to return", r"wait for \1 to return"),
    (r"(.{1,18})", r"\1 i in progressn progress"),
    (r"already (.{1,16})", r"already \1"),
    (r"not yet (.{1,16})", r"not yet \1"),
    (r"(.{1,16})", r"\1 not found not found"),
    (r"does not exist", "does not exist"),
    (r"already exists", "already exists"),
    (r"(.{1,8}) completed", r"\1 completed"),
    (r"start (.{1,16})", r"start \1"),
    (r"end (.{1,16})", r"end \1"),
    (r"complete (.{1,16})", r"complete \1"),
    (r"return (.{1,16}) to", r"return \1 to"),
    (r"return (.{1,16})", r"return \1"),
    (r"save (.{1,16}) to", r"save \1 to"),
    (r"convert (.{1,12}) to (.{1,12})", r"convert \1 to \2"),
    (r"add (.{1,12}) to (.{1,12})", r"add \1 to \2"),
    (r"write (.{1,12}) to (.{1,12})", r"write \1 to \2"),
    (r"read (.{1,12})",  from (.{1,12})r"read \2 from \1"),
    (r"implemented via (.{1,14})", r"implemented via \1"),
    (r"built on (.{1,14})", r"built on \1"),
    (r"according to (.{1,16})", r"according to \1"),
    (r"including (.{1,20})", r"including \1"),
    (r"contains (.{1,20})", r"contains \1"),
    (r"e.g. (.{1,20})", r"e.g. \1"),
    (r"note: (.{1,24})", r"note: \1"),
    (r"must (.{1,16})", r"must \1"),
    (r"cannot (.{1,16})", r"cannot \1"),
    (r"can (.{1,16})", r"can \1"),
    (r"need (.{1,16})", r"need \1"),
    (r"no need to (.{1,16})", r"no need to \1"),
    (r"each (.{1,10})", r"each \1"),
    (r"all (.{1,10})", r"all \1"),
    (r"any (.{1,10})", r"any \1"),
    (r"current (.{1,10})", r"current \1"),
    (r"default (.{1,10})", r"default \1"),
    (r"specified (.{1,10})", r"specified \1"),
    (r"optional (.{1,10})", r"optional \1"),
    (r"please (.{1,16})", r"please \1"),
]

PHRASES = {
    "action log": "action log", "action type": "action type", "user info": "user info",
    "username": "username", "user data": "user data", "platform config": "platform config",
    "platform actions": "platform actions", "dual-platform": "dual-platform", "initial posts": "initial posts",
    "initial activation": "initial activation", "initial": "initial", "activation": "activation",
    "orchestration": "orchestration", "narrative direction": "narrative direction", "trending topics": "trending topics",
    "behavior parameters": "behavior parameters", "active timeline": "active timeline", "card header": "card header",
    "time configuration": "time configuration", "basic info": "basic info", "detailed persona": "detailed persona",
    "persona dimensions": "persona dimensions", "simulation instance": "simulation instance", "simulation config": "simulation config",
    "simulation scripts": "simulation scripts", "simulation requirement": "simulation requirement", "simulation rounds": "simulation rounds",
    "config generation": "config generation", "replay": "replay", "divider": "divider",
    "navigation buttons": "navigation buttons", "modal header": "modal header", "modal content": "modal content",
    "file list": "file list", "card container": "card container", "card description": "card description",
    "card footer": "card footer", "title area": "title area", "background decoration": "background decoration",
    "tech grid lines": "tech grid lines", "corner decoration": "corner decoration", "viewfinder": "viewfinder",
    "decorative line": "decorative line", "placeholder": "placeholder", "toolbar": "toolbar",
    "detail panel": "detail panel", "node details": "node details", "edge details": "edge details",
    "self-loop": "self-loop", "view": "view", "layout": "layout", "canvas": "canvas",
    "node": "node", "hover": "hover", "click": "click", "selected": "selected",
    "zoom": "zoom", "drag": "drag", "collapse": "collapse", "expand": "expand",
    "panel": "panel", "sidebar": "sidebar", "top bar": "top bar", "bottom": "bottom",
    "left side": "left side", "right side": "right side", "double click": "double click",
    "real-time refresh": "real-time refresh", "refresh frequency": "refresh frequency", "auto refresh": "auto refresh",
    "fullscreen": "fullscreen", "exit fullscreen": "exit fullscreen", "legend": "legend",
    "color": "color", "size": "size", "position": "position", "opacity": "opacity",
    "animation": "animation", "transition": "transition", "style": "style", "topic": "theme",
    "depth": "depth", "hierarchy": "hierarchy", "structure": "structure",
    "opinion leader": "opinion leader", "official account": "official account",
    "worldview": "worldview", "values": "values", "emotion": "emotion", "attitude": "attitude",
    "stance": "stance", "viewpoint": "viewpoint", "opinion": "opinion", "sentiment": "sentiment",
    "positive": "positive", "negative": "negative", "neutral": "neutral", "polarization": "polarization",
    "spread": "spread", "diffusion": "diffusion", "amplification": "amplification", "buzz": "buzz",
    "inflection point": "inflection point", "peak": "peak", "convergence": "convergence",
    "divergence": "divergence", "stability": "stability", "fluctuation": "fluctuation",
    "scheduling": "scheduling", "scheduler": "scheduler", "launcher": "launcher", "executor": "executor",
    "workflow": "workflow", "pipeline": "pipeline", "pipeline": "pipeline", "channel": "channel",
    "pipe communication": "pipe communication", "semaphore": "semaphore", "mutex": "mutex",
    "deadlock": "deadlock", "race condition": "race condition", "resource": "resource",
    "leak": "leak", "overflow": "overflow", "null value": "null value",
    "undefined": "undefined", "uninitialized": "uninitialized", "invalid": "invalid",
    "valid": "valid", "illegal": "illegal", "expired": "expired",
    "lifecycle": "lifecycle", "scope": "scope", "namespace": "namespace",
    "environment variable": "environment variable", "command line": "command line", "argument parsing": "argument parsing",
    "entry file": "entry file", "entry": "entry", "exit": "exit", "bootstrap": "bootstrap",
    "framework": "framework", "library": "library", "plugin": "plugin", "extension": "extension",
    "middleware": "middleware", "decorator": "decorator", "factory": "factory", "singleton": "singleton",
    "adapter": "adapter", "observer": "observer", "pub-sub": "pub-sub",
    "event-driven": "event-driven", "event loop": "event loop", "event": "event",
    "handler": "handler", "listener": "listener", "filter": "filter",
    "interceptor": "interceptor", "hook function": "hook function", "hook": "hook",
    "priority": "priority", "weight config": "weight config", "quota": "quota",
    "rate limit": "rate limit", "circuit breaker": "circuit breaker", "fallback": "fallback",
    "fallback": "fallback", "fault tolerance": "fault tolerance", "robustness": "robustness",
    "idempotent": "idempotent", "atomicity": "atomicity", "consistency": "consistency",
    "integrity": "integrity", "availability": "availability", "scalability": "scalability",
    "maintainability": "maintainability", "readability": "readability", "bottleneck": "bottleneck",
    "throughput": "throughput", "latency": "latency", "response time": "response time",
    "concurrency": "concurrency", "connection pool": "connection pool", "thread pool": "thread pool",
    "process pool": "process pool", "buffer": "buffer", "warm-up": "warm-up",
    "cold start": "cold start", "hot reload": "hot reload", "canary": "canary",
    "rollback": "rollback", "migration": "migration", "upgrade": "upgrade",
    "compatible": "compatible", "incompatible": "incompatible", "deprecated": "deprecated",
    "obsolete": "obsolete", "experimental": "experimental", "production": "production",
    "development": "development", "staging": "staging", "sandbox": "sandbox",
    "isolation": "isolation", "access control": "access control", "allowlist": "allowlist",
    "blocklist": "blocklist", "audit": "audit", "tracing": "tracing",
    "instrumentation": "instrumentation", "sampling": "sampling", "report": "report",
    "collect": "collect", "aggregate": "aggregate", "aggregate stats": "aggregate stats",
    "analysis report": "analysis report", "visualization": "visualization", "chart": "chart",
    "dashboard": "dashboard", "monitoring panel": "monitoring panel", "alert": "alert",
    "message queue": "message queue", "persistence": "persistence", "serialization": "serialization",
    "deserialization": "deserialization", "compression": "compression", "decompression": "decompression",
    "sharding": "sharding", "replica": "replica", "primary": "primary", "replica node": "replica node",
    "election": "election", "heartbeat": "heartbeat", "timeout retry": "timeout retry",
    "exponential backoff": "exponential backoff", "jitter": "jitter",
    "liveness probe": "liveness probe", "readiness probe": "readiness probe",
    "graceful shutdown": "graceful shutdown", "graceful exit": "graceful exit", "force kill": "force kill",
    "zombie process": "zombie process", "orphan process": "orphan process", "daemon": "daemon",
    "background process": "background process", "stdout": "stdout", "stderr": "stderr",
    "stdin": "stdin", "redirect": "redirect", "append": "append", "truncate": "truncate",
    "clear": "clear", "binary": "binary", "text": "text", "charset": "charset",
    "mojibake": "mojibake", "newline": "newline", "delimiter": "delimiter",
    "prefix": "prefix", "suffix": "suffix", "template": "template", "placeholder": "placeholder",
    "render": "render", "binding": "binding", "two-way binding": "two-way binding",
    "reactive": "reactive", "component": "component", "child component": "child component",
    "parent component": "parent component", "lifecycle hook": "lifecycle hook",
    "mount": "mount", "uninstalled": "unmount", "destroy": "destroy", "rebuild": "rebuild",
    "state management": "state management", "global state": "global state", "local state": "local state",
    "prop passing": "prop passing", "event passing": "event passing", "slot": "slot",
    "routing": "routing", "route navigation": "route navigation", "navigation guard": "navigation guard",
    "lazy loading": "lazy loading", "preload": "preload", "code splitting": "code splitting",
    "bundle": "bundle", "build tool": "build tool", "dev server": "dev server",
    "proxy forwarding": "proxy forwarding", "cross-origin": "cross-origin",
    "same-origin policy": "same-origin policy", "API docs": "API docs", "please 求头": "request headers",
    "please 求体": "request body", "response headers": "response headers", "response body": "response body",
    "status code": "status code", "authentication": "authentication", "token check": "token check",
    "refresh token": "refresh token", "access token": "access token", "session management": "session management",
    "captcha": "captcha", "privacy policy": "privacy policy", "terms of service": "terms of service",
    "user": "user", "use": "use", "adopt": "adopt", "choose": "choose",
    "enable": "enable", "disable": "disable", "deactivate": "deactivate",
    "access": "access", "information": "information", "message": "message",
    "data": "data", "article": "article", "section": "section", "paragraph": "paragraph",
    "keywords": "keywords", "topic": "topic", "title": "title", "subtitle": "subtitle",
    "author": "author", "reader": "reader", "fans": "fans", "followers": "followers",
    "friends": "friends", "community": "community", "forum": "forum", "website": "website",
    "page": "page", "home page": "home page", "detail page": "detail page",
    "login": "login", "register": "register", "logout": "logout", "account": "account",
    "password": "password", "reject": "reject", "agree": "agree", "accept": "accept",
    "ignore": "ignore", "display": "display", "hide": "hide", "show": "show",
    "screened": "screened", "grouped": "grouped", "merged": "merged", "split": "split",
    "received": "received", "transferred": "transferred", "installed": "installed",
    "uninstalled": "uninstalled", "deployed": "deployed", "released": "released",
    "restarted": "restarted", "fixed": "fixed", "improved": "improved", "reviewed": "reviewed",
    "confirmed": "confirmed", "cancelled": "cancelled", "revoked": "revoked",
    "evaluated": "evaluated", "scored": "scored", "ranked": "ranked", "compared": "compared",
    "selected": "selected", "recommended": "recommended", "suggested": "suggested",
    "reminded": "reminded", "errored": "errored", "fault": "fault", "issue": "issue",
    "risk": "risk", "safety": "safety", "danger": "danger", "threat": "threat",
    "defense": "defense", "protect": "protect", "backup": "backup", "archived": "archived",
    "cleaned": "cleaned", "organized": "organized", "formatted": "formatted",
    "encoded": "encoded", "decoded": "decoded", "encrypted": "encrypted", "decrypted": "decrypted",
    "signed": "signed", "authenticated": "authenticated", "authorized": "authorized",
    "configured": "configured", "set": "set", "adjusted": "adjusted", "calibrated": "calibrated",
    "restricted": "restricted", "allowed": "allowed", "forbidden": "forbidden", "controlled": "controlled",
    "managed": "managed", "maintained": "maintained", "monitored": "monitored", "observed": "observed",
    "detected": "detected", "discovered": "discovered", "recognized": "recognized", "matched": "matched",
    "truncated": "truncated", "concatenated": "concatenated", "mapped": "mapped",
    "associated": "associated", "unbound": "unbound", "attached": "attached", "detached": "detached",
    "excluded": "excluded", "overridden": "overridden", "inherited": "inherited",
    "implemented": "implemented", "defined": "defined", "declared": "declared",
    "imported": "imported", "exported": "exported", "referenced": "referenced",
    "iterated": "iterated", "recursive": "recursive", "traversed": "traversed",
    "reversed": "reversed", "deduplicated": "deduplicated", "transaction": "transaction",
    "commit": "commit", "lock": "lock", "blocked": "blocked", "wakeup": "wakeup",
    "notified": "notified", "listening": "listening", "session": "session",
    "please 求": "request", "response": "response", "timeout": "timeout",
    "reconnect": "reconnect", "disconnected": "disconnected", "online": "online",
    "offline": "offline", "restart service": "restart service",
    "": "", "": "", "is": "is", "at": "at", "has": "has", "and": "and",
    "and": "and", "or": "or", "etc.": "etc.", "in": "in", "on": "on",
    "under": "under", "before": "before", "after": "after", "internal": "internal",
    "external": "external", "when": "when", "first": "first", "then": "then",
    "only then": "only then", "all": "all", "also": "also", "still": "still",
    "and": "and", "but": "but", "while": "while", "and": "and", "i.e.": "i.e.",
    "such as": "such as", "if": "if", "then": "then", "otherwise": "otherwise",
    "due to": "due to", "by": "by", "from": "from", "to": "to", "toward": "toward",
    "for": "for", "by": "by", "": "", "": "", "to": "to", "as": "as",
    "with": "with", "and": "and", "its": "its", "of": "of", "between": "between",
    "each": "each", "each": "each", "some": "some", "this": "this", "this": "this",
    "this": "this", "that": "that", "what": "what", "how": "how",
    "how": "how", "why": "why", "which": "which", "which": "which",
    "": "", "kind of": "kind of", "group": "group", "set": "set", "batch": "batch",
    "copy": "copy", "item": "item", "item": "item", "line": "line", "column": "column",
    "layer": "layer", "level": "level", "degree": "degree", "amount": "amount",
    "value": "value", "number": "number", "code": "code", "table": "table",
    "diagram": "diagram", "shape": "shape", "state": "state", "property": "property",
    "can": "can", "will": "will", "can": "can", "should": "should", "must": "must",
    "need": "need", "want": "want", "already": "already", "not yet": "not yet",
    "no": "no", "not": "not", "not": "not", "non-": "non-", "original": "original",
    "output": "output", "input": "input", "into": "into", "back": "back",
    "one": "one", "two": "two", "three": "three", "four": "four", "five": "five",
    "six": "six", "seven": "seven", "eight": "eight", "nine": "nine", "zero": "zero",
    "ten": "ten", "hundred": "hundred", "thousand": "thousand", "10k": "10k", "100M": "100M",
}

_RULES = [(re.compile(p), r) for p, r in RULES]
_SORTED_PHRASES = sorted(PHRASES.items(), key=lambda kv: -len(kv[0]))
_PAT = re.compile("|".join(re.escape(k) for k, _ in _SORTED_PHRASES))


def translate_text(s: str) -> str:
    prev = None
    cur = s
    for _ in range(5):
        for rx, rep in _RULES:
            cur = rx.sub(rep, cur)
        cur = _PAT.sub(lambda m: PHRASES.get(m.group(0), m.group(0)), cur)
        if cur == prev:
            break
        prev = cur
    return cur


def translate_file(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if not CJK.search(src):
        return 0
    out = []
    for line in src.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        eol = line[len(body):]
        if CJK.search(body):
            out.append(translate_text(body) + eol)
        else:
            out.append(line)
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(out))
    return sum(1 for l in out if CJK.search(l))


def main():
    n_files = left_total = 0
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            p = os.path.normpath(os.path.join(root, fn)).replace("\\", "/")
            if p in SKIP_FILES or p == "./locales/en.json":
                continue
            if fn.endswith((".py", ".js", ".vue", ".yml", ".yaml", ".md", ".txt", ".json", ".html")) \
                    or fn in (".gitignore", ".dockerignore", "Dockerfile"):
                left = translate_file(p)
                if left:
                    n_files += 1
                    left_total += left
                    print(f"  LEFT {left:4d}  {p}")
    print(f"\nfiles with residual CJK: {n_files}, residual lines: {left_total}")


if __name__ == "__main__":
    main()
