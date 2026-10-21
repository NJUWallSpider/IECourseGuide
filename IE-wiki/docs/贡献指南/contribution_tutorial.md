# 如何为本网站做贡献

本网站欢迎一切贡献 🎉
不过课程内容只面向 IE 范畴，外来贡献同样欢迎，但注意不要添加无关内容。

如果你想要为本网站进行贡献，以下是一些指南。

## 方法一：站内提交（推荐，无需 fork）

最简单的方式：直接打开[提交修改](../提交修改/index.md)页面，**不用 fork、不用懂 git、也不用装环境**，三步完成：

1. 选择投稿类型（补充资料 / 增补介绍 / 纠错 / 修改 / 新增课程页），填好标题、说明、正文和链接；
2. 点「🚀 生成并提交到 GitHub」，在打开的 GitHub Issue 页面里把 PDF / 图片直接拖进编辑框，点 `Submit new issue`；
3. 24 小时内机器人会回帖给出变更预览 diff，维护者批准后机器人自动修改仓库并重新构建网站。

支持的材料类型：

- 补充资料：上传往年卷、笔记、课件等文件（单个 ≤ 25MB）；
- 增补介绍：给已有页面的某个小节（或末尾）补充文字内容；
- 纠错 / 修改：精确替换页面中的错误文字（原文需在页面中恰好出现一次）；
- 新增课程页：网站还没有的课程，按模板新建页面并自动加入导航。

如果更喜欢传统方式，下面还有邮箱、GitHub Issue、fork + PR 三种方法。

## 方法二：邮箱

你可以将相关贡献的 markdown 文件和相关资源发送至邮箱baihaozhen@smail.nju.edu.cn，我会在检查后上传至网站。

## 方法三：GitHub

### Create Issues

你可以在[issue](https://github.com/NJUWallSpider/IECourseGuide/issues)中直接提出贡献内容，单个附件的上传大小限制为25MB。

### Pull Request

推荐通过 PR（即 Pull Request）的形式来进行贡献，具体流程：

- 在 GitHub 网页端点击右上角的 fork，将[本仓库](https://github.com/NJUWallSpider/IECourseGuide.git) fork 到自己的账号下
- 在自己账号的对应仓库中进行修改
- 修改完成后，点击 New pull request，提交一个 PR
- 等待其他人审核、修改，然后合并到本 repo 中

#### 本地构建指南

1. 克隆本项目 repo
    ```shell
    $ git clone https://github.com/NJUWallSpider/IECourseGuide.git
    $ cd IE-wiki
    ```
2. 安装 python 依赖（mkdocs 以及 material）
    ```shell
    $ pip install --upgrade mkdocs mkdocs-material mkdocs-material-extensions mkdocs-heti-plugin mkdocs-git-revision-date-localized-plugin mkdocs-minify-plugin
    ```
3. 启动 mkdocs 本地服务
    ```shell
    $ mkdocs serve
    ```
    - 之后即可通过浏览器访问 localhost:8000 预览网站

## 贡献守则

### 贡献守则

你可以对本网站进行任何贡献，包括完善、更新页面内容，添加新页面，样式修改等等。

如果是添加新页面的话，请记得同时更新好 `mkdocs.yml` 的 `nav` 部分，使新页面能够正常通过站点目录被访问。

对于页面内容：

- 对于课程请进行客观的评价，尽量不要带有主观色彩（比较主观的内容可以在页面下评论）
- 对于外部资源，小文件可以传入本 repo，大文件建议先存在南大网盘中，再插入永久链接
- 对于笔记、复习提纲等材料：
    - 如果有自己的网站，推荐放在自己的网站并在此插入链接
    - 也可以将文件上传到对应课程文件夹中，并插入相对链接。
- 尽量规范编写 markdown，避免出现格式错误
    - 如果你实在搞不定，不要担心，尽管上传，我发现后会及时进行修改



