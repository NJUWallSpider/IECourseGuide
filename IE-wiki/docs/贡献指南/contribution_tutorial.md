# 如何为本网站做贡献

本网站欢迎一切贡献 🎉
不过课程内容只面向 IE 范畴，外来贡献同样欢迎，但注意不要添加无关内容。

如果你想要为本网站进行贡献，以下是一些指南。

## 方法一：邮箱

你可以将相关贡献的 markdown 文件和相关资源发送至邮箱baihaozhen@smail.nju.edu.cn，我会在检查后上传至网站。

## 方法二：Github

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
    $ pip install --upgrade mkdocs mkdocs-material mkdocs-material-extensions mkdocs-heti-plugin
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



