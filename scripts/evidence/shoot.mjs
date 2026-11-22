/**
 * 把 .evidence-html/*.html 截图到 docs/homework/。
 * 用系统 Chrome（channel: "chrome"），不下载 chromium，与 e2e 保持一致。
 *
 * 用法：node scripts/evidence/shoot.mjs
 */
import { createRequire } from 'node:module'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..', '..')

// playwright 装在 frontend/node_modules 下，这里不重复安装。
const { chromium } = require(path.join(root, 'frontend', 'node_modules', 'playwright'))

// 与 build.py 一致：中间 HTML 放在仓库外，避免 SMK-14 扫描生成物。
const srcDir = process.env.EVIDENCE_HTML || path.join(os.tmpdir(), 'galaxy-evidence-html')
const outDir = path.join(root, 'docs', 'homework')
fs.mkdirSync(outDir, { recursive: true })

const PAGES = [
  ['01-迭代计划.html', '作业证据-01-迭代计划更新.png'],
  ['02-交接文档.html', '作业证据-02-handoff交接文档.png'],
  ['03-基线标签.html', '作业证据-03-基线标签.png'],
  ['04-完成度.html', '作业证据-04-完成度自评.png'],
]

const missing = PAGES.filter(([src]) => !fs.existsSync(path.join(srcDir, src)))
if (missing.length) {
  console.error('缺少 HTML，请先运行 python scripts/evidence/build.py：', missing.map(([s]) => s))
  process.exit(1)
}

const browser = await chromium.launch({ channel: 'chrome' })
const page = await browser.newPage({ viewport: { width: 1180, height: 900 }, deviceScaleFactor: 2 })

for (const [src, out] of PAGES) {
  const url = 'file:///' + path.join(srcDir, src).replace(/\\/g, '/')
  await page.goto(url, { waitUntil: 'load' })
  await page.waitForTimeout(300)
  const target = path.join(outDir, out)
  await page.screenshot({ path: target, fullPage: true })
  const size = await page.evaluate(() => ({
    w: document.documentElement.scrollWidth,
    h: document.documentElement.scrollHeight,
  }))
  console.log(`${out}  ${size.w}x${size.h}  ${(fs.statSync(target).size / 1024).toFixed(0)} KB`)
}

await browser.close()
