/**
 * 释放开发端口 5173 上残留的 Node/Vite 进程。
 */
import { execSync } from "node:child_process";

const PORT = Number(process.env.DEV_PORT ?? 5173);

function isNodeProcess(pid) {
  if (process.platform === "win32") {
    try {
      const output = execSync(`tasklist /FI "PID eq ${pid}" /FO CSV /NH`, {
        encoding: "utf8",
        stdio: ["pipe", "pipe", "ignore"],
      });
      return /node\.exe/i.test(output);
    } catch {
      return false;
    }
  }

  try {
    const output = execSync(`ps -p ${pid} -o comm=`, {
      encoding: "utf8",
      stdio: ["pipe", "pipe", "ignore"],
    });
    return /node/i.test(output);
  } catch {
    return false;
  }
}

function freePort(port) {
  if (process.platform === "win32") {
    try {
      const output = execSync(`netstat -ano | findstr :${port}`, {
        encoding: "utf8",
        stdio: ["pipe", "pipe", "ignore"],
      });
      const pids = new Set();
      for (const line of output.split("\n")) {
        if (!line.includes("LISTENING")) continue;
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && /^\d+$/.test(pid)) pids.add(pid);
      }
      for (const pid of pids) {
        if (!isNodeProcess(pid)) continue;
        try {
          execSync(`taskkill /PID ${pid} /F`, { stdio: "ignore" });
          console.log(`[free-dev-port] 已释放端口 ${port}（结束 node 进程 ${pid}）`);
        } catch {
          // 进程可能已退出
        }
      }
    } catch {
      // 端口未被占用
    }
    return;
  }

  try {
    const output = execSync(`lsof -ti :${port}`, {
      encoding: "utf8",
      stdio: ["pipe", "pipe", "ignore"],
    });
    for (const pid of output.split("\n").map((s) => s.trim()).filter(Boolean)) {
      if (!isNodeProcess(pid)) continue;
      try {
        execSync(`kill -9 ${pid}`, { stdio: "ignore" });
        console.log(`[free-dev-port] 已释放端口 ${port}（结束 node 进程 ${pid}）`);
      } catch {
        // ignore
      }
    }
  } catch {
    // 端口未被占用
  }
}

freePort(PORT);
