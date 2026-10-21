#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 IE-wiki/mkdocs.yml 的 nav 生成站内投稿页所需的课程目录。

输出：IE-wiki/docs/assets/courses.json

    [
      {
        "category": "专业核心课",
        "name": "运筹学Ⅰ",
        "md_path": "专业核心课/运筹学Ⅰ/index.md",
        "url": "专业核心课/运筹学Ⅰ/",
        "in_nav": true
      },
      ...
    ]

收录规则（见 .github/contribution-schema.md 第 7 节、第 4.4 节）：

1. 第一步：解析 ``mkdocs.yml`` 的 ``nav``，保持 nav 顺序，收录所有课程页
   （``<分类>/<课程>/index.md``）与必学工具页（``必学工具/<页面>.md``），
   ``category`` 取 nav 中的一级分类名，``in_nav`` 为 ``true``；
2. 第二步：扫描 ``IE-wiki/docs`` 下磁盘存在、但 nav 未收录的 ``.md`` 文件，
   作为「磁盘兜底」收录，``category`` 记为「其他页面」，``in_nav`` 为 ``false``。
   这样维护者补了页面却漏改 nav，或机器人落库新课程页后，下拉框也不会缺项；
3. 排除：``docs/index.md``、各分类的 ``index.md``、``贡献指南/**``、``提交修改/**``；
4. ``md_path`` 是相对 ``IE-wiki/docs/`` 的 POSIX 路径，``url`` 是 MkDocs
   ``use_directory_urls=True`` 下的目录式 URL（``<课程>/``）。

脚本只依赖 PyYAML（mkdocs 自带），可重复执行且结果幂等：

    python tools/gen_courses.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath

try:
    import yaml
except ImportError:  # pragma: no cover - 依赖缺失时给出明确提示
    sys.stderr.write(
        "错误：需要 PyYAML（pip install pyyaml，或使用 repo/.venv 中的 python）。\n"
    )
    raise SystemExit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_ROOT = REPO_ROOT / "IE-wiki"
MKDOCS_YML = WIKI_ROOT / "mkdocs.yml"
DOCS_ROOT = WIKI_ROOT / "docs"
OUTPUT_FILE = DOCS_ROOT / "assets" / "courses.json"

# 不作为投稿对象的 nav 一级分类（首页、贡献指南、投稿页自身）
EXCLUDED_SECTIONS = {"前言", "首页", "贡献指南", "提交修改"}
# 兜底：按路径前缀排除（防止 nav 结构/磁盘扫描漏网）
EXCLUDED_PREFIXES = ("贡献指南/", "提交修改/")
# 磁盘兜底页面的分类名
FALLBACK_CATEGORY = "其他页面"


def _display_name(title: object, md_path: str) -> str:
    """nav 标题缺失时，从路径推导一个可读名字。"""
    if isinstance(title, str) and title.strip():
        return title.strip()
    pure = PurePosixPath(md_path)
    if pure.name.lower() == "index.md" and pure.parent.name:
        return pure.parent.name
    return pure.stem


def _iter_nav(entries: object, category: str | None = None):
    """深度优先遍历 nav，产出 (category, title, md_path)。

    nav 的形态是嵌套的 list/dict：``{标题: "路径.md"}``、``{标题: [子项...]}``，
    偶尔也会直接出现裸路径字符串。每层 dict 只有一个键。
    """
    if not isinstance(entries, list):
        return
    for entry in entries:
        if isinstance(entry, str):
            # 裸路径（缺少标题），由调用方决定是否收录
            yield category, None, entry
        elif isinstance(entry, dict):
            for title, value in entry.items():
                if isinstance(value, str):
                    yield category, str(title), value
                elif isinstance(value, list):
                    child_category = str(title) if category is None else category
                    yield from _iter_nav(value, child_category)


def _is_category_index(md_path: str) -> bool:
    """判断是否是「分类首页」或站点首页的 index.md。

    ``专业核心课/index.md``（分类首页）、``index.md``（站点首页）排除；
    ``专业核心课/运筹学Ⅰ/index.md``（课程页）保留。
    """
    parts = PurePosixPath(md_path).parts
    if not parts or parts[-1].lower() != "index.md":
        return False
    return len(parts) <= 2


def _is_excluded_path(md_path: str) -> bool:
    if md_path.startswith(EXCLUDED_PREFIXES):
        return True
    if _is_category_index(md_path):
        return True
    return False


def _normalize_md_path(raw: object) -> str | None:
    """把路径规范成相对 docs 的 POSIX 路径；非法则返回 None。"""
    if not isinstance(raw, str):
        return None
    path = raw.strip().replace("\\", "/")
    if not path or path.startswith("/"):
        return None
    if "://" in path:  # nav 里可能写外链，跳过
        return None
    pure = PurePosixPath(path)
    if any(part in ("", ".", "..") for part in pure.parts):
        return None
    if pure.suffix.lower() != ".md":
        return None
    return pure.as_posix()


def _page_url(md_path: str) -> str:
    """按 MkDocs use_directory_urls=True 生成站内相对 URL。"""
    pure = PurePosixPath(md_path)
    if pure.name.lower() == "index.md":
        parent = pure.parent.as_posix()
        return f"{parent}/" if parent != "." else ""
    return f"{pure.with_suffix('').as_posix()}/"


def _nav_courses() -> tuple[list[dict[str, object]], list[str]]:
    """第一步：从 nav 取叶页。返回 (课程列表, 缺失文件列表)。"""
    if not MKDOCS_YML.is_file():
        raise SystemExit(f"错误：找不到 {MKDOCS_YML}")
    with MKDOCS_YML.open("r", encoding="utf-8") as fp:
        config = yaml.safe_load(fp) or {}
    nav = config.get("nav")
    if not isinstance(nav, list):
        raise SystemExit("错误：mkdocs.yml 中没有可解析的 nav 列表。")

    courses: list[dict[str, object]] = []
    seen: set[str] = set()
    missing: list[str] = []

    for category, title, raw_path in _iter_nav(nav):
        md_path = _normalize_md_path(raw_path)
        if md_path is None or category is None:
            # 顶层不是分类块（如 "- 前言: index.md"）不是投稿对象
            continue
        if category in EXCLUDED_SECTIONS or _is_excluded_path(md_path):
            continue
        if md_path in seen:
            continue
        if not (DOCS_ROOT / md_path).is_file():
            missing.append(md_path)
            continue

        seen.add(md_path)
        courses.append(
            {
                "category": category,
                "name": _display_name(title, md_path),
                "md_path": md_path,
                "url": _page_url(md_path),
                "in_nav": True,
            }
        )
    return courses, missing


def _disk_only_courses(existing: set[str]) -> list[dict[str, object]]:
    """第二步：磁盘兜底，收录 docs 下 nav 未提及的页面。"""
    extras: list[dict[str, object]] = []
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        rel = path.relative_to(DOCS_ROOT).as_posix()
        if rel in existing:
            continue
        if any(part.startswith(".") for part in PurePosixPath(rel).parts):
            continue
        if _is_excluded_path(rel):
            continue
        extras.append(
            {
                "category": FALLBACK_CATEGORY,
                "name": _display_name(None, rel),
                "md_path": rel,
                "url": _page_url(rel),
                "in_nav": False,
            }
        )
    return extras


def build_courses() -> list[dict[str, object]]:
    courses, missing = _nav_courses()
    for md_path in missing:
        sys.stderr.write(f"警告：nav 中的页面不存在，已跳过：{md_path}\n")
    courses.extend(
        _disk_only_courses({str(course["md_path"]) for course in courses})
    )
    return courses


def main() -> int:
    courses = build_courses()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(courses, ensure_ascii=False, indent=2) + "\n"
    old = ""
    if OUTPUT_FILE.is_file():
        old = OUTPUT_FILE.read_text(encoding="utf-8")
    # UTF-8（无 BOM）、LF 换行；内容不变时不重写文件（保持 mtime 稳定）
    if text != old:
        OUTPUT_FILE.write_text(text, encoding="utf-8", newline="\n")

    categories = list(dict.fromkeys(str(course["category"]) for course in courses))
    detail = "，".join(
        f"{name} {sum(1 for c in courses if c['category'] == name)} 条"
        for name in categories
    )
    fallback = sum(1 for c in courses if not c["in_nav"])
    print(
        f"已生成 {OUTPUT_FILE.relative_to(REPO_ROOT).as_posix()}："
        f"{len(courses)} 条（{detail}；其中磁盘兜底 {fallback} 条）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
