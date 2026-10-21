# -*- coding: utf-8 -*-
"""投稿协议 v1 的单元测试（契约见 .github/contribution-schema.md）。

全部测试只使用 ``tmp_path`` 里构造的最小 docs 树 + mkdocs.yml，不依赖真实仓库。
"""

from __future__ import annotations

import email.message
import http.server
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest
import yaml

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import apply_submission as A  # noqa: E402
import submission as S  # noqa: E402

# ---------------------------------------------------------------------------
# 测试数据
# ---------------------------------------------------------------------------

PAGE_REL = "专业核心课/运筹学Ⅰ/index.md"
PAGE = "# 运筹学Ⅰ\n\n## 课程学习内容\n\n运筹学内容。\n"

DEFAULT_MKDOCS = """site_name: 测试站点
nav:
  - 前言: "index.md"
  - 专业核心课:
    - 专业核心课/index.md
    - 运筹学Ⅰ: 专业核心课/运筹学Ⅰ/index.md
  - 专业选修课:
    - 数值分析: 专业选修课/数值分析/index.md
"""

ATT1 = "https://github.com/user-attachments/assets/11111111-1111-1111-1111-111111111111"
ATT2 = "https://github.com/user-attachments/assets/22222222-2222-2222-2222-222222222222"
ATT3 = "https://github.com/user-attachments/assets/33333333-3333-3333-3333-333333333333"
REPO_ASSET = "https://github.com/NJUWallSpider/IECourseGuide/assets/12345678"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def make_repo(tmp_path: Path, pages: dict[str, str] | None = None, mkdocs: str = DEFAULT_MKDOCS) -> Path:
    repo = tmp_path / "repo"
    docs = repo / "IE-wiki" / "docs"
    docs.mkdir(parents=True)
    for rel, text in (pages or {}).items():
        path = docs.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    (repo / "IE-wiki" / "mkdocs.yml").write_text(mkdocs, encoding="utf-8", newline="\n")
    return repo


def make_attachments(tmp_path: Path, files: dict[str, bytes]) -> Path:
    directory = tmp_path / "attachments"
    directory.mkdir(exist_ok=True)
    for name, data in files.items():
        (directory / name).write_bytes(data)
    return directory


def material_meta(**overrides) -> dict:
    meta = {
        "version": 1,
        "kind": "material",
        "target": PAGE_REL,
        "course": "运筹学Ⅰ",
        "category": "",
        "title": "2024 秋期末试卷",
        "display_name": "2024 秋期末试卷",
        "section": "",
        "notes": "",
        "links": [],
        "content": "",
        "replacements": [],
    }
    meta.update(overrides)
    return meta


def make_issue(
    tmp_path: Path,
    meta: dict | None,
    attachment_urls=(),
    external_urls=(),
    *,
    number: int = 7,
    include_marker: bool = True,
    body_extra: str = "",
    raw_body: str | None = None,
) -> Path:
    if raw_body is not None:
        body = raw_body
    else:
        parts = ["## 投稿类型", "", "## 附件", "<!-- ie-attachments -->", ""]
        parts.extend(attachment_urls)
        parts.extend(external_urls)
        parts.append("")
        if include_marker:
            parts.extend(
                [
                    "<!-- ie-contribution:v1",
                    json.dumps(meta, ensure_ascii=False, indent=2),
                    "-->",
                ]
            )
        if body_extra:
            parts.append(body_extra)
        body = "\n".join(parts) + "\n"
    issue = {
        "number": number,
        "title": (meta or {}).get("title", "投稿"),
        "body": body,
        "user": {"login": "contributor"},
    }
    path = tmp_path / "issue.json"
    path.write_text(json.dumps(issue, ensure_ascii=False), encoding="utf-8")
    return path


def invoke(
    capsys,
    repo: Path,
    issue: Path,
    *,
    apply: bool = False,
    attachments_dir: Path | None = None,
    extra_args=(),
):
    argv = [
        "--repo-root",
        str(repo),
        "--issue",
        str(issue),
        "--json",
        "--apply" if apply else "--dry-run",
    ]
    if attachments_dir is not None:
        argv.extend(["--attachments-dir", str(attachments_dir)])
    argv.extend(extra_args)
    code = A.main(argv)
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert lines, "CLI 没有输出"
    return code, json.loads(lines[-1])


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def change_paths(result: dict) -> dict[str, str]:
    return {change["path"]: change["action"] for change in result["changes"]}


def error_codes(result: dict) -> list[str]:
    return [error["code"] for error in result.get("errors") or []]


def warning_codes(result: dict) -> list[str]:
    return [warning["code"] for warning in result.get("warnings") or []]


# ---------------------------------------------------------------------------
# material：4.1
# ---------------------------------------------------------------------------


def test_material_creates_section_and_is_idempotent(tmp_path, capsys):
    page_without_section = "# 运筹学Ⅰ\n\n## 课程学习内容\n\n运筹学内容。"  # 末尾也没有换行
    repo = make_repo(tmp_path, {PAGE_REL: page_without_section})
    attachments = make_attachments(tmp_path, {"期末试卷.pdf": b"%PDF-1.4 demo"})
    issue = make_issue(tmp_path, material_meta(), [ATT1])

    code, result = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 0
    assert result["ok"] is True
    assert result["kind"] == "material"
    assert result["target"] == PAGE_REL
    assert result["commit_message"] == "content: 2024 秋期末试卷 (#7)"
    assert change_paths(result) == {
        "IE-wiki/docs/" + PAGE_REL: "modify",
        "IE-wiki/docs/专业核心课/运筹学Ⅰ/期末试卷.pdf": "add",
    }
    assert result["attachments"] == [
        {"url": ATT1, "filename": "期末试卷.pdf", "bytes": len(b"%PDF-1.4 demo")}
    ]

    saved = repo / "IE-wiki" / "docs" / "专业核心课" / "运筹学Ⅰ" / "期末试卷.pdf"
    assert saved.read_bytes() == b"%PDF-1.4 demo"
    new_page = read_text(repo / "IE-wiki" / "docs" / PAGE_REL)
    assert new_page.endswith(
        "运筹学内容。\n\n## 补充材料\n\n- [2024 秋期末试卷](期末试卷.pdf)\n"
    )
    modify = next(c for c in result["changes"] if c["action"] == "modify")
    assert "+++" in modify["diff"] and "@@" in modify["diff"]
    add = next(c for c in result["changes"] if c["action"] == "add")
    assert add["diff"].startswith("new file:")

    # 连续 apply 第二次：幂等，changes 为空
    code2, result2 = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code2 == 0
    assert result2["ok"] is True
    assert result2["changes"] == []
    assert read_text(repo / "IE-wiki" / "docs" / PAGE_REL) == new_page


def test_material_creates_own_section_next_to_similar_heading(tmp_path, capsys):
    page = "# 应用统计Ⅰ\n\n## 补充资料\n\n- [旧链接](https://example.com/old)\n"
    repo = make_repo(tmp_path, {"专业核心课/应用统计Ⅰ/index.md": page})
    meta = material_meta(
        target="专业核心课/应用统计Ⅰ/index.md",
        course="应用统计Ⅰ",
        display_name="",
        links=["https://example.com/new"],
    )
    issue = make_issue(tmp_path, meta)

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    text = read_text(repo / "IE-wiki" / "docs" / "专业核心课" / "应用统计Ⅰ" / "index.md")
    # 原有的「## 补充资料」保留，另建契约要求的「## 补充材料」
    assert text.count("## 补充资料") == 1
    assert text.count("## 补充材料") == 1
    assert text.endswith("## 补充材料\n\n- [example.com](https://example.com/new)\n")


def test_material_inserts_before_next_heading(tmp_path, capsys):
    page = (
        "# 运筹学Ⅰ\n\n"
        "## 补充材料\n"
        "- [旧资料](旧.pdf)\n"
        "\n"
        "## 历年回忆卷\n"
        "- [回忆卷](卷.pdf)\n"
    )
    repo = make_repo(tmp_path, {PAGE_REL: page})
    attachments = make_attachments(tmp_path, {"试卷.pdf": b"new"})
    issue = make_issue(tmp_path, material_meta(display_name=""), [ATT1])

    code, result = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 0
    text = read_text(repo / "IE-wiki" / "docs" / PAGE_REL)
    old_line = text.index("- [旧资料](旧.pdf)")
    new_line = text.index("- [试卷.pdf](试卷.pdf)")
    next_heading = text.index("## 历年回忆卷")
    assert old_line < new_line < next_heading
    assert text.count("- [试卷.pdf](试卷.pdf)") == 1


def test_material_dedupes_same_name_different_content_and_reuses_identical(tmp_path, capsys):
    page = "# 运筹学Ⅰ\n\n## 补充材料\n"
    repo = make_repo(tmp_path, {PAGE_REL: page})
    target_dir = repo / "IE-wiki" / "docs" / "专业核心课" / "运筹学Ⅰ"
    (target_dir / "试卷.pdf").write_bytes(b"old-content")
    attachments = make_attachments(tmp_path, {"试卷.pdf": b"new-content"})
    issue = make_issue(tmp_path, material_meta(display_name=""), [ATT1])

    code, result = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 0
    assert (target_dir / "试卷.pdf").read_bytes() == b"old-content"
    assert (target_dir / "试卷-2.pdf").read_bytes() == b"new-content"
    assert result["attachments"][0]["filename"] == "试卷-2.pdf"
    text = read_text(repo / "IE-wiki" / "docs" / PAGE_REL)
    assert "- [试卷-2.pdf](试卷-2.pdf)" in text

    # 同名同内容 → 复用已有文件，不产生附件变更
    code2, result2 = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code2 == 0
    assert result2["changes"] == []
    assert result2["attachments"][0]["filename"] == "试卷-2.pdf"


def test_material_reuses_identical_existing_attachment(tmp_path, capsys):
    page = "# 运筹学Ⅰ\n\n## 补充材料\n"
    repo = make_repo(tmp_path, {PAGE_REL: page})
    target_dir = repo / "IE-wiki" / "docs" / "专业核心课" / "运筹学Ⅰ"
    (target_dir / "试卷.pdf").write_bytes(b"same")
    attachments = make_attachments(tmp_path, {"试卷.pdf": b"same"})
    issue = make_issue(tmp_path, material_meta(display_name=""), [ATT1])

    code, result = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 0
    # 只有页面清单行变化，附件本身不新增
    assert list(change_paths(result).values()) == ["modify"]
    assert result["attachments"][0]["filename"] == "试卷.pdf"


def test_material_link_only_and_domain_label(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    meta = material_meta(display_name="", links=["https://example.com/资料"])
    issue = make_issue(tmp_path, meta)

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    text = read_text(repo / "IE-wiki" / "docs" / PAGE_REL)
    assert "- [example.com](https://example.com/资料)" in text
    assert result["attachments"] == []


def test_material_link_only_uses_display_name_for_single_item(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    meta = material_meta(display_name="课程网站", links=["https://example.com/site"])
    issue = make_issue(tmp_path, meta)

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    assert "- [课程网站](https://example.com/site)" in read_text(
        repo / "IE-wiki" / "docs" / PAGE_REL
    )


def test_material_empty_is_rejected(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    issue = make_issue(tmp_path, material_meta(display_name="", links=[]))

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert result["ok"] is False
    assert "EMPTY_MATERIAL" in error_codes(result)
    assert read_text(repo / "IE-wiki" / "docs" / PAGE_REL) == PAGE


def test_material_attachment_url_order_and_dedupe(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    attachments = make_attachments(tmp_path, {"a.pdf": b"aaa", "b.pdf": b"bbb"})
    issue = make_issue(tmp_path, material_meta(display_name=""), [ATT1, ATT2, ATT1])

    code, result = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 0
    assert [(a["url"], a["filename"]) for a in result["attachments"]] == [
        (ATT1, "a.pdf"),
        (ATT2, "b.pdf"),
    ]
    text = read_text(repo / "IE-wiki" / "docs" / PAGE_REL)
    assert text.index("(a.pdf)") < text.index("(b.pdf)")
    assert text.count("(a.pdf)") == 1


def test_material_attachment_with_space_encodes_link_target(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    attachments = make_attachments(tmp_path, {"期末 试卷.pdf": b"pdf"})
    issue = make_issue(tmp_path, material_meta(display_name=""), [ATT1])

    code, _ = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 0
    text = read_text(repo / "IE-wiki" / "docs" / PAGE_REL)
    assert "期末%20试卷.pdf" in text
    assert (repo / "IE-wiki" / "docs" / "专业核心课" / "运筹学Ⅰ" / "期末 试卷.pdf").is_file()


def test_material_ignores_external_attachment_links(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    attachments = make_attachments(tmp_path, {"试卷.pdf": b"pdf"})
    issue = make_issue(
        tmp_path,
        material_meta(display_name=""),
        [ATT1],
        external_urls=["https://example.com/file.pdf"],
    )

    code, result = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 0
    assert len(result["attachments"]) == 1
    assert "IGNORED_EXTERNAL_LINK" in warning_codes(result)
    assert not (repo / "IE-wiki" / "docs" / "专业核心课" / "运筹学Ⅰ" / "file.pdf").exists()


def test_material_too_large_attachment_rejected(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    attachments = make_attachments(tmp_path, {})
    big = attachments / "big.pdf"
    with open(big, "wb") as handle:
        handle.truncate(S.MAX_ATTACHMENT_BYTES + 1)
    issue = make_issue(tmp_path, material_meta(display_name=""), [ATT1])

    code, result = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 2
    assert "ATTACHMENT_TOO_LARGE" in error_codes(result)
    assert read_text(repo / "IE-wiki" / "docs" / PAGE_REL) == PAGE


def test_material_forbidden_extension_rejected(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    attachments = make_attachments(tmp_path, {"evil.exe": b"MZ"})
    issue = make_issue(tmp_path, material_meta(display_name=""), [ATT1])

    code, result = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 2
    assert "ATTACHMENT_FORBIDDEN" in error_codes(result)
    assert read_text(repo / "IE-wiki" / "docs" / PAGE_REL) == PAGE


def test_material_attachments_dir_insufficient_files(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    attachments = make_attachments(tmp_path, {"a.pdf": b"a"})
    issue = make_issue(tmp_path, material_meta(display_name=""), [ATT1, ATT2])

    code, result = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 2
    assert "ATTACHMENT_SOURCE_MISSING" in error_codes(result)


def test_dry_run_does_not_write(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    attachments = make_attachments(tmp_path, {"试卷.pdf": b"pdf"})
    issue = make_issue(tmp_path, material_meta(), [ATT1])

    code, result = invoke(capsys, repo, issue, attachments_dir=attachments)
    assert code == 0
    assert result["ok"] is True
    assert result["changes"], "dry-run 应给出变更预览"
    assert read_text(repo / "IE-wiki" / "docs" / PAGE_REL) == PAGE
    assert not (repo / "IE-wiki" / "docs" / "专业核心课" / "运筹学Ⅰ" / "试卷.pdf").exists()


# ---------------------------------------------------------------------------
# append：4.2
# ---------------------------------------------------------------------------


def append_meta(**overrides) -> dict:
    meta = material_meta(**overrides)
    meta.update(
        {
            "kind": "append",
            "title": "补充说明",
            "display_name": "",
            "links": [],
            "content": "补充说明文本。",
            "replacements": [],
        }
    )
    meta.update(overrides)
    return meta


def test_append_to_page_end_with_marker_and_idempotent(tmp_path, capsys):
    page = "# 运筹学Ⅰ\n\n内容"  # 末尾没有换行
    repo = make_repo(tmp_path, {PAGE_REL: page})
    issue = make_issue(tmp_path, append_meta())

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    text = read_text(repo / "IE-wiki" / "docs" / PAGE_REL)
    assert text.endswith("内容\n\n补充说明文本。\n<!-- ie-submission:issue-7 -->\n")

    code2, result2 = invoke(capsys, repo, issue, apply=True)
    assert code2 == 0
    assert result2["changes"] == []
    assert "ALREADY_APPLIED" in warning_codes(result2)


def test_append_into_section(tmp_path, capsys):
    page = (
        "# 运筹学Ⅰ\n\n"
        "## 考核标准\n"
        "出勤 10%。\n"
        "\n"
        "## 推荐教材\n"
        "某教材。\n"
    )
    repo = make_repo(tmp_path, {PAGE_REL: page})
    issue = make_issue(tmp_path, append_meta(section="考核标准", content="期末 90%。"))

    code, _ = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    text = read_text(repo / "IE-wiki" / "docs" / PAGE_REL)
    assert text.index("出勤 10%。") < text.index("期末 90%。") < text.index("## 推荐教材")
    assert text.index("期末 90%。") < text.index("<!-- ie-submission:issue-7 -->")
    assert text.index("<!-- ie-submission:issue-7 -->") < text.index("## 推荐教材")

    code2, result2 = invoke(capsys, repo, issue, apply=True)
    assert code2 == 0
    assert result2["changes"] == []


def test_append_section_not_found(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    issue = make_issue(tmp_path, append_meta(section="不存在的小节"))

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "SECTION_NOT_FOUND" in error_codes(result)
    assert read_text(repo / "IE-wiki" / "docs" / PAGE_REL) == PAGE


def test_append_section_ambiguous(tmp_path, capsys):
    page = "# 运筹学Ⅰ\n\n## 考核标准\n甲。\n\n## 考核标准\n乙。\n"
    repo = make_repo(tmp_path, {PAGE_REL: page})
    issue = make_issue(tmp_path, append_meta(section="考核标准"))

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "BAD_SECTION" in error_codes(result)


def test_append_empty_content_rejected(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    issue = make_issue(tmp_path, append_meta(content="   "))

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "BAD_CONTENT" in error_codes(result)


# ---------------------------------------------------------------------------
# edit：4.3
# ---------------------------------------------------------------------------


def edit_meta(old: str, new: str, **overrides) -> dict:
    meta = material_meta(**overrides)
    meta.update(
        {
            "kind": "edit",
            "title": "纠错",
            "display_name": "",
            "links": [],
            "content": "",
            "replacements": [{"old": old, "new": new}],
        }
    )
    meta.update(overrides)
    return meta


def test_edit_applies_and_is_idempotent(tmp_path, capsys):
    page = "# 运筹学Ⅰ\n\n任课老师：张老师。\n"
    repo = make_repo(tmp_path, {PAGE_REL: page})
    issue = make_issue(
        tmp_path,
        edit_meta("任课老师：张老师。", "任课老师：李老师。"),
    )

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    text = read_text(repo / "IE-wiki" / "docs" / PAGE_REL)
    assert "李老师" in text and "张老师" not in text

    code2, result2 = invoke(capsys, repo, issue, apply=True)
    assert code2 == 0
    assert result2["changes"] == []
    assert "ALREADY_APPLIED" in warning_codes(result2)


def test_edit_old_not_found(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    issue = make_issue(tmp_path, edit_meta("页面中不存在的一段原文。", "新的内容。"))

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "REPLACEMENT_NOT_FOUND" in error_codes(result)
    assert "第 1 组" in result["errors"][0]["message"]
    assert read_text(repo / "IE-wiki" / "docs" / PAGE_REL) == PAGE


def test_edit_old_ambiguous(tmp_path, capsys):
    page = "# 运筹学Ⅰ\n\n任课老师：张老师。\n\n任课老师：张老师。\n"
    repo = make_repo(tmp_path, {PAGE_REL: page})
    issue = make_issue(tmp_path, edit_meta("任课老师：张老师。", "任课老师：李老师。"))

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "REPLACEMENT_AMBIGUOUS" in error_codes(result)
    assert "第 1 组" in result["errors"][0]["message"]
    assert read_text(repo / "IE-wiki" / "docs" / PAGE_REL) == page


def test_edit_is_atomic_no_partial_write(tmp_path, capsys):
    page = "# 运筹学Ⅰ\n\n任课老师：张老师。\n"
    repo = make_repo(tmp_path, {PAGE_REL: page})
    meta = edit_meta("任课老师：张老师。", "任课老师：李老师。")
    meta["replacements"] = [
        {"old": "任课老师：张老师。", "new": "任课老师：李老师。"},
        {"old": "页面中不存在的一段原文。", "new": "新的内容。"},
    ]
    issue = make_issue(tmp_path, meta)

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "REPLACEMENT_NOT_FOUND" in error_codes(result)
    # 第一组虽然可替换，但整单失败 → 不落盘
    assert read_text(repo / "IE-wiki" / "docs" / PAGE_REL) == page


def test_edit_old_too_short(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    issue = make_issue(tmp_path, edit_meta("短", "长一点点"))

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "BAD_REPLACEMENT" in error_codes(result)


# ---------------------------------------------------------------------------
# new-course：4.4
# ---------------------------------------------------------------------------


def new_course_meta(**overrides) -> dict:
    meta = {
        "version": 1,
        "kind": "new-course",
        "target": "",
        "course": "人工智能导论",
        "category": "专业核心课",
        "title": "新增人工智能导论",
        "display_name": "",
        "section": "",
        "notes": "",
        "links": [],
        "content": "讲授搜索、机器学习基础。",
        "replacements": [],
    }
    meta.update(overrides)
    return meta


def test_new_course_creates_page_and_updates_nav(tmp_path, capsys):
    repo = make_repo(tmp_path, {})
    issue = make_issue(tmp_path, new_course_meta())

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    page_path = repo / "IE-wiki" / "docs" / "专业核心课" / "人工智能导论" / "index.md"
    assert page_path.is_file()
    text = read_text(page_path)
    assert text.startswith("---\nabbrs:\n    - 人工智能导论\n---\n")
    assert "# 人工智能导论\n" in text
    assert "## 课程学习内容\n\n讲授搜索、机器学习基础。\n" in text
    assert "## 任课老师\n\n（待补充）" in text
    assert text.endswith("## 补充材料\n")

    nav = yaml.safe_load(read_text(repo / "IE-wiki" / "mkdocs.yml"))["nav"]
    assert {"人工智能导论": "专业核心课/人工智能导论/index.md"} in nav[1]["专业核心课"]

    assert change_paths(result) == {
        "IE-wiki/docs/专业核心课/人工智能导论/index.md": "add",
        "IE-wiki/mkdocs.yml": "modify",
    }

    # 已存在同名页面 → DUPLICATE_PAGE
    code2, result2 = invoke(capsys, repo, issue, apply=True)
    assert code2 == 2
    assert "DUPLICATE_PAGE" in error_codes(result2)
    # 重跑失败不能重复写入 nav
    assert read_text(repo / "IE-wiki" / "mkdocs.yml").count("    - 人工智能导论:") == 1


def test_new_course_default_content(tmp_path, capsys):
    repo = make_repo(tmp_path, {})
    issue = make_issue(tmp_path, new_course_meta(content=""))

    code, _ = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    text = read_text(repo / "IE-wiki" / "docs" / "专业核心课" / "人工智能导论" / "index.md")
    assert "## 课程学习内容\n\n（待补充）\n" in text


def test_new_course_appends_missing_category_block(tmp_path, capsys):
    repo = make_repo(tmp_path, {})
    issue = make_issue(tmp_path, new_course_meta(category="其他", course="创新创业"))

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    nav = yaml.safe_load(read_text(repo / "IE-wiki" / "mkdocs.yml"))["nav"]
    assert {"创新创业": "其他/创新创业/index.md"} in nav[-1]["其他"]
    assert (repo / "IE-wiki" / "docs" / "其他" / "创新创业" / "index.md").is_file()


def test_new_course_nav_parse_failure_does_not_write(tmp_path, capsys):
    broken_mkdocs = (
        "site_name: 测试站点\n"
        "nav:\n"
        "  - 专业核心课:\n"
        "    - 运筹学Ⅰ: 专业核心课/运筹学Ⅰ/index.md\n"
        "  - [broken\n"
    )
    repo = make_repo(tmp_path, {}, mkdocs=broken_mkdocs)
    issue = make_issue(tmp_path, new_course_meta())

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 3
    assert "NAV_UPDATE_FAILED" in error_codes(result)
    assert not (repo / "IE-wiki" / "docs" / "专业核心课" / "人工智能导论").exists()
    assert read_text(repo / "IE-wiki" / "mkdocs.yml") == broken_mkdocs


def test_new_course_missing_nav_block(tmp_path, capsys):
    repo = make_repo(tmp_path, {}, mkdocs="site_name: 测试站点\n")
    issue = make_issue(tmp_path, new_course_meta())

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 3
    assert "NAV_UPDATE_FAILED" in error_codes(result)
    assert not (repo / "IE-wiki" / "docs" / "专业核心课" / "人工智能导论").exists()


def test_new_course_bad_category(tmp_path, capsys):
    repo = make_repo(tmp_path, {})
    issue = make_issue(tmp_path, new_course_meta(category="不存在的分类"))

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "BAD_CATEGORY" in error_codes(result)


def test_new_course_course_name_with_slash_rejected(tmp_path, capsys):
    repo = make_repo(tmp_path, {})
    issue = make_issue(tmp_path, new_course_meta(course="C/C++"))

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "BAD_COURSE" in error_codes(result)


def test_material_preserves_crlf_and_uses_existing_section(tmp_path, capsys):
    """真实仓库页面是 CRLF：定位小节要按逻辑行匹配，写回要保持原换行风格。"""

    page = (
        "# 运筹学Ⅰ\r\n"
        "\r\n"
        "## 补充材料\r\n"
        "- [旧资料](旧.pdf)\r\n"
        "\r\n"
        "## 历年回忆卷\r\n"
        "- [卷](卷.pdf)\r\n"
    )
    repo = make_repo(tmp_path, {PAGE_REL: page})
    attachments = make_attachments(tmp_path, {"试卷.pdf": b"pdf"})
    issue = make_issue(tmp_path, material_meta(display_name=""), [ATT1])

    code, result = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 0
    assert change_paths(result)["IE-wiki/docs/" + PAGE_REL] == "modify"
    raw = (repo / "IE-wiki" / "docs" / PAGE_REL).read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "写回后应保持全 CRLF"
    text = raw.decode("utf-8")
    assert text.count("## 补充材料") == 1, "不应重复创建小节"
    assert (
        text.index("- [旧资料](旧.pdf)")
        < text.index("- [试卷.pdf](试卷.pdf)")
        < text.index("## 历年回忆卷")
    )


def test_material_crlf_page_without_section_creates_crlf_section(tmp_path, capsys):
    page = "# 运筹学Ⅰ\r\n\r\n## 课程学习内容\r\n\r\n内容。\r\n"
    repo = make_repo(tmp_path, {PAGE_REL: page})
    attachments = make_attachments(tmp_path, {"试卷.pdf": b"pdf"})
    issue = make_issue(tmp_path, material_meta(display_name=""), [ATT1])

    code, _ = invoke(capsys, repo, issue, apply=True, attachments_dir=attachments)
    assert code == 0
    raw = (repo / "IE-wiki" / "docs" / PAGE_REL).read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n")
    assert b"## \xe8\xa1\xa5\xe5\x85\x85\xe6\x9d\x90\xe6\x96\x99\r\n\r\n- [" in raw


def test_append_crlf_page_preserves_style(tmp_path, capsys):
    page = "# 运筹学Ⅰ\r\n\r\n内容\r\n"
    repo = make_repo(tmp_path, {PAGE_REL: page})
    issue = make_issue(tmp_path, append_meta())

    code, _ = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    raw = (repo / "IE-wiki" / "docs" / PAGE_REL).read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n")
    assert b"\r\n\r\n\xe8\xa1\xa5\xe5\x85\x85\xe8\xaf\xb4\xe6\x98\x8e\xe6\x96\x87\xe6\x9c\xac\xe3\x80\x82\r\n" in raw
    assert b"<!-- ie-submission:issue-7 -->\r\n" in raw


def test_edit_crlf_page(tmp_path, capsys):
    page = "# 运筹学Ⅰ\r\n\r\n任课老师：张老师。\r\n"
    repo = make_repo(tmp_path, {PAGE_REL: page})
    issue = make_issue(tmp_path, edit_meta("任课老师：张老师。", "任课老师：李老师。"))

    code, _ = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    raw = (repo / "IE-wiki" / "docs" / PAGE_REL).read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n")
    assert "任课老师：李老师。" in raw.decode("utf-8")


def test_new_course_page_is_lf(tmp_path, capsys):
    repo = make_repo(tmp_path, {})
    issue = make_issue(tmp_path, new_course_meta())

    code, _ = invoke(capsys, repo, issue, apply=True)
    assert code == 0
    raw = (repo / "IE-wiki" / "docs" / "专业核心课" / "人工智能导论" / "index.md").read_bytes()
    assert b"\r\n" not in raw, "新增文件必须是 LF"


# ---------------------------------------------------------------------------
# 路径安全 / 元数据校验
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target",
    [
        "../escape.md",
        "../../etc/passwd.md",
        "/etc/passwd.md",
        "专业核心课\\..\\x.md",
        "%2e%2e/sneaky.md",
        "专业核心课/../../sneaky.md",
        "专业核心课/运筹学Ⅰ/index.txt",
        "C:/windows/x.md",
        "专业核心课//empty-segment.md",
    ],
)
def test_path_traversal_and_unsafe_targets_rejected(tmp_path, capsys, target):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    meta = material_meta(target=target, display_name="", links=["https://example.com/ok"])
    issue = make_issue(tmp_path, meta)

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "BAD_TARGET" in error_codes(result)
    assert not list(tmp_path.rglob("sneaky.md"))
    assert not list(tmp_path.rglob("escape.md"))


def test_target_not_found(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    meta = material_meta(target="专业核心课/不存在/index.md", links=["https://example.com/ok"])
    issue = make_issue(tmp_path, meta)

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "TARGET_NOT_FOUND" in error_codes(result)


def test_no_metadata_ignored(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    issue = make_issue(tmp_path, None, include_marker=False, raw_body="普通 Issue，没有投稿标记。\n")

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert result["ok"] is False
    assert "NO_METADATA" in error_codes(result)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"version": 2}, "BAD_VERSION"),
        ({"version": True}, "BAD_VERSION"),
        ({"kind": "hack"}, "BAD_KIND"),
        ({"title": ""}, "BAD_TITLE"),
        ({"course": ""}, "BAD_COURSE"),
        ({"links": ["ftp://example.com/a"]}, "BAD_LINK"),
        ({"links": ["https://example.com/" + str(i) for i in range(11)]}, "BAD_LINK"),
    ],
)
def test_bad_metadata_fields(tmp_path, capsys, overrides, expected):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    base_links = ["https://example.com/ok"]
    meta = material_meta(display_name="", links=base_links)
    meta.update(overrides)
    issue = make_issue(tmp_path, meta)

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert expected in error_codes(result)


def test_bad_json_marker(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    body = "<!-- ie-contribution:v1\n{not valid json}\n-->\n"
    issue = make_issue(tmp_path, None, include_marker=False, raw_body=body)

    code, result = invoke(capsys, repo, issue, apply=True)
    assert code == 2
    assert "BAD_JSON" in error_codes(result)


def test_issue_without_number(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    issue = make_issue(tmp_path, material_meta(), [ATT1])
    data = json.loads(read_text(issue))
    del data["number"]
    issue.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    code, result = invoke(capsys, repo, issue)
    assert code == 2
    assert "ISSUE_INVALID" in error_codes(result)


# ---------------------------------------------------------------------------
# 解析器 / 工具函数单元测试
# ---------------------------------------------------------------------------


def test_parse_metadata_takes_last_marker():
    body = (
        "<!-- ie-contribution:v1 {\"version\": 1, \"kind\": \"material\", \"title\": \"旧\"} -->\n"
        "中间内容\n"
        "<!-- ie-contribution:v1 {\"version\": 1, \"kind\": \"material\", \"title\": \"新\"} -->\n"
    )
    meta = S.parse_metadata(body)
    assert meta is not None
    assert meta["title"] == "新"
    assert S.parse_metadata("没有标记") is None


def test_parse_metadata_invalid_json_raises():
    with pytest.raises(S.SubmissionError) as excinfo:
        S.parse_metadata("<!-- ie-contribution:v1 {bad} -->")
    assert excinfo.value.code == "BAD_JSON"


def test_extract_attachments_order_and_forms():
    body = "\n".join([ATT1, ATT2, ATT1, REPO_ASSET])
    attachments = S.extract_attachments(body)
    assert [a.url for a in attachments] == [ATT1, ATT2, REPO_ASSET]
    assert attachments[0].kind == "user-attachments"
    assert attachments[2].owner == "NJUWallSpider"
    assert attachments[2].kind == "repo-assets"


def test_ignored_external_links_only_inside_attachment_section():
    body = (
        "## 附件\n"
        f"{ATT1}\n"
        "https://example.com/a.pdf\n"
        "\n"
        "## 链接\n"
        "https://example.com/b\n"
        "<!-- ie-contribution:v1 {\"version\": 1} -->\n"
    )
    ignored = S.ignored_external_links(body)
    assert ignored == ["https://example.com/a.pdf"]


def test_sanitize_filename():
    assert S.sanitize_filename('a/b:c?.pdf') == "a_b_c_.pdf"
    assert S.sanitize_filename("  期末 试卷.pdf  ") == "期末 试卷.pdf"
    long_name = "长" * 100 + ".pdf"
    cleaned = S.sanitize_filename(long_name)
    assert len(cleaned) <= 80
    assert cleaned.endswith(".pdf")
    assert S.sanitize_filename("a\x01b.pdf") == "a_b.pdf"
    assert S.sanitize_filename(".") == "attachment"


def test_markdown_link_helpers():
    assert S.markdown_link_target("期末 试卷(1).pdf") == "期末%20试卷%281%29.pdf"
    assert S.markdown_link_label("[草稿]试卷") == "\\[草稿\\]试卷"
    assert S.link_display_name("https://example.com/a/b") == "example.com"


def test_check_target_path_allows_normal_path():
    assert S.check_target_path(PAGE_REL) is None
    assert S.check_target_path("必学工具/Git.md") is None


# ---------------------------------------------------------------------------
# 附件下载（urllib，本地 HTTP 服务器）
# ---------------------------------------------------------------------------


class _AttachmentHandler(http.server.BaseHTTPRequestHandler):
    records: list[dict] = []
    redirect_target = ""

    def do_GET(self):  # noqa: N802
        type(self).records.append(
            {"path": self.path, "authorization": self.headers.get("Authorization")}
        )
        if self.path == "/assets/redirect":
            self.send_response(302)
            self.send_header("Location", type(self).redirect_target)
            self.end_headers()
        elif self.path == "/final/file.pdf":
            data = b"%PDF-1.4 from-server"
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", 'attachment; filename="server-file.pdf"')
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/big":
            self.send_response(200)
            self.send_header("Content-Length", str(A.MAX_ATTACHMENT_BYTES + 1))
            self.end_headers()
        elif self.path == "/needs-anon":
            # 模拟不接受 Bearer token 的 user-attachments 链接
            if self.headers.get("Authorization"):
                self.send_response(401)
                self.end_headers()
            else:
                data = b"anon-ok"
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition", 'attachment; filename="anon.pdf"')
                self.end_headers()
                self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # noqa: D102
        pass


@pytest.fixture()
def attachment_servers():
    servers = [
        http.server.HTTPServer(("127.0.0.1", 0), _AttachmentHandler),
        http.server.HTTPServer(("127.0.0.1", 0), _AttachmentHandler),
    ]
    threads = [
        threading.Thread(target=server.serve_forever, daemon=True) for server in servers
    ]
    for thread in threads:
        thread.start()
    _AttachmentHandler.records = []
    _AttachmentHandler.redirect_target = ""
    bases = [f"http://127.0.0.1:{server.server_port}" for server in servers]
    try:
        yield bases
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=5)


def test_download_attachment_follows_redirect_and_sends_bearer(attachment_servers):
    base = attachment_servers[0]
    _AttachmentHandler.redirect_target = base + "/final/file.pdf"

    data, filename = A.download_attachment(
        base + "/assets/redirect", token="secret-token", asset_id="abc"
    )
    assert data == b"%PDF-1.4 from-server"
    assert filename == "server-file.pdf"
    assert _AttachmentHandler.records[0]["authorization"] == "Bearer secret-token"


def test_download_attachment_strips_auth_when_host_changes(attachment_servers):
    first, second = attachment_servers
    _AttachmentHandler.redirect_target = second + "/final/file.pdf"

    data, _ = A.download_attachment(first + "/assets/redirect", token="secret-token")
    assert data == b"%PDF-1.4 from-server"
    assert _AttachmentHandler.records[0]["authorization"] == "Bearer secret-token"
    # 跨 host（这里是跨端口）重定向后不再携带 token
    assert _AttachmentHandler.records[1]["authorization"] is None


def test_download_attachment_too_large(attachment_servers):
    with pytest.raises(S.SubmissionError) as excinfo:
        A.download_attachment(attachment_servers[0] + "/big", token="")
    assert excinfo.value.code == "ATTACHMENT_TOO_LARGE"


def test_download_attachment_http_error(attachment_servers):
    with pytest.raises(S.SubmissionError) as excinfo:
        A.download_attachment(attachment_servers[0] + "/missing", token="")
    assert excinfo.value.code == "ATTACHMENT_DOWNLOAD_FAILED"
    assert "404" in excinfo.value.message


def test_attachment_download_retries_without_token(attachment_servers, monkeypatch):
    base = attachment_servers[0]
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    attachment = S.Attachment(url=base + "/needs-anon", asset_id="x")
    validation = S.ValidationResult(
        repo_root=Path("."),
        docs_root=Path("."),
        mkdocs_path=Path("."),
        attachments=[attachment],
    )
    args = A.build_parser().parse_args(["--issue", "unused.json"])
    warnings: list[dict] = []

    payloads = A._load_attachment_payloads(validation, args, warnings)
    assert payloads[0][1] == "anon.pdf"
    assert payloads[0][2] == b"anon-ok"
    assert any(w["code"] == "ATTACHMENT_ANONYMOUS_RETRY" for w in warnings)


def test_filename_from_response_variants():
    message = email.message.Message()
    message["Content-Disposition"] = (
        "attachment; filename*=UTF-8''%E6%9C%9F%E6%9C%AB%E8%AF%95%E5%8D%B7.pdf"
    )
    assert A._filename_from_response(message, "https://x/y", "id") == "期末试卷.pdf"

    plain = email.message.Message()
    plain["Content-Disposition"] = 'attachment; filename="plain.pdf"'
    assert A._filename_from_response(plain, "https://x/y", "id") == "plain.pdf"

    bare = email.message.Message()
    bare["Content-Disposition"] = "attachment; filename=bare.pdf"
    assert A._filename_from_response(bare, "https://x/y", "id") == "bare.pdf"

    fallback = email.message.Message()
    assert A._filename_from_response(fallback, "https://x/y/final.pdf", "id") == "final.pdf"
    assert A._filename_from_response(fallback, "https://x/y/", "id") == "attachment-id"


# ---------------------------------------------------------------------------
# CLI 契约
# ---------------------------------------------------------------------------


def test_cli_help_via_subprocess():
    completed = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "apply_submission.py"), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0
    for option in ("--repo-root", "--issue", "--dry-run", "--apply", "--json", "--attachments-dir", "--token-env"):
        assert option in completed.stdout


def test_json_output_shape(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    attachments = make_attachments(tmp_path, {"试卷.pdf": b"pdf"})
    issue = make_issue(tmp_path, material_meta(), [ATT1])

    code, result = invoke(capsys, repo, issue, attachments_dir=attachments)
    assert code == 0
    assert set(result) == {
        "ok",
        "issue",
        "kind",
        "title",
        "target",
        "changes",
        "attachments",
        "commit_message",
        "warnings",
        "errors",
    }
    for change in result["changes"]:
        assert set(change) == {"path", "action", "diff"}
    assert result["errors"] == []


def test_human_output_contains_diff(tmp_path, capsys):
    repo = make_repo(tmp_path, {PAGE_REL: PAGE})
    issue = make_issue(tmp_path, material_meta(display_name="", links=["https://example.com/x"]))
    code = A.main(["--repo-root", str(repo), "--issue", str(issue)])
    captured = capsys.readouterr().out
    assert code == 0
    assert "变更" in captured
    assert "+++" in captured


def test_render_preview_markdown():
    success = {
        "ok": True,
        "issue": 7,
        "kind": "material",
        "title": "2024 秋期末试卷",
        "target": PAGE_REL,
        "changes": [
            {
                "path": "IE-wiki/docs/" + PAGE_REL,
                "action": "modify",
                "diff": "--- a/x.md\n+++ b/x.md\n@@ -1 +1 @@\n-a\n+b\n",
            }
        ],
        "attachments": [{"url": ATT1, "filename": "试卷.pdf", "bytes": 1234}],
        "commit_message": "content: 2024 秋期末试卷 (#7)",
        "warnings": [{"code": "IGNORED_EXTERNAL_LINK", "message": "忽略外部链接"}],
        "errors": [],
    }
    body = A.render_preview_markdown(success)
    assert body.startswith("<!-- ie-preview -->")
    assert "<details>" in body
    assert "```diff" in body
    assert "content: 2024 秋期末试卷 (#7)" in body
    assert "审核" in body

    failure = {
        "ok": False,
        "issue": 8,
        "kind": "material",
        "title": "",
        "target": "",
        "changes": [],
        "attachments": [],
        "commit_message": "",
        "warnings": [],
        "errors": [{"code": "BAD_TARGET", "message": "target 路径不安全"}],
    }
    failed_body = A.render_preview_markdown(failure)
    assert "校验失败" in failed_body
    assert "`BAD_TARGET`" in failed_body

    truncated = A.render_preview_markdown(
        success,
        max_diff_chars=10,
        max_total_chars=100000,
    )
    assert "已截断" in truncated
