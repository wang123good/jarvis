#!/usr/bin/env python3
"""Read-only health report for the JARVIS Brain Markdown knowledge base."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


SKIP_DIRS = {".git", ".obsidian", ".trash"}
WIKILINK_RE = re.compile(r"(!?)\[\[([^\]]+)\]\]")
KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
VALID_TYPES = {
    "index",
    "topic",
    "reference",
    "synthesis",
    "decision",
    "task-summary",
    "rule",
    "draft",
    "conversation",
    "daily-report",
    "weekly-report",
    "template",
}
VALID_STATUS = {"inbox", "review", "active", "superseded", "archived", "rejected"}
CORE_FIELDS = ("title", "type", "status", "updated")


def parse_scalar(raw: str):
    value = raw.strip()
    if value in {"", "null", "~"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [item.strip().strip("\"'") for item in inner.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def split_frontmatter(text: str) -> tuple[dict, str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized
    closing = normalized.find("\n---", 4)
    if closing == -1:
        return {}, normalized
    header = normalized[4:closing]
    body_start = closing + 4
    if body_start < len(normalized) and normalized[body_start : body_start + 1] == "\n":
        body_start += 1
    data = {}
    for line in header.splitlines():
        if line.startswith((" ", "\t")):
            continue
        match = KEY_RE.match(line)
        if match:
            data[match.group(1)] = parse_scalar(match.group(2))
    return data, normalized[body_start:]


def mask_code(text: str) -> str:
    chars = list(text)
    in_fence = False
    marker = None
    lines = text.splitlines(keepends=True)
    offset = 0
    for line in lines:
        stripped = line.lstrip()
        fenced = stripped.startswith(("```", "~~~"))
        if fenced:
            current = stripped[:3]
            if not in_fence:
                in_fence, marker = True, current
            elif current == marker:
                in_fence, marker = False, None
        if fenced or in_fence:
            for index in range(offset, offset + len(line)):
                if chars[index] not in "\r\n":
                    chars[index] = " "
        else:
            index = offset
            while index < offset + len(line):
                if chars[index] == "`":
                    end_run = index
                    while end_run < offset + len(line) and chars[end_run] == "`":
                        end_run += 1
                    delimiter = "`" * (end_run - index)
                    close = text.find(delimiter, end_run)
                    if close != -1 and "\n" not in text[end_run:close]:
                        for blank_index in range(index, close + len(delimiter)):
                            if chars[blank_index] not in "\r\n":
                                chars[blank_index] = " "
                        index = close + len(delimiter)
                        continue
                index += 1
        offset += len(line)
    return "".join(chars)


def resolve(source: str, target: str, path_index, stem_index, all_index) -> tuple[str, str | None]:
    raw = target.strip()
    if raw.startswith("!"):
        raw = raw[1:]
    raw = raw.split("|", 1)[0].split("#", 1)[0].strip().rstrip("\\").lstrip("/")
    if not raw:
        return "self", source
    no_ext = raw[:-3] if raw.lower().endswith(".md") else raw
    for candidate in (no_ext,):
        exact = sorted(set(path_index.get(candidate, [])))
        if len(exact) == 1:
            return "resolved-note", exact[0]
        if len(exact) > 1:
            return "ambiguous-note", None
    parent = Path(source).parent.as_posix()
    if parent != ".":
        relative = os.path.normpath(os.path.join(parent, no_ext)).replace("\\", "/")
        matches = sorted(set(path_index.get(relative, [])))
        if len(matches) == 1:
            return "resolved-note", matches[0]
        if len(matches) > 1:
            return "ambiguous-note", None
    matches = sorted(set(stem_index.get(Path(no_ext).name.casefold(), [])))
    if len(matches) == 1:
        return "resolved-note", matches[0]
    if len(matches) > 1:
        return "ambiguous-note", None
    exact_attachment = sorted(set(all_index.get(raw.casefold(), [])))
    if len(exact_attachment) == 1:
        return "resolved-attachment", exact_attachment[0]
    attachment_matches = sorted(
        set(all_index.get(raw.casefold(), [])) | set(all_index.get(Path(raw).name.casefold(), []))
    )
    if len(attachment_matches) == 1:
        return "resolved-attachment", attachment_matches[0]
    if len(attachment_matches) > 1:
        return "ambiguous-attachment", None
    return "unresolved", None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-assets-folder", default="99 附件", help="Preserve raw documents; validate their links but not Brain note properties")
    args = parser.parse_args()
    vault = Path(args.vault).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError(f"Output already exists: {output}")

    markdown_paths, all_paths = [], []
    for current, dirs, files in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        current_path = Path(current)
        for name in sorted(files):
            path = current_path / name
            all_paths.append(path)
            if name.lower().endswith(".md"):
                markdown_paths.append(path)
    md_rels = [path.relative_to(vault).as_posix() for path in markdown_paths]
    all_rels = [path.relative_to(vault).as_posix() for path in all_paths]
    path_index, stem_index, all_index = defaultdict(list), defaultdict(list), defaultdict(list)
    for rel in md_rels:
        no_ext = rel[:-3]
        path_index[no_ext].append(rel)
        stem_index[Path(no_ext).name.casefold()].append(rel)
    md_set = set(md_rels)
    for rel in all_rels:
        if rel not in md_set:
            all_index[rel.casefold()].append(rel)
            all_index[Path(rel).name.casefold()].append(rel)

    properties, missing_core, invalid_fields, expired = [], [], [], []
    raw_asset_markdown = []
    links, outbound = [], defaultdict(set)
    today = date.today().isoformat()
    for path, rel in zip(markdown_paths, md_rels):
        text = path.read_text(encoding="utf-8-sig")
        fm, body = split_frontmatter(text)
        raw_asset = rel.startswith(args.raw_assets_folder.rstrip("/") + "/")
        if raw_asset:
            raw_asset_markdown.append(rel)
        else:
            properties.append({"path": rel, "frontmatter": fm})
        for key in (() if raw_asset else CORE_FIELDS):
            if not fm.get(key):
                missing_core.append({"path": rel, "field": key})
        if not raw_asset and fm.get("type") not in VALID_TYPES:
            invalid_fields.append({"path": rel, "field": "type", "value": fm.get("type")})
        if not raw_asset and fm.get("status") not in VALID_STATUS:
            invalid_fields.append({"path": rel, "field": "status", "value": fm.get("status")})
        review_after = fm.get("review_after")
        if fm.get("status") == "active" and isinstance(review_after, str) and review_after < today:
            expired.append({"path": rel, "review_after": review_after})
        masked = mask_code(body)
        for match in WIKILINK_RE.finditer(masked):
            raw = body[match.start() : match.end()]
            target = match.group(2)
            kind, resolved = resolve(rel, target, path_index, stem_index, all_index)
            links.append(
                {
                    "source": rel,
                    "raw": raw,
                    "target": target,
                    "resolution": kind,
                    "resolved_target": resolved,
                }
            )
            if resolved:
                outbound[rel].add(resolved)
    inbound = defaultdict(set)
    for link in links:
        if link["resolved_target"]:
            inbound[link["resolved_target"]].add(link["source"])
    unresolved = [
        link
        for link in links
        if link["resolution"]
        in {"unresolved", "ambiguous-note", "unresolved-md-link", "ambiguous-attachment"}
    ]
    fm_by_path = {item["path"]: item["frontmatter"] for item in properties}
    active_without_evidence = [
        path
        for path, fm in fm_by_path.items()
        if fm.get("status") == "active"
        and fm.get("type") not in {"index", "template", "task-summary", "conversation", "draft"}
        and not fm.get("source")
        and not fm.get("evidence")
        and fm.get("evidence_prompt_waived") not in (True, "true")
    ]
    business_orphans = [
        path
        for path, fm in fm_by_path.items()
        if fm.get("type") not in {"template", "index", "conversation", "draft"}
        and not inbound.get(path)
        and not outbound.get(path)
    ]
    superseded_issues = [
        path
        for path, fm in fm_by_path.items()
        if fm.get("status") == "superseded" and not fm.get("superseded_by")
    ]
    duplicate_stems = {
        stem: sorted(set(paths)) for stem, paths in stem_index.items() if len(set(paths)) > 1
    }
    report = {
        "schema_version": 1,
        "vault": str(vault),
        "generated_at": date.today().isoformat(),
        "markdown_count": len(markdown_paths),
        "link_check_scope": "Wikilinks outside code only; use native Obsidian unresolved output to inspect Markdown relative links and protected source-document dependencies",
        "brain_note_count": len(properties),
        "raw_asset_markdown_count": len(raw_asset_markdown),
        "raw_asset_markdown": raw_asset_markdown,
        "type_counts": dict(
            sorted(
                Counter(fm.get("type") for fm in fm_by_path.values()).items(),
                key=lambda item: str(item[0]),
            )
        ),
        "status_counts": dict(
            sorted(
                Counter(fm.get("status") for fm in fm_by_path.values()).items(),
                key=lambda item: str(item[0]),
            )
        ),
        "missing_core_fields": missing_core,
        "invalid_fields": invalid_fields,
        "unresolved_links": unresolved,
        "expired_review": expired,
        "active_without_source_or_evidence": active_without_evidence,
        "business_orphans": business_orphans,
        "superseded_without_successor": superseded_issues,
        "duplicate_stems": duplicate_stems,
        "checks": {
            "core_fields_ok": not missing_core,
            "type_status_ok": not invalid_fields,
            "links_ok": not unresolved,
            "supersession_ok": not superseded_issues,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": all(report["checks"].values()),
                "markdown_count": len(markdown_paths),
                "unresolved_links": len(unresolved),
                "missing_core_fields": len(missing_core),
                "invalid_fields": len(invalid_fields),
                "expired_review": len(expired),
                "active_without_source_or_evidence": len(active_without_evidence),
                "business_orphans": len(business_orphans),
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(report["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
