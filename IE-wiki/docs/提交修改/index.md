# 提交修改

本页是**站内投稿入口**：填好下面的表单，点一下按钮就会打开一个**已经预填正文的 GitHub Issue 页面**，把文件拖进去、点提交即可。

!!! tip "三步完成"
    1. **选类型、填内容**：按要投稿的内容选择「补充资料 / 增补介绍 / 纠错 / 修改 / 新增课程页」，填好必填项。
    2. **生成并提交**：点「🚀 生成并提交到 GitHub」，在新标签页里把文件拖进编辑框，然后点 `Submit new issue`。
    3. **等审核上线**：24 小时内机器人会在 Issue 里贴出「变更预览」diff，维护者批准后机器人自动修改仓库、重新构建网站，新内容就上线了。

!!! warning "提交前请确认内容可以公开"
    Issue、附件和变更预览都在 GitHub 上**公开可见**。请不要上传含个人隐私、未授权版权或考试作弊相关的材料；上传前请自行确认可以公开分享。

<div id="ie-contribution-card" class="ie-contribution-card">

  <p class="ie-form-lead">选择投稿类型（带 <span class="ie-req">*</span> 的为必填项）：</p>

  <div class="ie-kind-grid" role="tablist" aria-label="选择投稿类型">
    <button type="button" class="ie-kind-card is-active" data-kind="material" role="tab" aria-selected="true">
      <span class="ie-kind-emoji" aria-hidden="true">📎</span>
      <span class="ie-kind-title">补充资料</span>
      <span class="ie-kind-desc">添加试卷、笔记、课件等文件</span>
    </button>
    <button type="button" class="ie-kind-card" data-kind="append" role="tab" aria-selected="false">
      <span class="ie-kind-emoji" aria-hidden="true">📝</span>
      <span class="ie-kind-title">增补介绍</span>
      <span class="ie-kind-desc">给已有页面补充文字 / 建议</span>
    </button>
    <button type="button" class="ie-kind-card" data-kind="edit" role="tab" aria-selected="false">
      <span class="ie-kind-emoji" aria-hidden="true">✏️</span>
      <span class="ie-kind-title">纠错 / 修改</span>
      <span class="ie-kind-desc">修正页面里的错误内容</span>
    </button>
    <button type="button" class="ie-kind-card" data-kind="new-course" role="tab" aria-selected="false">
      <span class="ie-kind-emoji" aria-hidden="true">➕</span>
      <span class="ie-kind-title">新增课程页</span>
      <span class="ie-kind-desc">网站还没有的课程，新建一页</span>
    </button>
  </div>

  <form id="ie-form" class="ie-form" novalidate autocomplete="off">

    <div class="ie-field" data-ie-kinds="material append edit">
      <label for="ie-target">课程 / 页面 <span class="ie-req">*</span></label>
      <select id="ie-target" name="target"></select>
      <input type="text" id="ie-target-manual" name="target_manual" placeholder="例如：专业核心课/运筹学Ⅰ/index.md" hidden>
      <p class="ie-hint" id="ie-target-hint">列表来自站点课程目录；找不到目标页面时请选「新增课程页」。</p>
    </div>

    <div class="ie-field" data-ie-kinds="new-course">
      <label for="ie-category">分类 <span class="ie-req">*</span></label>
      <select id="ie-category" name="category">
        <option value="专业核心课">专业核心课</option>
        <option value="专业选修课">专业选修课</option>
        <option value="跨专业课">跨专业课</option>
        <option value="数理基础课">数理基础课</option>
        <option value="必学工具">必学工具</option>
        <option value="其他">其他</option>
      </select>
      <p class="ie-hint">新页面会创建在 <code>docs/&lt;分类&gt;/&lt;课程名&gt;/index.md</code>，并自动加入导航。</p>
    </div>

    <div class="ie-field" data-ie-kinds="new-course">
      <label for="ie-new-course-name">课程名 <span class="ie-req">*</span></label>
      <input type="text" id="ie-new-course-name" name="new_course_name" maxlength="40" placeholder="例如：库存管理">
      <p class="ie-hint">1–40 字，不能包含 <code>/</code> <code>\</code> <code>:</code> 等字符。</p>
    </div>

    <div class="ie-field">
      <label for="ie-title">标题 <span class="ie-req">*</span></label>
      <input type="text" id="ie-title" name="title" maxlength="120" placeholder="例如：2024 秋期末试卷 / 修正课程作业占比">
      <p class="ie-hint">1–120 字，会作为 Issue 标题和提交信息的一部分。</p>
    </div>

    <div class="ie-field">
      <label for="ie-notes">说明（可选）</label>
      <textarea id="ie-notes" name="notes" rows="3" maxlength="2000" placeholder="想对维护者说的话：资料来源、版本、修改理由……（≤ 2000 字）"></textarea>
    </div>

    <div class="ie-field" data-ie-kinds="material">
      <label for="ie-display-name">附件显示名（可选）</label>
      <input type="text" id="ie-display-name" name="display_name" maxlength="120" placeholder="例如：2024 秋期末试卷（留空则用原文件名）">
      <p class="ie-hint">会作为附件在课程页面「补充材料」里的显示名。</p>
    </div>

    <div class="ie-field" data-ie-kinds="material">
      <label id="ie-dropzone-label">附件（PDF / 图片 / 压缩包等）</label>
      <div id="ie-dropzone" class="ie-dropzone" role="button" tabindex="0" aria-labelledby="ie-dropzone-label">
        <span class="ie-dropzone-icon" aria-hidden="true">📎</span>
        <span class="ie-dropzone-title">点击选择文件，或把文件拖到这里</span>
        <span class="ie-dropzone-sub">最多 10 个，单个文件 ≤ 25MB</span>
      </div>
      <input type="file" id="ie-file-input" multiple hidden>
      <p class="ie-hint">受浏览器安全限制，网页不能直接把本地文件写入 GitHub；提交后请把这里选好的文件拖入打开的 GitHub 编辑框完成上传（也支持在 GitHub 里点 Choose files）。</p>
      <div id="ie-file-list" class="ie-file-list" hidden>
        <div class="ie-file-list-head">
          <span>已选文件<span id="ie-file-count"></span></span>
          <span id="ie-file-total">合计 0 B</span>
        </div>
        <ul id="ie-file-rows" class="ie-file-rows"></ul>
      </div>
    </div>

    <div class="ie-field" data-ie-kinds="append">
      <label for="ie-section">插入到哪个二级标题下（可选）</label>
      <input type="text" id="ie-section" name="section" maxlength="120" placeholder="例如：课程材料；留空则追加到页面末尾">
      <p class="ie-hint">只填标题文字，不要带 <code>##</code>；找不到该小节时机器人会报错。</p>
    </div>

    <div class="ie-field" data-ie-kinds="append new-course">
      <label for="ie-content"><span id="ie-content-label-text">正文 Markdown</span> <span class="ie-req" id="ie-content-req" hidden>*</span></label>
      <textarea id="ie-content" name="content" rows="10" maxlength="20000" placeholder="支持 Markdown，例如：&#10;- 2024 秋季作业参考答案&#10;- 复习时可以重点看第 3、5 章"></textarea>
      <p class="ie-hint" id="ie-content-hint">≤ 20000 字，支持 Markdown。</p>
    </div>

    <div class="ie-field" data-ie-kinds="edit">
      <label>替换内容 <span class="ie-req">*</span></label>
      <p class="ie-hint">找到页面中「原文」并替换为「替换为」。原文必须至少 8 个字符、且在页面中<strong>恰好出现一次</strong>，否则整单会被机器人拒绝（不会做部分修改）。</p>
      <div id="ie-replacements" class="ie-replacements"></div>
      <button type="button" class="ie-btn ie-btn-small" id="ie-add-replacement">＋ 再加一组</button>
    </div>

    <div class="ie-field">
      <label for="ie-links">外部链接（可选）</label>
      <textarea id="ie-links" name="links" rows="3" maxlength="4000" placeholder="每行一个 http(s) 链接，最多 10 个&#10;例如：https://example.com/notes.pdf"></textarea>
      <p class="ie-hint">大文件（超过 25MB）建议先放到南大网盘，再把分享链接填在这里。</p>
    </div>

    <div id="ie-errors" class="ie-errors" role="alert" hidden>
      <strong>请先修正以下问题：</strong>
      <ul id="ie-error-list"></ul>
    </div>

    <div class="ie-actions">
      <button type="submit" class="ie-btn ie-btn-primary" id="ie-submit">🚀 生成并提交到 GitHub</button>
      <button type="button" class="ie-btn" id="ie-preview-btn">👀 预览 Issue 正文</button>
      <button type="button" class="ie-btn" id="ie-copy-btn">📋 复制正文</button>
      <a class="ie-btn ie-btn-link" id="ie-open-link" href="#" target="_blank" rel="noopener" hidden>↗ 手动打开 GitHub 新建 Issue 页面</a>
    </div>

    <p class="ie-status" id="ie-status" role="status" aria-live="polite"></p>

    <div class="ie-preview-wrap" id="ie-preview-wrap" hidden>
      <div class="ie-preview-head">
        <span>Issue 正文预览（可以手动全选复制）</span>
        <button type="button" class="ie-btn ie-btn-small" id="ie-preview-close">收起</button>
      </div>
      <pre id="ie-preview" class="ie-preview"></pre>
    </div>

    <div id="ie-handoff" class="ie-handoff" hidden>
      <p class="ie-handoff-title">📤 文件交接</p>
      <p class="ie-handoff-desc">现在把下面 <strong id="ie-handoff-count">0</strong> 个文件拖进刚打开的 GitHub 编辑框（或在编辑框里点 <code>Choose files</code> 选择），然后点 <code>Submit new issue</code>。本页只记录文件名清单，不会上传文件。</p>
      <ul id="ie-handoff-list" class="ie-handoff-list"></ul>
      <button type="button" class="ie-btn ie-btn-small" id="ie-handoff-copy">📋 复制文件清单</button>
      <p class="ie-status" id="ie-handoff-status" role="status" aria-live="polite"></p>
    </div>

  </form>

</div>

## 提交之后 {: #ie-after-submit }

1. **交接附件**（仅「补充资料」需要）：在新的 GitHub Issue 页面里，把本页选好的文件拖进正文编辑框（或在编辑框里点 `Choose files` 选择），GitHub 会自动上传并插入 `user-attachments` 链接。本页只记录文件名清单，**不会**上传文件。单个文件 ≤ 25MB，可以拖多个。
2. **点 `Submit new issue`**：提交后 Issue 会出现在仓库的 Issues 列表里，**不要关闭它**。
3. **等机器人预览**：24 小时内机器人会在 Issue 下贴一条评论，里面有 `<details>` 折叠的**变更预览 diff**、附件列表和审核命令说明；格式有问题也会在评论里说明原因。
4. **维护者批准后自动上线**：维护者评论 `/批准`（或加 `contribution:approved` 标签）后，机器人自动改仓库、提交 `main`（若 `main` 受保护则自动开 PR），然后网站重新构建，新内容上线。

!!! note "担心提交错了？"
    在维护者批准之前，你随时可以在 Issue 里**继续评论说明**、**编辑 Issue 正文**（编辑后机器人会重新预览），或者直接关闭 Issue 撤回。已经上线的修改，可以再提一次「纠错 / 修改」。

## 常见问题

??? question "需要 GitHub 账号吗？"
    需要，但**只需要注册一个免费账号**。注册入口见 [GitHub 官网](https://github.com/signup)。
    如果不想注册 GitHub，可以用邮箱备选方式（见下方 FAQ），或直接在 [Issues](https://github.com/NJUWallSpider/IECourseGuide/issues) 里留言。

??? question "附件可以多大？能传几个？"
    单个文件 **≤ 25MB**（GitHub 拖拽上传的限制），本页一次最多选 **10 个**文件；GitHub 本身不限上传总数。
    超过 25MB 的文件建议先放到南大网盘 / 自己的网站，再把**永久分享链接**填到「外部链接」里。

??? question "能直接在本页上传文件吗？"
    不能。受浏览器安全限制，网页不能直接把本地文件写入 GitHub。本页的「附件」区域只是帮你**记录文件名清单**并做大小 / 类型检查；
    提交后会打开 GitHub 编辑框，请把选好的文件**拖进去**（或点 `Choose files` 选择）完成真正的上传，再点 `Submit new issue`。

??? question "多久能上线？"
    提交 Issue 后，机器人通常会在 **24 小时内**贴出变更预览；维护者批准后自动落库并触发网站重建，一般 **1–2 天**内就能在网站上看到。

??? question "提交之后能修改或撤回吗？"
    可以。批准前：在 Issue 里继续评论、编辑 Issue 正文（机器人会重新预览）或关闭 Issue。
    已经上线的修改：再提一次「纠错 / 修改」即可，机器人会生成新的 diff 供维护者审核。

??? question "正文太长，GitHub 页面没有预填怎么办？"
    正文很长时，页面会自动把正文**复制到剪贴板**，只带标题打开空白 Issue：在编辑框里按 `Ctrl+V`（Mac 为 `⌘V`）粘贴，再拖入附件即可。
    也可以把内容保存成 `.md` 文件，改用「补充资料」上传；或点「👀 预览 Issue 正文」/「📋 复制正文」手动处理。

??? question "机器人说「原文找不到 / 出现多次」怎么办？"
    页面可能已经更新过。请打开目标页面，**重新原样复制**那段文字（至少 8 个字符，确保只出现一次），再提交一次；如果确实需要改多处，请分成多组替换内容。

??? question "还有其他投稿方式吗？"
    有。完整方式见[如何为本网站做贡献](../贡献指南/contribution_tutorial.md)，包括：
    邮箱 **baihaozhen@smail.nju.edu.cn**（把 markdown 和资源发过去，注明课程 / 页面）、直接提 GitHub Issue、以及传统的 Pull Request 方式。

??? question "我的邮箱/个人信息会被公开吗？"
    通过本页投稿只会公开你填写的标题、说明、正文和链接，以及你上传的附件。GitHub Issue 会显示你的 GitHub 用户名；不想公开身份就用邮箱备选方式。

<script src="../js/contribution-form.js"></script>
