# 作业证据生成

把仓库里的真实文档与真实 `git` 输出渲染成图片，用于作业上交。**内容不做任何改写**：文档部分由 `markdown` 从源文件直接转 HTML，git 部分由脚本现场执行命令取输出。

## 产物

| 文件 | 对应作业要求 |
| --- | --- |
| `docs/homework/作业证据-01-迭代计划更新.png` | 迭代计划的更新截图 |
| `docs/homework/作业证据-02-handoff交接文档.png` | handoff 生成的截图 |
| `docs/homework/作业证据-03-基线标签.png` | 每迭代基线的标签截图 |
| `docs/homework/作业证据-04-完成度自评.png` | 迭代闭合状态（如实统计） |

第 4 张不是作业要求的，是用来核对前 3 张是否足以支撑「两个以上完整迭代」这个结论。

## 重新生成

```powershell
# 1 安装渲染依赖到仓库外（SMK-14 会扫描仓库内 .py，第三方库会误判超限）
python -m pip install --target "$env:TEMP\galaxy-evidence-deps" markdown

# 2 生成 HTML（输出到 $env:TEMP\galaxy-evidence-html）
.\.venv\Scripts\python.exe scripts\evidence\build.py

# 3 截图到 docs/homework/（用系统 Chrome，不下载 chromium）
node scripts\evidence\shoot.mjs
```

## 注意

- 截图是**全页长图**（1180 宽，最高约 4100 px），提交前确认目标平台不会压缩到看不清。
- `04-完成度.html` 的迭代统计由 `迭代计划文档.md` §15 台账**实时解析**得出，不是写死的数字；台账改了，图跟着变。
- 第 3 张的 `git describe` 含当前提交数，随着后续提交会变化；基线一旦新增标签，需重新生成。
