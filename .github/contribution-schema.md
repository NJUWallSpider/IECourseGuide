# IE 课程指南 · 共同完善投稿协议（v1）

本文件是「站内投稿入口」的实现契约，前端页面、投稿解析脚本、GitHub Actions 工作流都必须严格遵守。
**任何一方修改本协议，都必须同步修改另外两处。**

## 1. 总体流程（无 fork、无本地环境）

```
贡献者（浏览器）                        维护者（GitHub）                     机器人（Actions）
─────────────────                    ─────────────────                   ─────────────────
打开站点「提交修改」页
填写表单（类型 / 课程 / 标题 / 正文 / 链接）
点击「生成并提交」
   └─> 打开 GitHub 新建 Issue 页（正文已预填）
       拖入附件（GitHub 自动上传）
       点击 Submit new issue
                                        ──> 收到 Issue
                                            看机器人贴出的「变更预览」diff
                                            评论 /批准 或 加 label
                                                                    ──> 校验 → 预览
                                                                    ──> 校验通过后自动改仓库并提交 main
                                        <── 回帖「已收录」并关闭 Issue
站点自动重新构建 → 页面出现新内容
```

- 贡献者只需要一个 GitHub 账号，**不需要 fork、不需要装环境、不需要懂 git**。
- 维护者只审核 Issue 内容（预览 diff），批准后机器人直接改仓库（若 main 受保护则自动改走 PR）。
- 附件只接受 GitHub 自己上传的 `user-attachments` 链接（拖拽上传产生），单个 ≤ 25 MB。

## 2. Issue 正文格式（前端必须生成，解析器必须容忍）

````markdown
## 投稿类型
补充资料

## 课程 / 页面
运筹学Ⅰ（专业核心课/运筹学Ⅰ/index.md）

## 标题
2024 秋期末试卷

## 说明
（贡献者填写的说明，可空）

## 附件
<!-- 请把文件直接拖拽到本行下方（GitHub 会自动上传），一个文件一行。单个文件不超过 25MB。 -->
<!-- ie-attachments -->

## 链接
- https://example.com

<!-- ie-contribution:v1
{
  "version": 1,
  "kind": "material",
  "target": "专业核心课/运筹学Ⅰ/index.md",
  "course": "运筹学Ⅰ",
  "category": "",
  "title": "2024 秋期末试卷",
  "display_name": "2024 秋期末试卷",
  "section": "",
  "notes": "",
  "links": ["https://example.com"],
  "content": "",
  "replacements": []
}
-->
````

解析规则：

- 以正则 `<!--\s*ie-contribution:v1\s*(\{.*?\})\s*-->`（`re.S`）提取 JSON；**取最后一个匹配**。
- JSON 之后出现的内容忽略；JSON 内允许多余空白。
- 若 Issue 正文没有该标记 → 不是投稿 Issue，所有工作流直接忽略（不评论、不贴标签）。
- 附件 = 正文中所有形如
  `https://github.com/user-attachments/assets/<id>`（图片）、
  `https://github.com/user-attachments/files/<数字 id>/<文件名>`（PDF 等文件，2025 年起 GitHub 使用此格式）、
  `https://github.com/<owner>/<repo>/assets/<id>`（旧格式）
  的链接（按出现顺序，去重）。
  其他域名一律不下载，只在预览里提示「忽略外部链接」。
  注意：GitHub 的附件链接通常包在 `[文件名](链接)` 里，解析时不能把结尾的 `)` 吃进 URL。

## 3. 元数据字段

| 字段 | 类型 | 必填 | 说明 / 校验 |
|---|---|---|---|
| `version` | int | 是 | 必须为 `1` |
| `kind` | enum | 是 | `material` / `append` / `edit` / `new-course` |
| `target` | string | 视 kind | 相对 `IE-wiki/docs/` 的 md 路径，如 `专业核心课/运筹学Ⅰ/index.md`；`new-course` 时为空串。禁止 `..`、绝对路径、反斜杠、URL 编码绕过；必须以 `.md` 结尾且文件存在（`new-course` 除外） |
| `course` | string | 是 | 页面显示名，1–60 字 |
| `category` | string | `new-course` 必填 | `专业核心课` / `专业选修课` / `跨专业课` / `数理基础课` / `必学工具` / `其他` |
| `title` | string | 是 | 1–120 字，作为 Issue 标题与 commit message 的一部分 |
| `display_name` | string | `material` 推荐 | 附件在页面上的显示名，缺省用原文件名 |
| `section` | string | 否 | 目标页面中的二级标题文字（不含 `## `），仅 `append` 使用；找不到则报错 |
| `notes` | string | 否 | 说明文字，≤ 2000 字，仅出现在 Issue 里 |
| `links` | string[] | 否 | 外部资源链接，≤ 10 个，必须 http(s) |
| `content` | string | `append` 必填 | Markdown 正文，≤ 20000 字 |
| `replacements` | object[] | `edit` 必填 | `[{old, new}]`，1–20 组；`old` 长度 ≥ 8 且必须在目标页面中**恰好出现 1 次**，否则整单失败（不做部分修改） |

`material` 至少要有一个附件或一个链接。

## 4. 各类型的落盘规则（`apply_submission.py` 必须实现）

### 4.1 `material`（补充资料 / 上传文件）

1. 附件下载后保存到 `target` 所在目录（如 `IE-wiki/docs/专业核心课/运筹学Ⅰ/`）。
2. 文件名：保留原文件名，清洗 `\/:*?"<>|`、控制字符、首尾空格与点，截断到 80 字符（保留扩展名）；
   若同名文件已存在且内容相同 → 复用；若内容不同 → 追加 `-2`、`-3`…
3. 在页面 `## 补充材料` 小节末尾追加清单行：
   `- [<display_name>](<文件名>)`；链接里的空格编码为 `%20`；外部链接写成 `- [<display_name 或域名>](<url>)`。
   当一次投稿的条目多于一个（多个附件，或附件 + 外部链接）时，附件改用清洗后的文件名、链接用域名，
   避免出现多条同名条目；此时 `display_name` 只作为 Issue 标题/说明的参考。
   `append` / `edit` 类型不处理 `links`，会返回 `LINKS_IGNORED` 警告。
4. `## 补充材料` 不存在时：在文件末尾追加 `\n## 补充材料\n\n` 再写清单。
5. 幂等：已存在完全相同的清单行则不重复添加。

### 4.2 `append`（增补介绍 / 文字内容）

1. `section` 为空：追加到页面末尾（前面补一个空行）。
2. `section` 非空：在目标页面中查找 `## <section>`，把内容插到该小节**最后一个非空行之后**（即下一个 `## ` 标题之前），
   找不到 → 报错并终止。
3. 追加的内容末尾必须有 `<!-- ie-submission:issue-<编号> -->` 标记，重复执行时若标记已存在则跳过（幂等）。
4. 页面末尾追加时，若最后一行不是换行则先补换行。

### 4.3 `edit`（纠错 / 精确修改）

1. 逐个 `replacement`：在目标页面中 `old` 必须**恰好出现 1 次**，替换为 `new`。
2. 任何一组不满足 → 整单失败，不写任何文件，返回结构化错误（含「第几组、未找到/出现多次」）。
3. 每组替换后校验文件仍为 UTF-8 文本。

### 4.4 `new-course`（新增课程页）

1. 新页面路径：`IE-wiki/docs/<category>/<course>/index.md`（`必学工具` 为 `IE-wiki/docs/必学工具/<course>/index.md`）；
   `course` 清洗同上，长度 ≤ 40，不得包含 `/`。
2. 页面内容模板（`content` 非空则填入「课程学习内容」）：

```markdown
---
abbrs:
    - <course>
---

# <course>

## 课程学习内容

<content 或 "（待补充）">

## 任课老师

（待补充）

## 考核标准

（待补充）

## 推荐教材

（待补充）

## 补充材料
```

3. 更新 `IE-wiki/mkdocs.yml` 的 `nav`：在对应分类块内插入 `    - <course>: <category>/<course>/index.md`；
   分类块不存在则在文件末追加新分类；插入后必须用 PyYAML 重新解析通过（失败则回滚并报错）。
4. 已存在同名页面 → 报错。

### 4.5 通用

- 所有文件写入使用 UTF-8（无 BOM），换行保持 LF。
- 任何一步失败 → 不落盘、不提交；由工作流回帖说明原因。
- 提交信息：`content: <title> (#<issue>)`。
- 变更预览（dry-run）必须给出每个文件的 unified diff 或「新增文件」说明，供维护者审核。

## 5. `tools/apply_submission.py` CLI 契约

```bash
python tools/apply_submission.py \
  --repo-root . \
  --issue /tmp/issue.json \        # GitHub Issue JSON（至少含 number/body/title/user.login）
  [--dry-run | --apply] \          # 默认 dry-run
  [--json] \                       # 仅输出 JSON（最后一行），便于 jq 解析
  [--attachments-dir DIR] \        # 测试用：本地附件目录，按 issue 中 URL 顺序配对
  [--token-env GITHUB_TOKEN]       # 下载附件用的 token 环境变量名
```

- 退出码：`0` 成功/预览成功；`2` 校验失败；`3` 落盘失败。
- `--json` 输出结构：

```json
{
  "ok": true,
  "issue": 12,
  "kind": "material",
  "title": "2024 秋期末试卷",
  "target": "专业核心课/运筹学Ⅰ/index.md",
  "changes": [{"path": "IE-wiki/docs/专业核心课/运筹学Ⅰ/index.md", "action": "modify", "diff": "..."}],
  "attachments": [{"url": "https://github.com/user-attachments/assets/...", "filename": "期末试卷.pdf", "bytes": 1234}],
  "commit_message": "content: 2024 秋期末试卷 (#12)",
  "warnings": [],
  "errors": []
}
```

- 失败时：`{"ok": false, "errors": [{"code": "TARGET_NOT_FOUND", "message": "..."}]}`，退出码 2/3。
- 代码错误码至少覆盖：`NO_METADATA`、`BAD_VERSION`、`BAD_KIND`、`BAD_TARGET`、`TARGET_NOT_FOUND`、
  `BAD_SECTION`、`SECTION_NOT_FOUND`、`REPLACEMENT_NOT_FOUND`、`REPLACEMENT_AMBIGUOUS`、
  `EMPTY_MATERIAL`、`BAD_LINK`、`DUPLICATE_PAGE`、`BAD_CATEGORY`、`ATTACHMENT_TOO_LARGE`、
  `ATTACHMENT_FORBIDDEN`、`NAV_UPDATE_FAILED`。

## 6. 工作流契约

### 6.1 `contribution-intake.yml`（Issue 校验 + 预览）

- 触发：`issues: [opened, edited]`（`edited` 只在正文含标记时重新预览）。
- 权限：`contents: read`、`issues: write`。
- 行为：dry-run → 在 Issue 下贴一条评论（含 `<details>` 折叠的变更预览、附件列表、审核命令说明）；
  成功加 `contribution:pending`，失败加 `contribution:invalid` 并说明原因；同一个 Issue 编辑后重跑时**更新已有评论**而不是刷屏。

### 6.2 `contribution-apply.yml`（批准后落库）

- 触发：`issue_comment: [created]`（评论含 `/批准`、`/approve`、`/通过`）或
  `issues: [labeled]`（label 为 `contribution:approved`）。
- 权限：`contents: write`、`issues: write`、`pull-requests: write`。
- 安全：只有 `author_association` ∈ {`OWNER`, `MEMBER`, `COLLABORATOR`} 的用户才能批准/拒绝。
- 行为：`--apply` → `git add -A` → commit（`content: ... (#N)`）→ 推送到 `main`；
  推送被保护规则拒绝时，自动推送分支 `contrib/issue-<N>` 并创建 PR，回帖给出 PR 链接。
- 成功后：评论「已收录 + commit/PR 链接」、关闭 Issue、加 `contribution:applied`、移除 `contribution:pending`。
- 失败：评论错误原因，保留 Issue 打开，加 `contribution:invalid`。
- 拒绝命令 `/拒绝`、`/reject`：评论并关闭，加 `contribution:rejected`。
- 幂等：已存在 `<!-- ie-applied -->` 标记的评论则不再重复执行。

### 6.3 标签

`contribution:pending`（待审核）、`contribution:approved`（已批准，触发落库）、
`contribution:applied`（已收录）、`contribution:invalid`（格式/内容有误）、`contribution:rejected`（已拒绝）。
工作流需在缺失时自动创建标签（`POST /repos/{owner}/{repo}/labels`，已存在则忽略）。

## 7. 站点入口契约

- 全站悬浮按钮「✍️ 投稿 / 纠错」：右下角，点击进入 `提交修改/` 页面；在 `提交修改/` 页隐藏。
- 导航新增 `提交修改: "提交修改/index.md"`（放在「贡献指南」之后）。
- 首页增加一张醒目的卡片/提示，链接到 `提交修改/`。
- 页面内表单生成第 2 节的正文格式；`kind` 四种：`material`/`append`/`edit`/`new-course`，
  中文标签分别为「补充资料」「增补介绍」「纠错 / 修改」「新增课程页」。
- 表单里的「课程 / 页面」下拉数据来自 `IE-wiki/docs/assets/courses.json`（由 `tools/gen_courses.py` 从 `mkdocs.yml` 生成）。
- 提交方式：`window.open` 打开
  `https://github.com/<repo>/issues/new?title=<title>&body=<body>`（正文 URL 编码），
  并提示「附件请拖进 GitHub 编辑框」。`<repo>` 从模板变量 `config.extra.contribution_repo` 注入（默认 `NJUWallSpider/IECourseGuide`）。
- 不引入任何后端、第三方前端依赖；纯原生 HTML/CSS/JS，`<script>` 内联或放 `docs/js/`。
