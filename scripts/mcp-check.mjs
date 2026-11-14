#!/usr/bin/env node
/**
 * MCP 安装检查器：真实发起 JSON-RPC 握手 + tools/list，
 * 用于验证 ~/.cursor/mcp.json 里配置的服务是否可用。
 *
 * 用法：node scripts/mcp-check.mjs [服务名...]
 */
import { spawn } from "node:child_process";

const SERVERS = {
  "windows-cli": {
    command: "npx",
    args: ["-y", "@simonb97/server-win-cli"],
    env: {
      WIN_CLI_ALLOWED_DIRECTORIES: "D:\\myProject,C:\\Users\\zhang",
      WIN_CLI_MAX_COMMAND_TIMEOUT: "60000",
    },
  },
  redis: {
    command: "npx",
    args: ["-y", "@modelcontextprotocol/server-redis", "redis://127.0.0.1:6379"],
    env: {},
  },
  mysql: {
    command: "npx",
    args: ["-y", "@benborla29/mcp-server-mysql"],
    env: {
      MYSQL_HOST: "127.0.0.1",
      MYSQL_PORT: "3306",
      MYSQL_USER: "shop",
      MYSQL_PASS: "ShopDb2026!",
      MYSQL_DB: "shop",
      ALLOW_INSERT_OPERATION: "true",
      ALLOW_UPDATE_OPERATION: "true",
      ALLOW_DELETE_OPERATION: "false",
    },
  },
  playwright: {
    command: "npx",
    args: ["-y", "@playwright/mcp@latest", "--isolated", "--browser", "chrome"],
    env: {},
  },
  "chrome-devtools": {
    command: "npx",
    args: ["-y", "chrome-devtools-mcp@latest", "--isolated"],
    env: {},
  },
  godot: {
    command: "npx",
    args: ["-y", "@coding-solo/godot-mcp"],
    env: {
      GODOT_PATH: "C:\\Program Files\\Godot\\Godot_v4.4-stable_win64.exe",
      DEBUG: "false",
    },
  },
  blender: {
    command: "uvx",
    args: ["mcp-for-blender"],
    env: {},
  },
};

const TIMEOUT_MS = Number(process.env.MCP_CHECK_TIMEOUT ?? 120000);

function handshake(name, spec) {
  return new Promise((resolve) => {
    const started = Date.now();
    const child = spawn(spec.command, spec.args, {
      env: { ...process.env, ...spec.env },
      shell: process.platform === "win32",
      windowsHide: true,
    });

    let buffer = "";
    let tools = null;
    let serverInfo = null;
    let stderr = "";
    let settled = false;

    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      let killed = false;
      try {
        child.kill();
        killed = true;
      } catch {
        /* ignore */
      }
      resolve({
        name,
        ms: Date.now() - started,
        killed,
        stderr: stderr.trim().split("\n").slice(-3).join(" | "),
        ...result,
      });
    };

    const timer = setTimeout(
      () => finish({ ok: false, error: `超时 ${TIMEOUT_MS}ms`, tools }),
      TIMEOUT_MS
    );

    const send = (payload) => {
      try {
        child.stdin.write(JSON.stringify(payload) + "\n");
      } catch {
        /* pipe closed */
      }
    };

    child.on("error", (err) => finish({ ok: false, error: String(err.message) }));

    child.stdout.on("data", (chunk) => {
      buffer += chunk.toString();
      let index;
      while ((index = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, index).trim();
        buffer = buffer.slice(index + 1);
        if (!line.startsWith("{")) continue;
        let message;
        try {
          message = JSON.parse(line);
        } catch {
          continue;
        }
        if (message.id === 1 && message.result) {
          serverInfo = message.result.serverInfo ?? null;
          send({ jsonrpc: "2.0", method: "notifications/initialized" });
          send({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} });
        }
        if (message.id === 2) {
          if (message.result?.tools) {
            tools = message.result.tools;
            finish({ ok: true, tools, serverInfo });
          } else {
            finish({ ok: false, error: JSON.stringify(message.error), tools: [] });
          }
        }
      }
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("exit", (code) => {
      if (!settled) {
        finish({
          ok: false,
          error: `进程退出 code=${code}${stderr ? ` :: ${stderr.split("\n")[0]}` : ""}`,
          tools,
        });
      }
    });

    send({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "mcp-check", version: "1.0.0" },
      },
    });
  });
}

const requested = process.argv.slice(2);
const names = requested.length ? requested : Object.keys(SERVERS);
const results = [];

for (const name of names) {
  const spec = SERVERS[name];
  if (!spec) {
    results.push({ name, ok: false, error: "未在脚本中定义" });
    continue;
  }
  process.stdout.write(`检查 ${name} ... `);
  const result = await handshake(name, spec);
  results.push(result);
  const count = result.tools ? result.tools.length : 0;
  console.log(
    result.ok ? `OK  ${count} 个工具  用时 ${(result.ms / 1000).toFixed(1)}s` : `FAIL ${result.error}`
  );
}

console.log("\n名称 | 结果 | 工具数 | 示例工具");
console.log("--- | --- | --- | ---");
for (const item of results) {
  const count = item.tools ? item.tools.length : 0;
  const sample = (item.tools ?? []).slice(0, 3).map((t) => t.name).join(", ");
  console.log(`${item.name} | ${item.ok ? "可用" : "失败"} | ${count} | ${sample}`);
}

const failed = results.filter((item) => !item.ok);
console.log(`\n合计 ${results.length} 个，成功 ${results.length - failed.length} 个，失败 ${failed.length} 个`);
process.exit(failed.length ? 1 : 0);
