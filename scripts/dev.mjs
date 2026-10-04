#!/usr/bin/env node
// Starts the FastAPI backend and Next.js frontend together.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const venvUvicorn = path.join(root, "apps/api/.venv/bin/uvicorn");
const hasVenv = existsSync(venvUvicorn);

const procs = [
  spawn("npm", ["run", "dev"], { cwd: path.join(root, "apps/web"), stdio: "inherit" }),
  hasVenv
    ? spawn(venvUvicorn, ["hivemind.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        { cwd: path.join(root, "apps/api"), stdio: "inherit" })
    : spawn("uvicorn", ["hivemind.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        { cwd: path.join(root, "apps/api"), stdio: "inherit" }),
];

const stop = () => procs.forEach((p) => p.kill("SIGTERM"));
process.on("SIGINT", () => { stop(); process.exit(0); });
process.on("SIGTERM", () => { stop(); process.exit(0); });
procs.forEach((p) => p.on("exit", (code) => { if (code && code !== 0) { stop(); process.exit(code); } }));
