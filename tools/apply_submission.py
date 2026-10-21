#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IECourseGuide 投稿落库脚本（契约第 4、5 节）。

用法（默认 dry-run，不写任何文件）::

    python tools/apply_submission.py \
        --repo-root . \
        --issue issue.json \
        [--dry-run | --apply] \
        [--json] \
        [--attachments-dir DIR] \
        [--token-env GITHUB_TOKEN]

退出码：``0`` 成功/预览成功；``2`` 校验失败；``3`` 落盘失败。
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

try:  # ``python tools/apply_submission.py`` 时可用
    from submission import (
        KIND_LABELS,
        MATERIAL_HEADING,
        MAX_ATTACHMENT_BYTES,
        Attachment,
        SubmissionError,
        ValidationResult,
        build_new_course_page,
        check_attachment_extension,
        convert_newlines,
        detect_newline,
        extract_attachments,
        ignored_external_links,
        link_display_name,
        markdown_link_label,
        markdown_link_target,
        normalize_newlines,
        parse_metadata,
        read_page_text,
        sanitize_filename,
        validate_metadata,
    )
except ImportError:  # ``import tools.apply_submission`` 等包形式
    from .submission import (  # type: ignore[no-redef]
        KIND_LABELS,
        MATERIAL_HEADING,
        MAX_ATTACHMENT_BYTES,
        Attachment,
        SubmissionError,
        ValidationResult,
        build_new_course_page,
        check_attachment_extension,
        convert_newlines,
        detect_newline,
        extract_attachments,
        ignored_external_links,
        link_display_name,
        markdown_link_label,
        markdown_link_target,
        normalize_newlines,
        parse_metadata,
        read_page_text,
        sanitize_filename,
        validate_metadata,
    )

USER_AGENT = "IECourseGuide-contribution-bot/1.0"
DOWNLOAD_CHUNK = 64 * 1024
DEFAULT_TIMEOUT = 90

CHANGE_ADD = "add"
CHANGE_MODIFY = "modify"

MKDOCS_REL = "IE-wiki/mkdocs.yml"

#: 这些错误码属于「落盘/运行阶段」，退出码为 3；其余为 2（校验失败）。
EXIT_CODE_3 = frozenset(
    {
        "ATTACHMENT_DOWNLOAD_FAILED",
        "WRITE_FAILED",
        "NAV_UPDATE_FAILED",
    }
)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class Change:
    """一个待落盘文件的变更。"""

    path: str  # 仓库内相对路径（posix）
    action: str  # add | modify
    diff: str
    data: bytes = b""
    abs_path: Path | None = None

    def to_json(self) -> dict:
        return {"path": self.path, "action": self.action, "diff": self.diff}


@dataclass
class AttachmentResult:
    url: str
    filename: str
    size: int
    data: bytes = field(default=b"", repr=False)
    rel_path: str = ""
    reused: bool = False

    def to_json(self) -> dict:
        return {"url": self.url, "filename": self.filename, "bytes": self.size}


@dataclass
class Plan:
    changes: list[Change] = field(default_factory=list)
    attachments: list[AttachmentResult] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 附件下载（标准库 urllib）
# ---------------------------------------------------------------------------


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """跟随重定向；跨域时丢弃 Authorization，避免 token 泄漏给 CDN。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        new_request = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_request is not None:
            old_host = urlsplit(req.full_url).netloc
            new_host = urlsplit(newurl).netloc
            if old_host != new_host:
                for container in (new_request.headers, new_request.unredirected_hdrs):
                    for key in [k for k in container if k.lower() == "authorization"]:
                        container.pop(key, None)
        return new_request


def download_attachment(
    url: str,
    token: str = "",
    asset_id: str = "",
    max_bytes: int = MAX_ATTACHMENT_BYTES,
    timeout: int = DEFAULT_TIMEOUT,
    name_hint: str = "",
) -> tuple[bytes, str]:
    """下载一枚 GitHub 附件，返回 ``(bytes, filename)``。"""

    headers = {"User-Agent": USER_AGENT, "Accept": "application/octet-stream, */*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    opener = urllib.request.build_opener(_SafeRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = response.geturl()
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > max_bytes:
                        raise SubmissionError(
                            "ATTACHMENT_TOO_LARGE",
                            f"附件超过 {max_bytes // (1024 * 1024)} MB 上限：{url}",
                        )
                except ValueError:
                    pass
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(DOWNLOAD_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise SubmissionError(
                        "ATTACHMENT_TOO_LARGE",
                        f"附件超过 {max_bytes // (1024 * 1024)} MB 上限：{url}",
                    )
                chunks.append(chunk)
            data = b"".join(chunks)
            filename = _filename_from_response(
                response.headers, final_url, asset_id, name_hint
            )
    except SubmissionError:
        raise
    except urllib.error.HTTPError as exc:
        raise SubmissionError(
            "ATTACHMENT_DOWNLOAD_FAILED",
            f"下载附件失败（HTTP {exc.code}）：{url}",
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SubmissionError(
            "ATTACHMENT_DOWNLOAD_FAILED",
            f"下载附件失败：{url}（{exc}）",
        ) from exc
    if not data:
        raise SubmissionError("ATTACHMENT_DOWNLOAD_FAILED", f"下载到的附件为空：{url}")
    return data, filename


def _filename_from_response(
    headers, final_url: str, asset_id: str, name_hint: str = ""
) -> str:
    disposition = headers.get("Content-Disposition", "") or ""
    name = ""
    match = re.search(r"filename\*\s*=\s*UTF-8''([^;\s]+)", disposition, re.I)
    if match:
        name = unquote(match.group(1).strip().strip('"'))
    if not name:
        match = re.search(r'filename\s*=\s*"([^"]+)"', disposition, re.I)
        if not match:
            match = re.search(r"filename\s*=\s*([^;\s]+)", disposition, re.I)
        if match:
            name = match.group(1).strip()
            if "%" in name:
                name = unquote(name)
    if not name:
        base = unquote(urlsplit(final_url).path.rsplit("/", 1)[-1])
        if base and "." in base:
            name = base
    if not name and name_hint:
        # /user-attachments/files/<id>/<文件名> 链接自带的文件名（下载重定向后可能丢失）
        name = name_hint
        if "%" in name:
            name = unquote(name)
    if not name:
        name = f"attachment-{asset_id or 'file'}"
    return name


# ---------------------------------------------------------------------------
# 统一 diff
# ---------------------------------------------------------------------------


def unified_diff(rel_path: str, old_text: str, new_text: str) -> str:
    chunks = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile="a/" + rel_path,
        tofile="b/" + rel_path,
        lineterm="",
    )
    return _join_diff_lines(chunks)


def new_text_file_diff(rel_path: str, content: str) -> str:
    chunks = difflib.unified_diff(
        [],
        content.splitlines(keepends=True),
        fromfile="/dev/null",
        tofile="b/" + rel_path,
        lineterm="",
    )
    return f"new file: {rel_path}\n" + _join_diff_lines(chunks)


def new_binary_file_diff(rel_path: str, size: int) -> str:
    return f"new file: {rel_path}（二进制文件，{size} 字节）\n"


def _join_diff_lines(chunks) -> str:
    out: list[str] = []
    for line in chunks:
        out.append(line if line.endswith("\n") else line + "\n")
    return "".join(out)


# ---------------------------------------------------------------------------
# 页面文本处理
# ---------------------------------------------------------------------------


@dataclass
class SectionSpan:
    heading_start: int
    content_start: int
    section_end: int


def find_section_spans(text: str, heading: str) -> list[SectionSpan]:
    """找出所有 ``## <heading>`` 小节的范围（content_start 在标题行之后）。"""

    pattern = re.compile(r"^##[ \t]+" + re.escape(heading) + r"[ \t]*$", re.M)
    heading_pattern = re.compile(r"^#{1,2}[ \t]+", re.M)
    spans: list[SectionSpan] = []
    for match in pattern.finditer(text):
        cursor = match.end()
        if text.startswith("\r\n", cursor):
            cursor += 2
        elif text.startswith("\n", cursor):
            cursor += 1
        next_heading = heading_pattern.search(text, cursor)
        section_end = next_heading.start() if next_heading else len(text)
        spans.append(SectionSpan(match.start(), cursor, section_end))
    return spans


def last_nonblank_line_end(text: str, span: SectionSpan) -> int | None:
    """返回小节内最后一个非空行结束后的偏移；小节为空时返回 None。"""

    body = text[span.content_start : span.section_end]
    offset = span.content_start
    last: int | None = None
    for line in body.splitlines(keepends=True):
        if line.strip():
            last = offset + len(line)
        offset += len(line)
    return last


def add_material_lines(text: str, lines: list[str]) -> tuple[str, list[str]]:
    """把清单行追加到 ``## 补充材料`` 小节末尾；返回 ``(新文本, 实际新增行)``。"""

    spans = find_section_spans(text, MATERIAL_HEADING)
    if spans:
        span = spans[0]
        body = text[span.content_start : span.section_end]
        existing = {line.strip() for line in body.splitlines() if line.strip()}
        new_lines = [line for line in lines if line.strip() not in existing]
        if not new_lines:
            return text, []
        insert_at = last_nonblank_line_end(text, span)
        if insert_at is None:
            insert_at = span.content_start
        block = "\n" + "".join(line + "\n" for line in new_lines)
        return text[:insert_at] + block + text[insert_at:], new_lines

    # 没有「## 补充材料」小节 → 在文件末尾新建（契约 4.1.4）
    existing = {line.strip() for line in text.splitlines() if line.strip()}
    new_lines = [line for line in lines if line.strip() not in existing]
    if not new_lines:
        return text, []
    body = "\n".join(new_lines) + "\n"
    if text:
        base = text
        if not base.endswith("\n"):
            base += "\n"
        return base + "\n## " + MATERIAL_HEADING + "\n\n" + body, new_lines
    return "## " + MATERIAL_HEADING + "\n\n" + body, new_lines


def append_to_page(text: str, content: str, marker: str, section: str) -> tuple[str, list[dict]]:
    """append 类型落库：返回 ``(新文本, warnings)``。"""

    warnings: list[dict] = []
    if marker in text:
        warnings.append(
            {
                "code": "ALREADY_APPLIED",
                "message": f"页面中已存在投稿标记 {marker}，跳过（幂等）",
            }
        )
        return text, warnings

    if section:
        spans = find_section_spans(text, section)
        if not spans:
            raise SubmissionError(
                "SECTION_NOT_FOUND",
                f"目标页面中找不到小节「## {section}」",
            )
        if len(spans) > 1:
            raise SubmissionError(
                "BAD_SECTION",
                f"目标页面中小节「## {section}」出现了 {len(spans)} 次，无法确定插入位置",
            )
        span = spans[0]
        insert_at = last_nonblank_line_end(text, span)
        if insert_at is None:
            insert_at = span.content_start
        block = "\n" + content + "\n" + marker + "\n"
        return text[:insert_at] + block + text[insert_at:], warnings

    base = text
    if base and not base.endswith("\n"):
        base += "\n"
    block = ("\n" if base else "") + content + "\n" + marker + "\n"
    return base + block, warnings


def apply_replacements(text: str, replacements: list[dict]) -> tuple[str, list[dict]]:
    """edit 类型落库：返回 ``(新文本, warnings)``；任何一组失败整单失败。"""

    warnings: list[dict] = []
    current = text
    for index, replacement in enumerate(replacements, start=1):
        old = replacement["old"]
        new = replacement["new"]
        count = current.count(old)
        if count == 1:
            current = current.replace(old, new, 1)
        elif count > 1:
            raise SubmissionError(
                "REPLACEMENT_AMBIGUOUS",
                f"第 {index} 组修改的 old 在页面中出现了 {count} 次（必须恰好 1 次），整单失败",
            )
        else:
            if new and current.count(new) == 1:
                warnings.append(
                    {
                        "code": "ALREADY_APPLIED",
                        "message": f"第 {index} 组修改已应用，跳过（幂等）",
                    }
                )
            else:
                raise SubmissionError(
                    "REPLACEMENT_NOT_FOUND",
                    f"第 {index} 组修改的 old 未在目标页面中找到，整单失败",
                )
        try:  # 契约 4.3.3：每组替换后校验仍为 UTF-8 文本
            current.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise SubmissionError(
                "REPLACEMENT_ENCODING",
                f"第 {index} 组修改后页面不是合法的 UTF-8 文本：{exc}",
            ) from exc
    return current, warnings


# ---------------------------------------------------------------------------
# mkdocs.yml nav 更新
# ---------------------------------------------------------------------------


def insert_nav_entry(mkdocs_text: str, category: str, course: str) -> tuple[str, list[dict]]:
    """在 nav 的分类块中插入 ``    - <course>: <category>/<course>/index.md``。

    分类块不存在时在 nav 块末尾追加新分类；返回 ``(新文本, warnings)``。
    """

    entry_rel = f"{category}/{course}/index.md"
    entry_line = f"    - {course}: {entry_rel}"
    warnings: list[dict] = []

    lines = mkdocs_text.splitlines(keepends=True)
    nav_start = None
    for index, line in enumerate(lines):
        if re.match(r"^nav:[ \t]*(?:#.*)?$", line.rstrip("\r\n")):
            nav_start = index
            break
    if nav_start is None:
        raise SubmissionError("NAV_UPDATE_FAILED", "mkdocs.yml 中找不到 nav 配置块，无法新增课程页")

    nav_end = len(lines)
    for index in range(nav_start + 1, len(lines)):
        content = lines[index].rstrip("\r\n")
        if not content.strip() or content.lstrip().startswith("#"):
            continue
        if len(content) == len(content.lstrip()):
            nav_end = index
            break

    for index in range(nav_start + 1, nav_end):
        if lines[index].rstrip("\r\n").strip() == entry_line.strip():
            warnings.append(
                {
                    "code": "NAV_ENTRY_EXISTS",
                    "message": f"nav 中已存在条目，未重复插入：{entry_line.strip()}",
                }
            )
            return "".join(lines), warnings

    category_pattern = re.compile(r"^  - " + re.escape(category) + r":[ \t]*$")
    for index in range(nav_start + 1, nav_end):
        if not category_pattern.match(lines[index].rstrip("\r\n")):
            continue
        last_item = index
        cursor = index + 1
        while cursor < nav_end:
            content = lines[cursor].rstrip("\r\n")
            if not content.strip() or content.lstrip().startswith("#"):
                cursor += 1
                continue
            indent = len(content) - len(content.lstrip(" "))
            if indent >= 4:
                last_item = cursor
                cursor += 1
                continue
            break
        lines.insert(last_item + 1, entry_line + "\n")
        return "".join(lines), warnings

    # 分类块不存在 → 在 nav 块末尾追加
    block = [f"  - {category}:\n", entry_line + "\n"]
    if nav_end == len(lines) and lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines[nav_end:nav_end] = block
    return "".join(lines), warnings


def verify_nav_yaml(mkdocs_text: str, category: str, course: str) -> None:
    """用 PyYAML 复验 nav；失败抛 ``NAV_UPDATE_FAILED``。"""

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - 环境问题
        raise SubmissionError(
            "NAV_UPDATE_FAILED",
            "环境缺少 PyYAML，无法校验 mkdocs.yml（请先 pip install pyyaml）",
        ) from exc
    try:
        data = yaml.safe_load(mkdocs_text)
    except yaml.YAMLError as exc:
        raise SubmissionError(
            "NAV_UPDATE_FAILED",
            f"更新 nav 后 mkdocs.yml 无法被 PyYAML 解析：{exc}",
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("nav"), list):
        raise SubmissionError("NAV_UPDATE_FAILED", "更新 nav 后 mkdocs.yml 缺少可用的 nav 列表")
    if not _nav_contains(data["nav"], course, f"{category}/{course}/index.md"):
        raise SubmissionError(
            "NAV_UPDATE_FAILED",
            f"nav 插入未生效：找不到 {course}: {category}/{course}/index.md",
        )


def _nav_contains(node, course: str, rel_path: str) -> bool:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == course and value == rel_path:
                return True
            if _nav_contains(value, course, rel_path):
                return True
        return False
    if isinstance(node, list):
        return any(_nav_contains(item, course, rel_path) for item in node)
    return False


# ---------------------------------------------------------------------------
# 落库计划
# ---------------------------------------------------------------------------


def build_plan(
    validation: ValidationResult,
    args: argparse.Namespace,
    warnings: list[dict] | None = None,
) -> Plan:
    kind = validation.kind
    plan = Plan(
        warnings=list(warnings) if warnings is not None else list(validation.warnings)
    )
    if kind == "material":
        _plan_material(validation, args, plan)
    elif kind == "append":
        _plan_append(validation, plan)
    elif kind == "edit":
        _plan_edit(validation, plan)
    elif kind == "new-course":
        _plan_new_course(validation, plan)
    else:  # pragma: no cover - validate_metadata 已拦截
        raise SubmissionError("BAD_KIND", f"未知投稿类型：{kind}")
    return plan


def _read_page_for_edit(validation: ValidationResult) -> tuple[str, str]:
    """读取目标页（统一成 LF 用于定位/插入），同时返回原换行风格。

    真实仓库的页面当前是 CRLF，而契约要求新文件为 LF；这里对已有文件保持
    原换行风格写回，避免一行改动引发整文件 diff；新页面一律 LF。
    """

    assert validation.target_path is not None
    raw = read_page_text(validation.target_path)
    if raw is None:
        raise SubmissionError(
            "PAGE_READ_FAILED",
            f"目标页面不是合法的 UTF-8 文本：{validation.page_rel}",
        )
    return normalize_newlines(raw), detect_newline(raw)


def _plan_material(validation: ValidationResult, args: argparse.Namespace, plan: Plan) -> None:
    assert validation.target_path is not None
    links: list[str] = list(validation.metadata["links"])
    payloads = _load_attachment_payloads(validation, args, plan.warnings)

    target_dir = validation.target_path.parent
    page_text, page_newline = _read_page_for_edit(validation)
    attachment_changes: list[Change] = []
    staged: dict[str, bytes] = {}
    attachment_lines: list[str] = []
    total_items = len(payloads) + len(links)
    display_name = validation.metadata["display_name"]

    for attachment, original_name, data in payloads:
        problem = check_attachment_extension(original_name)
        if problem:
            raise SubmissionError(
                "ATTACHMENT_FORBIDDEN",
                f"附件 {original_name} 不允许上传：{problem}",
            )
        clean_name = sanitize_filename(original_name)
        if check_attachment_extension(clean_name):
            raise SubmissionError(
                "ATTACHMENT_FORBIDDEN",
                f"附件 {clean_name} 不允许上传：{check_attachment_extension(clean_name)}",
            )
        final_name, reused = _pick_attachment_name(clean_name, data, target_dir, staged)
        staged[final_name] = data
        abs_path = target_dir / final_name
        rel_path = _repo_rel(abs_path, validation.repo_root)
        if reused:
            plan.warnings.append(
                {
                    "code": "ATTACHMENT_REUSED",
                    "message": f"附件已存在且内容相同，直接复用：{final_name}",
                }
            )
        else:
            if final_name != clean_name:
                plan.warnings.append(
                    {
                        "code": "ATTACHMENT_RENAMED",
                        "message": f"同名文件内容不同，附件重命名为：{final_name}",
                    }
                )
            attachment_changes.append(
                Change(
                    path=rel_path,
                    action=CHANGE_ADD,
                    diff=new_binary_file_diff(rel_path, len(data)),
                    data=data,
                    abs_path=abs_path,
                )
            )
        plan.attachments.append(
            AttachmentResult(
                url=attachment.url,
                filename=final_name,
                size=len(data),
                data=data,
                rel_path=rel_path,
                reused=reused,
            )
        )
        label = display_name if (display_name and total_items == 1) else final_name
        attachment_lines.append(
            f"- [{markdown_link_label(label)}]({markdown_link_target(final_name)})"
        )

    link_lines: list[str] = []
    for link in links:
        label = display_name if (display_name and total_items == 1) else link_display_name(link)
        link_lines.append(f"- [{markdown_link_label(label)}]({link})")

    new_text, added = add_material_lines(page_text, attachment_lines + link_lines)
    page_change: Change | None = None
    if new_text != page_text:
        assert validation.page_rel is not None
        page_change = Change(
            path=validation.page_rel,
            action=CHANGE_MODIFY,
            diff=unified_diff(validation.page_rel, page_text, new_text),
            data=convert_newlines(new_text, page_newline).encode("utf-8"),
            abs_path=validation.target_path,
        )
    plan.changes = ([page_change] if page_change else []) + attachment_changes
    if not added:
        plan.warnings.append(
            {"code": "MATERIAL_UNCHANGED", "message": "补充材料清单没有任何新增行（幂等）"}
        )


def _repo_rel(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _natural_key(path: Path) -> list[tuple[int, Any]]:
    return [
        (0, part.lower()) if not part.isdigit() else (1, int(part))
        for part in re.split(r"(\d+)", path.name)
    ]


def _load_attachment_payloads(
    validation: ValidationResult,
    args: argparse.Namespace,
    warnings: list[dict],
) -> list[tuple[Attachment, str, bytes]]:
    attachments = validation.attachments
    if not attachments:
        if args.attachments_dir:
            warnings.append(
                {
                    "code": "ATTACHMENTS_DIR_IGNORED",
                    "message": "--attachments-dir 已提供，但投稿中没有 GitHub 附件链接",
                }
            )
        return []

    if args.attachments_dir:
        directory = Path(args.attachments_dir)
        if not directory.is_dir():
            raise SubmissionError(
                "ATTACHMENT_SOURCE_MISSING",
                f"--attachments-dir 目录不存在：{directory}",
            )
        files = sorted(
            (path for path in directory.iterdir() if path.is_file()),
            key=_natural_key,
        )
        if len(files) < len(attachments):
            raise SubmissionError(
                "ATTACHMENT_SOURCE_MISSING",
                f"本地附件目录文件数不足：需要 {len(attachments)} 个，实际 {len(files)} 个"
                f"（按 Issue 中链接出现顺序配对）",
            )
        if len(files) > len(attachments):
            warnings.append(
                {
                    "code": "EXTRA_LOCAL_ATTACHMENTS",
                    "message": f"--attachments-dir 中有 {len(files) - len(attachments)} 个多余文件，已忽略",
                }
            )
        payloads: list[tuple[Attachment, str, bytes]] = []
        for attachment, path in zip(attachments, files):
            size = path.stat().st_size
            if size > MAX_ATTACHMENT_BYTES:
                raise SubmissionError(
                    "ATTACHMENT_TOO_LARGE",
                    f"附件超过 {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB 上限：{path.name}",
                )
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise SubmissionError(
                    "ATTACHMENT_DOWNLOAD_FAILED",
                    f"读取本地附件失败：{path}（{exc}）",
                ) from exc
            payloads.append((attachment, path.name, data))
        return payloads

    token = os.environ.get(args.token_env, "") if args.token_env else ""
    if not token:
        warnings.append(
            {
                "code": "NO_TOKEN",
                "message": f"环境变量 {args.token_env or 'GITHUB_TOKEN'} 为空，附件将以匿名方式下载",
            }
        )
    payloads = []
    for attachment in attachments:
        try:
            data, filename = download_attachment(
                attachment.url,
                token=token,
                asset_id=attachment.asset_id,
                name_hint=attachment.filename_hint,
            )
        except SubmissionError as exc:
            # 部分 user-attachments 链接不接受 Bearer token（会 404/403），
            # 公开仓库的附件匿名也能下载，因此失败时回退一次匿名下载。
            if token and exc.code == "ATTACHMENT_DOWNLOAD_FAILED":
                warnings.append(
                    {
                        "code": "ATTACHMENT_ANONYMOUS_RETRY",
                        "message": f"带 token 下载附件失败，改用匿名下载重试：{attachment.url}",
                    }
                )
                data, filename = download_attachment(
                    attachment.url,
                    token="",
                    asset_id=attachment.asset_id,
                    name_hint=attachment.filename_hint,
                )
            else:
                raise
        payloads.append((attachment, filename, data))
    return payloads


def _pick_attachment_name(
    clean_name: str,
    data: bytes,
    directory: Path,
    staged: dict[str, bytes],
) -> tuple[str, bool]:
    """同名文件内容相同则复用，不同则追加 -2/-3…；返回 ``(名字, 是否复用)``。"""

    stem, ext = os.path.splitext(clean_name)
    if not stem:
        stem, ext = "attachment", ext
    candidate = clean_name
    counter = 2
    while counter <= 1000:
        if candidate in staged:
            if staged[candidate] == data:
                return candidate, True
        else:
            existing = directory / candidate
            if existing.is_file():
                try:
                    existing_data = existing.read_bytes()
                except OSError:
                    existing_data = None
                if existing_data == data:
                    return candidate, True
            else:
                return candidate, False
        candidate = f"{stem}-{counter}{ext}"
        counter += 1
    raise SubmissionError(
        "ATTACHMENT_NAME_CONFLICT",
        f"无法为附件 {clean_name} 找到可用的文件名（同名文件过多）",
    )


def _plan_append(validation: ValidationResult, plan: Plan) -> None:
    assert validation.target_path is not None and validation.page_rel is not None
    text, newline = _read_page_for_edit(validation)
    marker = f"<!-- ie-submission:issue-{validation.issue_number} -->"
    new_text, warnings = append_to_page(
        text,
        validation.metadata["content"],
        marker,
        validation.metadata["section"],
    )
    plan.warnings.extend(warnings)
    if new_text == text:
        return
    plan.changes.append(
        Change(
            path=validation.page_rel,
            action=CHANGE_MODIFY,
            diff=unified_diff(validation.page_rel, text, new_text),
            data=convert_newlines(new_text, newline).encode("utf-8"),
            abs_path=validation.target_path,
        )
    )


def _plan_edit(validation: ValidationResult, plan: Plan) -> None:
    assert validation.target_path is not None and validation.page_rel is not None
    text, newline = _read_page_for_edit(validation)
    new_text, warnings = apply_replacements(text, validation.metadata["replacements"])
    plan.warnings.extend(warnings)
    if new_text == text:
        return
    plan.changes.append(
        Change(
            path=validation.page_rel,
            action=CHANGE_MODIFY,
            diff=unified_diff(validation.page_rel, text, new_text),
            data=convert_newlines(new_text, newline).encode("utf-8"),
            abs_path=validation.target_path,
        )
    )


def _plan_new_course(validation: ValidationResult, plan: Plan) -> None:
    assert validation.page_path is not None and validation.page_rel is not None
    course = validation.metadata["course"]
    category = validation.metadata["category"]
    page_text = build_new_course_page(course, validation.metadata["content"])
    plan.changes.append(
        Change(
            path=validation.page_rel,
            action=CHANGE_ADD,
            diff=new_text_file_diff(validation.page_rel, page_text),
            data=page_text.encode("utf-8"),
            abs_path=validation.page_path,
        )
    )

    mkdocs_raw = read_page_text(validation.mkdocs_path)
    if mkdocs_raw is None:
        raise SubmissionError(
            "NAV_UPDATE_FAILED",
            f"mkdocs.yml 不是合法的 UTF-8 文本：{validation.mkdocs_path}",
        )
    mkdocs_newline = detect_newline(mkdocs_raw)
    mkdocs_text = normalize_newlines(mkdocs_raw)
    new_mkdocs, warnings = insert_nav_entry(mkdocs_text, category, course)
    plan.warnings.extend(warnings)
    if new_mkdocs == mkdocs_text:
        return
    verify_nav_yaml(new_mkdocs, category, course)
    plan.changes.append(
        Change(
            path=MKDOCS_REL,
            action=CHANGE_MODIFY,
            diff=unified_diff(MKDOCS_REL, mkdocs_text, new_mkdocs),
            data=convert_newlines(new_mkdocs, mkdocs_newline).encode("utf-8"),
            abs_path=validation.mkdocs_path,
        )
    )


# ---------------------------------------------------------------------------
# 落盘（事务 + 回滚）
# ---------------------------------------------------------------------------


def write_changes(changes: list[Change], post_write_check=None) -> None:
    """按顺序写入全部变更；任何一步失败则回滚已写入的文件。"""

    written: list[tuple[Path, bytes | None]] = []
    try:
        for change in changes:
            if change.abs_path is None:
                raise SubmissionError("WRITE_FAILED", f"内部错误：变更缺少绝对路径 {change.path}")
            abs_path = change.abs_path
            original = abs_path.read_bytes() if abs_path.exists() else None
            if change.action == CHANGE_MODIFY and original is None:
                raise SubmissionError("WRITE_FAILED", f"要修改的文件不存在：{change.path}")
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            with open(abs_path, "wb") as handle:
                handle.write(change.data)
            written.append((abs_path, original))
        if post_write_check is not None:
            post_write_check()
    except SubmissionError:
        _rollback(written)
        raise
    except OSError as exc:
        _rollback(written)
        raise SubmissionError("WRITE_FAILED", f"写入文件失败：{exc}") from exc


def _rollback(written: list[tuple[Path, bytes | None]]) -> None:
    for abs_path, original in reversed(written):
        try:
            if original is None:
                if abs_path.exists():
                    abs_path.unlink()
            else:
                with open(abs_path, "wb") as handle:
                    handle.write(original)
        except OSError:  # pragma: no cover - 回滚时尽力而为
            pass


# ---------------------------------------------------------------------------
# Issue 读取
# ---------------------------------------------------------------------------


def load_issue(path: Path | str) -> dict:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise SubmissionError("ISSUE_LOAD_FAILED", f"读取 Issue JSON 失败：{path}（{exc}）") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SubmissionError(
            "ISSUE_LOAD_FAILED",
            f"Issue JSON 解析失败：{path}（第 {exc.lineno} 行：{exc.msg}）",
        ) from exc
    if not isinstance(data, dict):
        raise SubmissionError("ISSUE_LOAD_FAILED", "Issue JSON 顶层必须是一个对象")
    return data


def extract_issue_number(issue: dict) -> int:
    number = issue.get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        raise SubmissionError(
            "ISSUE_INVALID",
            f"Issue JSON 缺少合法的 number 字段（实际为 {number!r}）",
        )
    return number


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def execute(args: argparse.Namespace) -> tuple[dict, int]:
    """执行一次投稿处理，返回 ``(JSON 结果, 退出码)``。"""

    warnings: list[dict] = []
    issue: dict = {}
    issue_number: int | None = None
    kind = ""
    title = ""

    try:
        issue = load_issue(args.issue)
        issue_number = extract_issue_number(issue)
        body = issue.get("body") or ""
        metadata = parse_metadata(body)
        if metadata is None:
            raise SubmissionError(
                "NO_METADATA",
                "Issue 正文中没有 <!-- ie-contribution:v1 ... --> 标记，这不是投稿 Issue",
            )
        kind = str(metadata.get("kind") or "")
        title = str(metadata.get("title") or "")
        attachments = extract_attachments(body)
        for url in ignored_external_links(body):
            warnings.append(
                {
                    "code": "IGNORED_EXTERNAL_LINK",
                    "message": f"忽略外部链接（仅下载 GitHub 上传的附件）：{url}",
                }
            )
        validation = validate_metadata(
            metadata,
            args.repo_root,
            attachments=attachments,
            issue_number=issue_number,
        )
        warnings.extend(validation.warnings)
        if not validation.ok:
            return _failure(validation.errors, warnings, issue_number, kind, title, validation), 2

        plan = build_plan(validation, args, warnings)
        warnings = plan.warnings
        result = _success_result(validation, plan, issue_number)

        if args.apply and plan.changes:
            def post_write_check() -> None:
                if not validation.is_new_page:
                    return
                written = read_page_text(validation.mkdocs_path)
                if written is None:
                    raise SubmissionError(
                        "NAV_UPDATE_FAILED", "mkdocs.yml 写入后无法按 UTF-8 重新读取"
                    )
                verify_nav_yaml(
                    normalize_newlines(written),
                    validation.metadata["category"],
                    validation.metadata["course"],
                )
                if not validation.page_path.exists():  # pragma: no cover - 防御性检查
                    raise SubmissionError("WRITE_FAILED", "新课程页写入后不存在")

            write_changes(plan.changes, post_write_check)

        return result, 0
    except SubmissionError as exc:
        return _failure([exc.to_dict()], warnings, issue_number, kind, title, None), _exit_code(exc.code)


def _success_result(validation: ValidationResult, plan: Plan, issue_number: int) -> dict:
    title = validation.metadata["title"]
    commit_title = re.sub(r"\s+", " ", title).strip()
    return {
        "ok": True,
        "issue": issue_number,
        "kind": validation.kind,
        "title": title,
        "target": validation.metadata.get("target", ""),
        "changes": [change.to_json() for change in plan.changes],
        "attachments": [attachment.to_json() for attachment in plan.attachments],
        "commit_message": f"content: {commit_title} (#{issue_number})",
        "warnings": plan.warnings,
        "errors": [],
    }


def _failure(
    errors: list[dict],
    warnings: list[dict],
    issue_number: int | None,
    kind: str,
    title: str,
    validation: ValidationResult | None,
) -> dict:
    return {
        "ok": False,
        "issue": issue_number,
        "kind": kind,
        "title": title,
        "target": validation.metadata.get("target", "") if validation else "",
        "changes": [],
        "attachments": [],
        "commit_message": "",
        "warnings": warnings,
        "errors": errors,
    }


def _exit_code(code: str) -> int:
    return 3 if code in EXIT_CODE_3 else 2


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------


def print_human(result: dict, apply_mode: bool) -> None:
    if not result.get("ok"):
        print("投稿处理失败。")
        for error in result.get("errors") or []:
            print(f"  [{error.get('code')}] {error.get('message')}")
        _print_warnings(result.get("warnings") or [])
        return

    issue = result.get("issue")
    kind = result.get("kind", "")
    label = KIND_LABELS.get(kind, kind)
    print(f"投稿 #{issue} 「{result.get('title')}」 类型：{kind}（{label}）")
    target = result.get("target") or ""
    if target:
        print(f"目标页面：IE-wiki/docs/{target}")
    print(f"模式：{'apply（写入文件）' if apply_mode else 'dry-run（不写文件）'}")
    if result.get("commit_message"):
        print(f"提交信息：{result['commit_message']}")

    attachments = result.get("attachments") or []
    if attachments:
        print(f"附件（{len(attachments)}）：")
        for attachment in attachments:
            print(f"  - {attachment['filename']}（{attachment['bytes']} 字节）← {attachment['url']}")
    for warning in result.get("warnings") or []:
        print(f"提示：[{warning.get('code')}] {warning.get('message')}")

    changes = result.get("changes") or []
    if not changes:
        print("没有需要写入的变更。")
        return
    print(f"变更（{len(changes)} 个文件）：")
    for change in changes:
        print(f"\n=== {change['action']}: {change['path']} ===")
        diff = change.get("diff") or ""
        print(diff, end="" if diff.endswith("\n") else "\n")


def _print_warnings(warnings: list[dict]) -> None:
    for warning in warnings:
        print(f"  提示 [{warning.get('code')}] {warning.get('message')}")


def render_preview_markdown(
    result: dict,
    max_diff_chars: int = 12000,
    max_total_chars: int = 60000,
) -> str:
    """把处理结果渲染成 Issue 预览评论（供 contribution-intake.yml 使用）。"""

    marker = "<!-- ie-preview -->"
    lines: list[str] = [marker]
    issue = result.get("issue")
    issue_suffix = f"（Issue #{issue}）" if issue is not None else ""
    if result.get("ok"):
        kind = result.get("kind", "")
        lines.append(f"## 🤖 投稿预览{issue_suffix}")
        lines.append("")
        lines.append(f"- 类型：{KIND_LABELS.get(kind, kind)}（`{kind}`）")
        if result.get("target"):
            lines.append(f"- 目标页面：`{result['target']}`")
        else:
            lines.append("- 目标页面：（新增课程页）")
        lines.append(f"- 标题：{result.get('title')}")
        lines.append(f"- 预览提交信息：`{result.get('commit_message')}`")
        lines.append("")
        attachments = result.get("attachments") or []
        if attachments:
            lines.append(f"<details><summary>附件（{len(attachments)}）</summary>")
            lines.append("")
            for attachment in attachments:
                lines.append(
                    f"- `{attachment['filename']}`（{_human_size(attachment['bytes'])}）"
                    f" ← {attachment['url']}"
                )
            lines.append("")
            lines.append("</details>")
            lines.append("")
        warnings = result.get("warnings") or []
        if warnings:
            lines.append("<details><summary>提示 / 警告</summary>")
            lines.append("")
            for warning in warnings:
                lines.append(f"- `{warning.get('code')}` {warning.get('message')}")
            lines.append("")
            lines.append("</details>")
            lines.append("")
        changes = result.get("changes") or []
        if changes:
            lines.append(f"### 变更预览（{len(changes)} 个文件）")
            lines.append("")
            used = 0
            for change in changes:
                block = _render_change_block(change, max_diff_chars)
                if used + len(block) > max_total_chars:
                    lines.append("…（预览内容过长，后续变更已省略，请让维护者本地运行 dry-run 查看）")
                    break
                used += len(block)
                lines.append(block)
            lines.append("")
        else:
            lines.append("✅ 与当前仓库内容一致，没有需要写入的变更。")
            lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(
            "审核：维护者评论 `/批准`（或 `contribution:approved` 标签）后由机器人落库；"
            "评论 `/拒绝` 将关闭本 Issue。"
        )
    else:
        lines.append(f"## ❌ 投稿校验失败{issue_suffix}")
        lines.append("")
        lines.append("请按提示修改 Issue 正文后重新编辑（编辑后会自动重新预览）。")
        lines.append("")
        lines.append("### 错误")
        lines.append("")
        for error in result.get("errors") or []:
            lines.append(f"- `{error.get('code')}`：{error.get('message')}")
        warnings = result.get("warnings") or []
        if warnings:
            lines.append("")
            lines.append("### 提示")
            lines.append("")
            for warning in warnings:
                lines.append(f"- `{warning.get('code')}` {warning.get('message')}")
    lines.append("")
    lines.append("<sub>由 contribution-intake 自动生成；编辑 Issue 后会自动更新本评论，不会重复刷屏。</sub>")
    return "\n".join(lines) + "\n"


def _render_change_block(change: dict, max_diff_chars: int) -> str:
    action = change.get("action")
    title = "新增文件" if action == CHANGE_ADD else "修改文件"
    diff = change.get("diff") or ""
    truncated = ""
    if len(diff) > max_diff_chars:
        diff = diff[:max_diff_chars]
        truncated = "\n…（diff 过长，已截断）"
    return (
        f"<details><summary>{title}：<code>{change.get('path')}</code></summary>\n\n"
        "```diff\n"
        f"{diff}"
        f"{truncated}\n"
        "```\n\n"
        "</details>\n"
    )


def _human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="IECourseGuide 投稿落库脚本（默认 dry-run，不写文件）",
        epilog="退出码：0 成功；2 校验失败；3 落盘失败。",
    )
    parser.add_argument("--repo-root", default=".", help="仓库根目录（包含 IE-wiki/），默认 .")
    parser.add_argument("--issue", required=True, help="GitHub Issue JSON 文件路径")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="只预览，不写文件（默认）",
    )
    mode.add_argument(
        "--apply",
        dest="apply",
        action="store_true",
        help="真正写入仓库文件",
    )
    parser.set_defaults(apply=False)
    parser.add_argument("--json", action="store_true", help="只输出 JSON（最后一行）")
    parser.add_argument(
        "--attachments-dir",
        default=None,
        help="测试用：本地附件目录，按 Issue 中 URL 顺序配对",
    )
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="下载附件所用 token 的环境变量名（默认 GITHUB_TOKEN）",
    )
    return parser


def _configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):  # pragma: no cover - 非标准流
            pass


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    result, exit_code = execute(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print_human(result, args.apply)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
