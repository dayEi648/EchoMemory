/**
 * Tauri beforeDevCommand：释放 5173 上的残留 Vite 进程，再以 strictPort 启动开发服务器。
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

import "./free-dev-port.mjs";

const viteBin = join(frontendRoot, "node_modules", "vite", "bin", "vite.js");
if (!existsSync(viteBin)) {
  console.error("[tauri-before-dev] 未找到 Vite，请先在 apps/frontend 执行 npm install");
  process.exit(1);
}

const child = spawn(process.execPath, [viteBin], {
  cwd: frontendRoot,
  stdio: "inherit",
  env: process.env,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.exit(1);
  }
  process.exit(code ?? 1);
});

child.on("error", (err) => {
  console.error("[tauri-before-dev] 启动 Vite 失败:", err.message);
  process.exit(1);
});
