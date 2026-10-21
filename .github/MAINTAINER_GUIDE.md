# 维护者手册 · 共同完善投稿系统

本仓库在原有「邮箱 / Issue / fork+PR」之外，新增了一套 **无需 fork 的站内投稿入口**：
贡献者在网站「提交修改」页填表 → 自动生成结构化的 GitHub Issue → 维护者只审核 Issue 内容 →
机器人校验并给出变更预览 → 维护者评论 `/批准` → 机器人直接改仓库（或自动开 PR）→ 站点自动重新部署。

```
贡献者填表 ──> GitHub Issue（含隐藏的 ie-contribution:v1 元数据）
                     │
                     ├─ 机器人：校验 + 贴「变更预览」+ 打 contribution:pending
                     │
维护者评论 /批准 ────┴─> 机器人：下载附件 → 改 md / 建页面 / 更新 nav → commit → push main
                                     → 复用 site-deploy.yml 重新构建并发布 Pages
                                     → 回帖「已收录」→ 关闭 Issue
```

---

## 一、首次启用清单（只需做一次）

1. **开启 GitHub Pages**
   - 仓库 `Settings → Pages → Build and deployment → Source` 选择 **GitHub Actions**（不要选 "Deploy from a branch"）。
   - 首次推送 `main` 后，`Deploy site` 工作流会自动发布；站点地址形如 `https://<owner>.github.io/IECourseGuide/`。

2. **确认 Actions 权限**
   - `Settings → Actions → General → Workflow permissions` 选 **Read and write permissions**（或保持默认，工作流内已显式声明所需 `permissions`）。
   - 若仓库开启了「Fork pull request workflows」等限制，不影响本方案（投稿走 Issue，不走 fork PR）。

3. **（可选）main 分支保护**
   - 若 `main` 受保护且禁止直推，机器人推送失败时会自动改为推送 `contrib/issue-<N>` 分支并创建 PR，
     Issue 里会给出 PR 链接；此时在 PR 上再点合并即可，合并后站点同样会自动部署。

4. **确认入口指向的仓库**
   - 站点 `IE-wiki/mkdocs.yml` 中 `extra.contribution_repo` 决定「提交」时打开的仓库，默认
     `NJUWallSpider/IECourseGuide`。若你部署的是自己的 fork，改成 `你的用户名/IECourseGuide`，
     并确保该仓库里已有 `.github/workflows/contribution-*.yml`。

5. **标签**：`contribution:pending` / `contribution:approved` / `contribution:applied` /
   `contribution:invalid` / `contribution:rejected` 由工作流在缺失时自动创建，无需手工建。

---

## 二、日常审核流程

1. 收到标题带「投稿」的 Issue 后，机器人会自动贴一条 **变更预览**（折叠的 diff、附件清单、将落库的位置）。
   - 若预览失败（格式错误、目标页面不存在等），机器人会说明原因并打 `contribution:invalid`，可直接回帖告知贡献者修改。
2. 审核内容（说明、附件、将改动的页面）。
3. 批准：
   - 评论 `/批准`（也支持 `/approve`、`/通过`），**或** 给 Issue 加 `contribution:approved` 标签。
   - 仅仓库 `OWNER` / `MEMBER` / `COLLABORATOR` 有效，普通贡献者无法触发。
4. 机器人自动落库：评论「已收录」+ commit 链接，加 `contribution:applied`，关闭 Issue。
   - 站点随后由 `Deploy site` 工作流自动更新（投稿工作流会复用调用部署，无需手动）。
5. 拒绝：评论 `/拒绝`（或 `/reject`），Issue 关闭并标记 `contribution:rejected`。

### 审核要点

- **补充资料（material）**：附件会存进对应课程目录，并在页面 `## 补充材料` 末尾追加清单行。
  确认文件是否与课程相关、文件名是否合适（页面显示名取 `display_name`）。
- **增补介绍（append）**：内容会追加到指定小节末尾（或页面末尾），带 `<!-- ie-submission:issue-N -->` 幂等标记。
- **纠错修改（edit）**：只做「原文 → 新文」的精确替换；`old` 必须在页面中唯一出现，否则整单失败不落库。
  预览 diff 会显示每处替换，务必逐条核对，避免改坏上下文。
- **新增课程页（new-course）**：自动建 `docs/<分类>/<课程>/index.md` 并更新 `mkdocs.yml` 的 `nav`；
  合并前确认分类正确、课程名无歧义。

---

## 三、安全设计（为什么可以放心批准）

- 投稿 Issue 只写入 `IE-wiki/docs/` 与 `IE-wiki/mkdocs.yml`，脚本对路径做严格校验（拒绝 `..`、绝对路径、编码绕过、非 `.md`）。
- 附件只接受 GitHub 自己托管的 `user-attachments` 链接，限制域名、扩展名与 25 MB 大小，其他链接只作为文字链接展示。
- 只有维护者能批准；批准后才落库，落库失败不会产生半成品提交。
- 机器人使用仓库自带 `GITHUB_TOKEN`，权限按工作流最小化声明；不涉及任何外部服务器或第三方服务。
- 所有投稿都留有 Issue 记录，可追溯、可回滚（`git revert` 单个提交即可）。

---

## 四、本地演练（不产生提交）

在仓库根目录执行：

```bash
# 1) 造一个 Issue JSON（可从真实 Issue 用 gh api repos/<owner>/<repo>/issues/<N> 获取）
cat > /tmp/issue.json <<'JSON'
{
  "number": 999,
  "title": "投稿：2024 秋期末试卷",
  "user": {"login": "student"},
  "body": "## 投稿类型\n补充资料\n\n<!-- ie-contribution:v1\n{\"version\":1,\"kind\":\"material\",\"target\":\"专业核心课/运筹学Ⅰ/index.md\",\"course\":\"运筹学Ⅰ\",\"title\":\"2024 秋期末试卷\",\"display_name\":\"2024 秋期末试卷\",\"links\":[],\"content\":\"\",\"replacements\":[]}\n-->\n"
}
JSON

# 2) 只预览、不写盘（附件用本地目录模拟，按正文中出现顺序配对）
python tools/apply_submission.py --repo-root . --issue /tmp/issue.json --attachments-dir /tmp/local-attachments --json

# 3) 真正落库（会改文件；确认后再 git add/commit）
python tools/apply_submission.py --repo-root . --issue /tmp/issue.json --attachments-dir /tmp/local-attachments --apply
```

跑测试：

```bash
python -m pip install pyyaml pytest
python -m pytest tools/tests -q
```

本地预览站点：

```bash
pip install -r IE-wiki/requirements.txt
python tools/gen_courses.py
mkdocs serve -f IE-wiki/mkdocs.yml
```

---

## 五、故障排查

| 现象 | 原因 / 处理 |
|---|---|
| Issue 没有任何机器人回复 | 正文缺少 `<!-- ie-contribution:v1 ... -->` 元数据（例如贡献者手工建的 Issue）。让贡献者从站内入口重新提交 |
| 预览显示「目标页面不存在」 | 课程页被改名/删除，或贡献者选了 `其他页面` 之外的路径；确认后让贡献者改选，或手工把 target 改成现有页面 |
| 批准后提示 push 失败 | main 分支保护；工作流会自动改走 `contrib/issue-N` + PR，去 PR 里合并即可 |
| 站点没更新 | 检查 `Deploy site` 是否成功；确认 Pages Source 是 **GitHub Actions**；机器人提交后是复用部署工作流，不依赖 push 事件 |
| 附件下载失败 | 附件可能被删除/非 GitHub 托管；让贡献者重新在 Issue 编辑框拖拽上传。外部网盘链接只保留为文字链接 |
| 构建失败 | 看 `Deploy site` 日志；常见原因：`mkdocs.yml` nav 引用了不存在的文件、新页面 frontmatter 写错、`requirements.txt` 依赖问题 |
| 想撤回某次投稿 | 在仓库 history 里找到 `content: ... (#N)` 提交，`git revert` 后推送，站点会自动回滚 |

---

## 六、文件地图

| 路径 | 作用 |
|---|---|
| `IE-wiki/docs/提交修改/index.md` | 站内投稿页（表单 + 说明 + FAQ） |
| `IE-wiki/docs/js/contribution-entry.js` | 全站右下角「投稿 / 纠错」悬浮入口 |
| `IE-wiki/docs/assets/courses.json` | 课程目录（由 `tools/gen_courses.py` 从 nav 生成） |
| `IE-wiki/overrides/main.html` | 注入前端配置（仓库地址、站点根路径） |
| `IE-wiki/mkdocs.yml` | 导航新增「提交修改」、`extra_javascript`、`extra.contribution_repo` |
| `tools/submission.py` | Issue 元数据解析、校验、附件提取 |
| `tools/apply_submission.py` | 预览 / 落库 CLI（4 类投稿语义） |
| `tools/tests/` | 投稿系统单元测试 |
| `.github/workflows/contribution-intake.yml` | 新投稿校验 + 预览评论 |
| `.github/workflows/contribution-apply.yml` | 批准后落库 + 提交/PR + 关闭 Issue |
| `.github/workflows/site-deploy.yml` | 构建并发布 GitHub Pages（可被投稿工作流复用） |
| `.github/workflows/site-check.yml` | PR 构建检查 + 投稿脚本测试 |
| `.github/contribution-schema.md` | 三方共用的接口契约（改协议必须同步三处） |
