#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IECourseGuide「无 fork 投稿入口」投稿协议 v1 的解析与校验库。

本模块是 ``.github/contribution-schema.md`` 第 2、3 节的代码实现，只做
「纯计算」：解析 Issue 正文、提取附件链接、校验元数据并给出规范化的
目标路径。它不读写仓库内容（落库逻辑在 ``tools/apply_submission.py``），
也不访问网络（附件下载也在 ``apply_submission.py``）。

错误码见契约第 5 节；本模块额外使用：
``BAD_JSON``、``BAD_COURSE``、``BAD_TITLE``、``BAD_NOTES``、
``BAD_LINK``、``BAD_CONTENT``、``BAD_REPLACEMENT``、``BAD_DISPLAY_NAME``、
``DOCS_NOT_FOUND``、``PAGE_READ_FAILED``。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

# ---------------------------------------------------------------------------
# 常量（契约）
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
KINDS = ("material", "append", "edit", "new-course")
KIND_LABELS = {
    "material": "补充资料",
    "append": "增补介绍",
    "edit": "纠错 / 修改",
    "new-course": "新增课程页",
}
CATEGORIES = (
    "专业核心课",
    "专业选修课",
    "跨专业课",
    "数理基础课",
    "必学工具",
    "其他",
)

MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 单个附件 ≤ 25 MB

#: 投稿元数据标记：取最后一个匹配
MARKER_PATTERN = re.compile(r"<!--\s*ie-contribution:v1\s*(\{.*?\})\s*-->", re.S)

#: GitHub 上传附件链接（契约第 2 节，只接受这两种形式）
ATTACHMENT_URL_PATTERN = re.compile(
    r"https://github\.com/(?:"
    r"user-attachments/assets/[A-Za-z0-9][A-Za-z0-9._-]*"
    r"|"
    r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*/assets/[A-Za-z0-9][A-Za-z0-9._-]*"
    r")"
)

#: 普通 URL（用于在「## 附件」小节里发现被忽略的外部链接）
_BARE_URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]\"'`]+")

#: 页面上「补充材料」小节标题
MATERIAL_HEADING = "补充材料"

HEADING_LEVEL2_PATTERN = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.M)

#: 文件名清洗：\ / : * ? " < > | 以及控制字符
_FILENAME_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
#: 课程名（用于目录 / 导航）额外禁止 #，否则会破坏 mkdocs.yml 的 YAML
_COURSE_FORBIDDEN = re.compile(r'[\\/:*?"<>|#\x00-\x1f\x7f]')

#: 附件扩展名黑名单（可执行文件 / 可能带来 XSS 的网页文件）
FORBIDDEN_ATTACHMENT_EXTENSIONS = frozenset(
    {
        ".exe",
        ".dll",
        ".msi",
        ".msp",
        ".bat",
        ".cmd",
        ".com",
        ".scr",
        ".pif",
        ".ps1",
        ".psm1",
        ".vbs",
        ".vbe",
        ".wsf",
        ".hta",
        ".lnk",
        ".reg",
        ".jar",
        ".apk",
        ".dmg",
        ".pkg",
        ".deb",
        ".rpm",
        ".app",
        ".iso",
        ".html",
        ".htm",
        ".xhtml",
        ".svg",
        ".swf",
    }
)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


# ---------------------------------------------------------------------------
# 错误类型
# ---------------------------------------------------------------------------


class SubmissionError(Exception):
    """带结构化错误码的异常，``to_dict()`` 可直接进入 JSON 输出。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


# ---------------------------------------------------------------------------
# 附件链接
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Attachment:
    """Issue 正文里的一枚 GitHub 附件链接。"""

    url: str
    asset_id: str
    owner: str = ""
    repo: str = ""

    @property
    def kind(self) -> str:
        return "user-attachments" if not self.owner else "repo-assets"


def extract_attachments(body: str) -> list[Attachment]:
    """按出现顺序提取并去重 GitHub 附件链接（契约第 2 节）。"""

    if not isinstance(body, str):
        return []
    seen: set[str] = set()
    result: list[Attachment] = []
    for match in ATTACHMENT_URL_PATTERN.finditer(body):
        url = match.group(0)
        if url in seen:
            continue
        seen.add(url)
        parts = url.split("/")
        asset_id = parts[-1]
        if "user-attachments" in parts:
            owner = repo = ""
        else:
            owner = parts[3]
            repo = parts[4]
        result.append(Attachment(url=url, asset_id=asset_id, owner=owner, repo=repo))
    return result


def ignored_external_links(body: str) -> list[str]:
    """返回「## 附件」小节里被忽略的非 GitHub 附件链接（用于 warning）。

    契约要求「其他域名一律不下载，只在预览里提示忽略外部链接」。这里只看
    ``## 附件`` 小节，避免把元数据里合法的 ``links`` 也报成 warning。
    """

    if not isinstance(body, str):
        return []
    section = _find_attachment_section(body)
    if section is None:
        return []
    ignored: list[str] = []
    seen: set[str] = set()
    for match in _BARE_URL_PATTERN.finditer(section):
        url = match.group(0).rstrip(".,;:，。；：、!")
        if ATTACHMENT_URL_PATTERN.fullmatch(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        ignored.append(url)
    return ignored


def _find_attachment_section(body: str) -> str | None:
    lines = body.splitlines(keepends=True)
    start = None
    for index, line in enumerate(lines):
        if re.match(r"^##[ \t]*附件[ \t]*$", line.strip() + "\n"):
            start = index + 1
            continue
        if start is not None:
            if re.match(r"^#{1,2}[ \t]+", line):
                return "".join(lines[start:index])
    if start is not None:
        return "".join(lines[start:])
    return None


# ---------------------------------------------------------------------------
# 元数据解析
# ---------------------------------------------------------------------------


def parse_metadata(body: str) -> dict | None:
    """从 Issue 正文提取投稿元数据。

    - 没有 ``<!-- ie-contribution:v1 ... -->`` 标记 → 返回 ``None``
      （不是投稿 Issue，工作流直接忽略）。
    - 有多个标记 → 取最后一个（契约第 2 节）。
    - JSON 损坏 → 抛 :class:`SubmissionError` (``BAD_JSON``)。
    """

    if not isinstance(body, str):
        return None
    matches = list(MARKER_PATTERN.finditer(body))
    if not matches:
        return None
    raw = matches[-1].group(1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SubmissionError(
            "BAD_JSON",
            f"投稿元数据 JSON 解析失败：{exc.msg}（第 {exc.lineno} 行第 {exc.colno} 列）",
        ) from exc
    if not isinstance(data, dict):
        raise SubmissionError("BAD_JSON", "投稿元数据必须是一个 JSON 对象")
    return data


# ---------------------------------------------------------------------------
# 校验结果
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """一次校验的完整结果，供 ``apply_submission.py`` 直接消费。"""

    repo_root: Path
    docs_root: Path
    mkdocs_path: Path
    metadata: dict = field(default_factory=dict)
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    #: 已存在页面的绝对路径（new-course 为空）
    target_path: Path | None = None
    #: 落库后的页面绝对路径（new-course 为新页面）
    page_path: Path | None = None
    #: 页面仓库内相对路径（posix 风格），用于 JSON 的 changes.path
    page_rel: str | None = None
    #: 相对 IE-wiki/docs 的页面路径（new-course 为新建页面路径）
    page_docs_rel: str | None = None
    is_new_page: bool = False
    issue_number: int | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def kind(self) -> str:
        return self.metadata.get("kind", "")

    @property
    def target_rel(self) -> str:
        return self.metadata.get("target", "")


# ---------------------------------------------------------------------------
# 校验实现
# ---------------------------------------------------------------------------


def validate_metadata(
    metadata: dict | None,
    repo_root: Path | str,
    attachments: Iterable[Attachment] | None = None,
    issue_number: int | None = None,
) -> ValidationResult:
    """按契约第 3 节校验元数据，收集全部错误而不是遇到第一个就退出。"""

    repo_root = Path(repo_root)
    docs_root = repo_root / "IE-wiki" / "docs"
    mkdocs_path = repo_root / "IE-wiki" / "mkdocs.yml"
    result = ValidationResult(
        repo_root=repo_root,
        docs_root=docs_root,
        mkdocs_path=mkdocs_path,
        metadata={},
        attachments=list(attachments or []),
        issue_number=issue_number,
    )
    errors = result.errors
    warnings = result.warnings

    if not docs_root.is_dir():
        errors.append(
            {
                "code": "DOCS_NOT_FOUND",
                "message": f"仓库中找不到文档目录：{docs_root}",
            }
        )
        return result

    meta = metadata if isinstance(metadata, dict) else {}
    if not isinstance(metadata, dict):
        errors.append(
            {"code": "BAD_JSON", "message": "投稿元数据必须是一个 JSON 对象"}
        )

    normalized: dict[str, Any] = {
        "version": SCHEMA_VERSION,
        "kind": "",
        "target": "",
        "course": "",
        "category": "",
        "title": "",
        "display_name": "",
        "section": "",
        "notes": "",
        "links": [],
        "content": "",
        "replacements": [],
    }
    result.metadata = normalized

    # --- version -----------------------------------------------------------
    version = meta.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version != SCHEMA_VERSION:
        errors.append(
            {
                "code": "BAD_VERSION",
                "message": f"元数据 version 必须为整数 {SCHEMA_VERSION}，实际为 {version!r}",
            }
        )

    # --- kind --------------------------------------------------------------
    kind = meta.get("kind")
    if not isinstance(kind, str) or kind not in KINDS:
        errors.append(
            {
                "code": "BAD_KIND",
                "message": f"kind 必须是 {' / '.join(KINDS)} 之一，实际为 {kind!r}",
            }
        )
        return result
    normalized["kind"] = kind

    # --- course ------------------------------------------------------------
    course = meta.get("course")
    if not isinstance(course, str):
        errors.append(
            {"code": "BAD_COURSE", "message": f"course 必须是字符串，实际为 {course!r}"}
        )
    else:
        course = course.strip()
        max_course_len = 40 if kind == "new-course" else 60
        if not (1 <= len(course) <= max_course_len):
            errors.append(
                {
                    "code": "BAD_COURSE",
                    "message": f"course 长度需在 1–{max_course_len} 字之间（实际 {len(course)} 字）",
                }
            )
        elif _CONTROL_CHARS.search(course):
            errors.append({"code": "BAD_COURSE", "message": "course 不能包含换行等控制字符"})
        else:
            normalized["course"] = course

    # --- category ----------------------------------------------------------
    category = meta.get("category")
    if category is None:
        category = ""
    if not isinstance(category, str):
        errors.append({"code": "BAD_CATEGORY", "message": f"category 必须是字符串，实际为 {category!r}"})
    else:
        category = category.strip()
        if kind == "new-course" and not category:
            errors.append(
                {
                    "code": "BAD_CATEGORY",
                    "message": f"new-course 必须提供 category，可选值：{' / '.join(CATEGORIES)}",
                }
            )
        elif category and category not in CATEGORIES:
            errors.append(
                {
                    "code": "BAD_CATEGORY",
                    "message": f"category 必须是 {' / '.join(CATEGORIES)} 之一，实际为 {category!r}",
                }
            )
        elif category:
            normalized["category"] = category

    # --- title -------------------------------------------------------------
    title = meta.get("title")
    if not isinstance(title, str):
        errors.append({"code": "BAD_TITLE", "message": f"title 必须是字符串，实际为 {title!r}"})
    else:
        title = title.strip()
        if not (1 <= len(title) <= 120):
            errors.append(
                {
                    "code": "BAD_TITLE",
                    "message": f"title 长度需在 1–120 字之间（实际 {len(title)} 字）",
                }
            )
        elif _CONTROL_CHARS.search(title):
            errors.append({"code": "BAD_TITLE", "message": "title 不能包含换行等控制字符"})
        else:
            normalized["title"] = title

    # --- notes -------------------------------------------------------------
    notes = meta.get("notes")
    if notes is None:
        notes = ""
    if not isinstance(notes, str):
        errors.append({"code": "BAD_NOTES", "message": "notes 必须是字符串"})
    elif len(notes.strip()) > 2000:
        errors.append({"code": "BAD_NOTES", "message": "notes 长度不能超过 2000 字"})
    else:
        normalized["notes"] = notes.strip()

    # --- links -------------------------------------------------------------
    links = meta.get("links")
    if links is None:
        links = []
    if not isinstance(links, list):
        errors.append({"code": "BAD_LINK", "message": "links 必须是数组"})
    elif len(links) > 10:
        errors.append({"code": "BAD_LINK", "message": f"links 最多 10 个（实际 {len(links)} 个）"})
    else:
        for index, link in enumerate(links, start=1):
            if not isinstance(link, str) or not link.strip():
                errors.append({"code": "BAD_LINK", "message": f"第 {index} 个链接为空或不是字符串"})
                continue
            link = link.strip()
            problem = check_http_url(link)
            if problem:
                errors.append(
                    {
                        "code": "BAD_LINK",
                        "message": f"第 {index} 个链接不合法：{link}（{problem}）",
                    }
                )
                continue
            if link in normalized["links"]:
                warnings.append(
                    {"code": "DUPLICATE_LINK", "message": f"链接重复，已去重：{link}"}
                )
                continue
            normalized["links"].append(link)

    # --- display_name ------------------------------------------------------
    display_name = meta.get("display_name")
    if display_name is None:
        display_name = ""
    if not isinstance(display_name, str):
        errors.append({"code": "BAD_DISPLAY_NAME", "message": "display_name 必须是字符串"})
    else:
        display_name = display_name.strip()
        if len(display_name) > 200:
            errors.append(
                {"code": "BAD_DISPLAY_NAME", "message": "display_name 长度不能超过 200 字"}
            )
        elif _CONTROL_CHARS.search(display_name):
            errors.append(
                {"code": "BAD_DISPLAY_NAME", "message": "display_name 不能包含换行等控制字符"}
            )
        else:
            normalized["display_name"] = display_name

    # --- section -----------------------------------------------------------
    section = meta.get("section")
    if section is None:
        section = ""
    if not isinstance(section, str):
        errors.append({"code": "BAD_SECTION", "message": "section 必须是字符串"})
    else:
        section = section.strip()
        if _CONTROL_CHARS.search(section):
            errors.append({"code": "BAD_SECTION", "message": "section 不能包含换行等控制字符"})
        elif len(section) > 200:
            errors.append({"code": "BAD_SECTION", "message": "section 长度不能超过 200 字"})
        elif section:
            normalized["section"] = section
            if kind != "append":
                warnings.append(
                    {
                        "code": "IGNORED_FIELD",
                        "message": f"{kind} 类型不使用 section 字段，已忽略：{section}",
                    }
                )

    # --- content -----------------------------------------------------------
    content = meta.get("content")
    if content is None:
        content = ""
    if not isinstance(content, str):
        errors.append({"code": "BAD_CONTENT", "message": "content 必须是字符串"})
    else:
        content = normalize_newlines(content)
        if kind == "append":
            if not content.strip():
                errors.append(
                    {"code": "BAD_CONTENT", "message": "append 类型必须提供非空的 content"}
                )
            elif len(content.strip()) > 20000:
                errors.append(
                    {"code": "BAD_CONTENT", "message": "content 长度不能超过 20000 字"}
                )
            else:
                normalized["content"] = content.strip("\n")
        elif kind == "new-course":
            if len(content.strip()) > 20000:
                errors.append(
                    {"code": "BAD_CONTENT", "message": "content 长度不能超过 20000 字"}
                )
            else:
                normalized["content"] = content.strip("\n")
        elif content.strip():
            warnings.append(
                {
                    "code": "IGNORED_FIELD",
                    "message": f"{kind} 类型不使用 content 字段，已忽略",
                }
            )

    # --- replacements ------------------------------------------------------
    replacements = meta.get("replacements")
    if replacements is None:
        replacements = []
    if not isinstance(replacements, list):
        errors.append({"code": "BAD_REPLACEMENT", "message": "replacements 必须是数组"})
    elif kind == "edit":
        if not (1 <= len(replacements) <= 20):
            errors.append(
                {
                    "code": "BAD_REPLACEMENT",
                    "message": f"edit 的 replacements 需要 1–20 组（实际 {len(replacements)} 组）",
                }
            )
        else:
            valid = True
            for index, item in enumerate(replacements, start=1):
                if not isinstance(item, dict):
                    errors.append(
                        {"code": "BAD_REPLACEMENT", "message": f"第 {index} 组 replacement 不是对象"}
                    )
                    valid = False
                    continue
                old, new = item.get("old"), item.get("new")
                if not isinstance(old, str) or not isinstance(new, str):
                    errors.append(
                        {
                            "code": "BAD_REPLACEMENT",
                            "message": f"第 {index} 组 replacement 的 old/new 必须都是字符串",
                        }
                    )
                    valid = False
                elif len(old) < 8:
                    errors.append(
                        {
                            "code": "BAD_REPLACEMENT",
                            "message": f"第 {index} 组 replacement 的 old 长度必须 ≥ 8（实际 {len(old)}）",
                        }
                    )
                    valid = False
                elif old == new:
                    errors.append(
                        {
                            "code": "BAD_REPLACEMENT",
                            "message": f"第 {index} 组 replacement 的 old 与 new 相同",
                        }
                    )
                    valid = False
                else:
                    normalized["replacements"].append({"old": old, "new": new})
            if not valid:
                normalized["replacements"] = []
    elif replacements:
        warnings.append(
            {
                "code": "IGNORED_FIELD",
                "message": f"{kind} 类型不使用 replacements 字段，已忽略",
            }
        )

    # --- 目标路径 / 各类型专属校验 -----------------------------------------
    if kind == "new-course":
        _validate_new_course(meta, result)
    else:
        _validate_existing_target(result, meta)

    if kind == "material":
        if not result.attachments and not normalized["links"]:
            errors.append(
                {
                    "code": "EMPTY_MATERIAL",
                    "message": "material 类型至少要提供一个 GitHub 附件或一个外部链接",
                }
            )
        if normalized["display_name"] and len(result.attachments) > 1:
            warnings.append(
                {
                    "code": "MULTIPLE_ATTACHMENTS_DISPLAY_NAME",
                    "message": "本单有多个附件，display_name 只用于唯一附件；多附件时改用各文件名",
                }
            )
    elif kind in ("append", "edit"):
        if result.attachments:
            warnings.append(
                {
                    "code": "ATTACHMENTS_IGNORED",
                    "message": f"{kind} 类型不处理附件，已忽略 {len(result.attachments)} 个附件链接",
                }
            )
        if normalized["links"]:
            warnings.append(
                {
                    "code": "LINKS_IGNORED",
                    "message": f"{kind} 类型不处理 links 字段，已忽略 {len(normalized['links'])} 个链接",
                }
            )

    return result


def _validate_existing_target(result: ValidationResult, meta: dict) -> None:
    """校验 target 存在、路径安全；append 还要校验 section 是否存在。"""

    errors = result.errors
    normalized = result.metadata
    target = meta.get("target")
    if not isinstance(target, str) or not target.strip():
        errors.append(
            {
                "code": "BAD_TARGET",
                "message": "target 不能为空，且必须是相对 IE-wiki/docs/ 的 .md 路径",
            }
        )
        return
    target = target.strip()
    problem = check_target_path(target)
    if problem:
        errors.append({"code": "BAD_TARGET", "message": f"target 路径不安全：{problem}"})
        return

    target_path = _docs_join(result.docs_root, target)
    if target_path is None or not _is_relative_to(target_path, result.docs_root):
        errors.append({"code": "BAD_TARGET", "message": f"target 超出了文档目录：{target}"})
        return
    if not target_path.is_file():
        errors.append(
            {
                "code": "TARGET_NOT_FOUND",
                "message": f"目标页面不存在：IE-wiki/docs/{target}",
            }
        )
        return

    normalized["target"] = target
    result.target_path = target_path
    result.page_path = target_path
    result.page_docs_rel = target
    result.page_rel = "IE-wiki/docs/" + target

    # append 的 section 必须在页面中恰好存在一次
    if normalized["kind"] == "append" and normalized["section"]:
        text = read_page_text(target_path)
        if text is None:
            errors.append(
                {
                    "code": "PAGE_READ_FAILED",
                    "message": f"目标页面不是合法的 UTF-8 文本：IE-wiki/docs/{target}",
                }
            )
            return
        count = count_section_headings(normalize_newlines(text), normalized["section"])
        if count == 0:
            errors.append(
                {
                    "code": "SECTION_NOT_FOUND",
                    "message": f"目标页面中找不到小节「## {normalized['section']}」",
                }
            )
        elif count > 1:
            errors.append(
                {
                    "code": "BAD_SECTION",
                    "message": f"目标页面中小节「## {normalized['section']}」出现了 {count} 次，无法确定插入位置",
                }
            )


def _validate_new_course(meta: dict, result: ValidationResult) -> None:
    """new-course：校验课程名、目标页面与 mkdocs.yml。"""

    errors = result.errors
    normalized = result.metadata

    target = meta.get("target")
    if target not in (None, ""):
        if not isinstance(target, str) or target.strip():
            errors.append(
                {
                    "code": "BAD_TARGET",
                    "message": "new-course 的 target 必须为空字符串（页面路径由 category + course 推导）",
                }
            )

    course = normalized["course"]
    category = normalized["category"]
    if not course or not category:
        return

    problem = check_course_name(course)
    if problem:
        errors.append({"code": "BAD_COURSE", "message": f"课程名不合法：{problem}"})
        return

    page_path = _docs_join(result.docs_root, category, course, "index.md")
    if page_path is None or not _is_relative_to(page_path, result.docs_root):
        errors.append({"code": "BAD_COURSE", "message": "课程名导致页面路径越界"})
        return
    if page_path.exists():
        errors.append(
            {
                "code": "DUPLICATE_PAGE",
                "message": f"页面已存在：IE-wiki/docs/{category}/{course}/index.md",
            }
        )
        return

    normalized["target"] = ""
    result.page_path = page_path
    result.page_docs_rel = f"{category}/{course}/index.md"
    result.page_rel = "IE-wiki/docs/" + result.page_docs_rel
    result.is_new_page = True

    if not result.mkdocs_path.is_file():
        errors.append(
            {
                "code": "NAV_UPDATE_FAILED",
                "message": f"找不到 mkdocs.yml，无法更新 nav：{result.mkdocs_path}",
            }
        )


# ---------------------------------------------------------------------------
# 路径 / 文本工具
# ---------------------------------------------------------------------------


def check_target_path(path: str) -> str | None:
    """检查 target 是否为安全、相对 docs 的 .md 路径；返回问题描述或 None。"""

    if not isinstance(path, str) or not path:
        return "路径为空"
    if unquote(path) != path:
        return "路径不得包含 URL 编码字符（如 %2e%2e），以防编码绕过"
    if "\\" in path:
        return "路径不得包含反斜杠"
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return "必须使用相对路径"
    segments = path.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        return "路径不得包含空段、. 或 .."
    if not path.lower().endswith(".md"):
        return "路径必须以 .md 结尾"
    if _CONTROL_CHARS.search(path):
        return "路径包含控制字符"
    return None


def check_course_name(course: str) -> str | None:
    """new-course 的课程名同时用于目录名与 nav，必须能安全放进 YAML。"""

    if not course:
        return "课程名为空"
    if len(course) > 40:
        return f"课程名不能超过 40 字（实际 {len(course)} 字）"
    if _COURSE_FORBIDDEN.search(course):
        return '课程名不能包含 \\ / : * ? " < > | # 等字符'
    if not course.strip(" ."):
        return "课程名不能只由点或空格组成"
    if course[0] in "-?:,[]{}#&*!|>'\"%@`":
        return f"课程名不能以特殊字符 {course[0]!r} 开头"
    return None


def sanitize_filename(name: str, max_length: int = 80, fallback: str = "attachment") -> str:
    """按契约 4.1.2 清洗附件文件名（保留扩展名并截断到 80 字符）。"""

    name = name if isinstance(name, str) else ""
    name = name.replace("\ufffd", "")
    name = _FILENAME_FORBIDDEN.sub("_", name)
    name = name.strip(" .\t")
    if not name:
        return fallback
    stem, ext = os.path.splitext(name)
    stem = stem.strip(" .")
    if not stem:
        stem = fallback
    if len(stem) + len(ext) > max_length:
        keep = max_length - len(ext)
        if keep < 1:
            keep = max_length
            ext = ""
        stem = stem[:keep].rstrip(" .")
        if not stem:
            stem = fallback
    return stem + ext


def attachment_extension(name: str) -> str:
    return os.path.splitext(name)[1].lower()


def check_attachment_extension(name: str) -> str | None:
    """返回问题描述或 None。"""

    ext = attachment_extension(name)
    if ext in FORBIDDEN_ATTACHMENT_EXTENSIONS:
        return f"不允许上传 {ext} 类型的文件"
    return None


def markdown_link_target(filename: str) -> str:
    """markdown 链接里的文件名转义：空格 → %20，并转义会破坏链接语法的字符。"""

    return (
        filename.replace("%", "%25")
        .replace(" ", "%20")
        .replace("(", "%28")
        .replace(")", "%29")
        .replace("[", "%5B")
        .replace("]", "%5D")
    )


def markdown_link_label(label: str) -> str:
    """转义链接文字里的方括号。"""

    return label.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def link_display_name(url: str) -> str:
    """外部链接的缺省显示名：域名。"""

    try:
        host = urlsplit(url).netloc
    except ValueError:
        host = ""
    return host or url


def check_http_url(url: str) -> str | None:
    if not isinstance(url, str) or not url:
        return "URL 为空"
    if _CONTROL_CHARS.search(url) or any(ch.isspace() for ch in url):
        return "URL 不能包含空白或控制字符"
    if len(url) > 2048:
        return "URL 过长"
    try:
        parsed = urlsplit(url)
    except ValueError:
        return "URL 解析失败"
    if parsed.scheme.lower() not in ("http", "https"):
        return "只接受 http/https 链接"
    if not parsed.netloc:
        return "URL 缺少域名"
    return None


def count_section_headings(text: str, heading: str) -> int:
    """统计 ``## <heading>`` 出现次数（heading 必须整行匹配）。"""

    pattern = re.compile(r"^##[ \t]+" + re.escape(heading) + r"[ \t]*$", re.M)
    return len(pattern.findall(text))


def read_page_text(path: Path) -> str | None:
    """读取页面文本（UTF-8，去掉 BOM）；失败返回 None。"""

    try:
        raw = Path(path).read_bytes()
    except OSError:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if text.startswith("\ufeff"):
        text = text[1:]
    return text


def build_new_course_page(course: str, content: str = "") -> str:
    """按契约 4.4.2 生成新课程页（UTF-8，LF）。"""

    body = normalize_newlines(content or "").strip("\n")
    if not body.strip():
        body = "（待补充）"
    return (
        "---\n"
        "abbrs:\n"
        f"    - {course}\n"
        "---\n"
        "\n"
        f"# {course}\n"
        "\n"
        "## 课程学习内容\n"
        "\n"
        f"{body}\n"
        "\n"
        "## 任课老师\n"
        "\n"
        "（待补充）\n"
        "\n"
        "## 考核标准\n"
        "\n"
        "（待补充）\n"
        "\n"
        "## 推荐教材\n"
        "\n"
        "（待补充）\n"
        "\n"
        "## 补充材料\n"
    )


def new_course_nav_entry(category: str, course: str) -> str:
    """nav 里新增的条目文本（不含缩进）：``<course>: <category>/<course>/index.md``。"""

    return f"{course}: {category}/{course}/index.md"


def normalize_newlines(text: str) -> str:
    """统一成 LF，便于做小节省定位（写入时再恢复原文件换行风格）。"""

    return text.replace("\r\n", "\n").replace("\r", "\n")


def detect_newline(text: str) -> str:
    """判断文本的换行风格，返回 ``"\\r\\n"`` 或 ``"\\n"``。"""

    return "\r\n" if "\r\n" in text else "\n"


def convert_newlines(text: str, newline: str) -> str:
    """把 LF 文本转换为指定换行风格（newline 为 ``"\\n"`` 时原样返回）。"""

    if newline == "\n":
        return text
    return text.replace("\n", newline)


def _docs_join(docs_root: Path, *segments: str) -> Path | None:
    try:
        return docs_root.joinpath(*segments)
    except (TypeError, ValueError):
        return None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


__all__ = [
    "Attachment",
    "CATEGORIES",
    "FORBIDDEN_ATTACHMENT_EXTENSIONS",
    "KINDS",
    "KIND_LABELS",
    "MATERIAL_HEADING",
    "MAX_ATTACHMENT_BYTES",
    "MARKER_PATTERN",
    "SCHEMA_VERSION",
    "SubmissionError",
    "ValidationResult",
    "attachment_extension",
    "build_new_course_page",
    "check_attachment_extension",
    "check_course_name",
    "check_http_url",
    "check_target_path",
    "convert_newlines",
    "count_section_headings",
    "detect_newline",
    "extract_attachments",
    "ignored_external_links",
    "link_display_name",
    "markdown_link_label",
    "markdown_link_target",
    "new_course_nav_entry",
    "normalize_newlines",
    "parse_metadata",
    "read_page_text",
    "sanitize_filename",
    "validate_metadata",
]
