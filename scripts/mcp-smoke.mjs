#!/usr/bin/env node
/**
 * MCP 功能冒烟：真实调用工具，验证服务不仅"能列出工具"，而且"能干活"。
 * 用法：node scripts/mcp-smoke.mjs
 */
import { spawn } from "node:child_process";

const CASES = [
  {
    name: "redis",
    command: "npx",
    args: ["-y", "@modelcontextprotocol/server-redis", "redis://127.0.0.1:6379"],
    call: (send) => [
      { jsonrpc: "2.0", id: 10, method: "tools/call", params: { name: "set", arguments: { key: "mcp:check", value: "ok-2026" } } },
      { jsonrpc: "2.0", id: 11, method: "tools/call", params: { name: "get", arguments: { key: "mcp:check" } } },
    ],
    expectIds: [10, 11],
    env: {},
  },
  {
    name: "mysql",
    command: "npx",
    args: ["-y", "@benborla29/mcp-server-mysql"],
    call: () => [
      { jsonrpc: "2.0", id: 20, method: "tools/call", params: { name: "mysql_query", arguments: { sql: "SELECT COUNT(*) AS products FROM catalog_product" } } },
    ],
    expectIds: [20],
    env: {
      MYSQL_HOST: "127.0.0.1",
      MYSQL_PORT: "3306",
      MYSQL_USER: "shop",
      MYSQL_PASS: "ShopDb2026!",
      MYSQL_DB: "shop",
    },
  },
  {
    name: "playwright",
    command: "npx",
    args: ["-y", "@playwright/mcp@latest", "--isolated", "--browser", "chrome"],
    call: () => [
      {
        jsonrpc: "2.0",
        id: 30,
        method: "tools/call",
        params: { name: "browser_navigate", arguments: { url: "http://127.0.0.1:5173/" } },
      },
    ],
    expectIds: [30],
    env: {},
  },
];

function runCase(item) {
  return new Promise((resolve) => {
    const child = spawn(item.command, item.args, {
      env: { ...process.env, ...item.env },
      shell: process.platform === "win32",
      windowsHide: true,
    });
    const answers = new Map();
    let stderr = "";
    let buffer = "";

    const timer = setTimeout(() => done(false, "超时"), 90000);

    function done(ok, error) {
      clearTimeout(timer);
      try {
        child.kill();
      } catch {
        /* ignore */
      }
      resolve({ name: item.name, ok, error, answers: [...answers.entries()] });
    }

    const send = (payload) => {
      try {
        child.stdin.write(JSON.stringify(payload) + "\n");
      } catch {
        /* ignore */
      }
    };

    child.on("error", (err) => done(false, String(err.message)));
    child.stderr.on("data", (chunk) => (stderr += chunk.toString()));
    child.stdout.on("data", (chunk) => {
      buffer += chunk.toString();
      let index;
      while ((index = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, index).trim();
        buffer = buffer.slice(index + 1);
        if (!line.startsWith("{")) continue;
        let msg;
        try {
          msg = JSON.parse(line);
        } catch {
          continue;
        }
        if (msg.id === 1 && msg.result) {
          send({ jsonrpc: "2.0", method: "notifications/initialized" });
          for (const payload of item.call(send)) send(payload);
        }
        if (item.expectIds.includes(msg.id)) answers.set(msg.id, msg);
        const missing = item.expectIds.filter((id) => !answers.has(id));
        if (missing.length === 0) done(true, "");
      }
    });
    child.on("exit", (code) => {
      const missing = item.expectIds.filter((id) => !answers.has(id));
      if (missing.length) done(false, `进程退出 code=${code} ${stderr.split("\n")[0] ?? ""}`);
    });

    send({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "mcp-smoke", version: "1.0.0" },
      },
    });
  });
}

let failed = 0;
for (const item of CASES) {
  const result = await runCase(item);
  if (!result.ok) failed += 1;
  console.log(`\n=== ${result.name}: ${result.ok ? "调用成功" : "调用失败 " + result.error} ===`);
  for (const [id, msg] of result.answers) {
    const content = msg.result?.content ?? [];
    const text = content.map((part) => part.text ?? JSON.stringify(part)).join(" ");
    console.log(`id=${id} isError=${msg.result?.isError ?? false} -> ${text.slice(0, 300)}`);
  }
}
process.exit(failed ? 1 : 0);
