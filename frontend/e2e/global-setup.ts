import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

/**
 * E2E 全局准备：清空开发环境缓存。
 *
 * 为什么需要：认证与地址用例每次注册一个随机用户来隔离数据，而
 * `register_ip` 限流为 20/hour。反复跑整套 E2E 会在几轮内耗尽额度，
 * 后续用例一律 429，看起来像功能坏了。
 *
 * 只清 Redis 缓存（开发环境里只有分类/横幅的 60 秒缓存与限流计数），
 * 不动数据库，因此不会破坏演示数据。
 */
const here = path.dirname(fileURLToPath(import.meta.url))
const backendDir = path.resolve(here, '..', '..', 'backend')
const python = path.resolve(here, '..', '..', '.venv', 'Scripts', 'python.exe')

export default function globalSetup(): void {
  try {
    execFileSync(python, ['manage.py', 'shell', '-c', 'from django.core.cache import cache; cache.clear()'], {
      cwd: backendDir,
      stdio: 'pipe',
      timeout: 60_000,
    })
  } catch (error) {
    // 缓存清不掉不该让整个套件失败：可能是 Redis 未启动，这时用例自己会暴露真实问题。
    console.warn('[e2e] 清理缓存失败，限流计数可能残留：', (error as Error).message)
  }
}
