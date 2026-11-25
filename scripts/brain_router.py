#!/usr/bin/env python3
"""Validate and query the JARVIS dual-mode Brain context policy."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import json
import os
import re
import unicodedata
from pathlib import Path, PureWindowsPath
from typing import Iterable

from brain_health import split_frontmatter
from resolve_environment import EnvironmentConfigError, read_object, relative_to


PROJECT_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STATUS_VALUES = {
    "active",
    "reviewed",
    "trusted",
    "draft",
    "inbox",
    "review",
    "archived",
    "superseded",
    "rejected",
    "deprecated",
    "expired",
}
ASCII_RE = re.compile(r"[a-z0-9][a-z0-9_.+-]*", re.IGNORECASE)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")
SKIP_DIRS = {".git", ".obsidian", ".trash"}
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "with",
}


class RouterConfigError(ValueError):
    """The project registry or research policy is incomplete or unsafe."""


@dataclass(frozen=True)
class Scope:
    layer: str
    root: str
    source_project: str | None
    kind: str


@dataclass
class Note:
    rel_path: str
    title: str
    note_type: str
    status: str
    tags: list[str]
    body: str
    layer: str
    source_project: str | None
    source_kind: str


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip("/")


def validate_registry(config: dict, vault: Path | None = None) -> dict:
    if not isinstance(config, dict):
        raise RouterConfigError("Knowledge pointer must be an object")
    project = config.get("project")
    registry = config.get("project_registry")
    policy = config.get("research_policy")
    layers = config.get("layers")
    if not isinstance(project, dict):
        raise RouterConfigError("project must be an object")
    if not isinstance(registry, dict):
        raise RouterConfigError("project_registry must be an object")
    if not isinstance(policy, dict):
        raise RouterConfigError("research_policy must be an object")
    if not isinstance(layers, dict):
        raise RouterConfigError("layers must be an object")

    projects = registry.get("projects")
    if not isinstance(projects, list) or not projects:
        raise RouterConfigError("project_registry.projects must be a nonempty list")
    current_id = registry.get("current_project_id")
    if current_id != project.get("id"):
        raise RouterConfigError("current_project_id must match project.id")

    ids, roots = set(), set()
    for entry in projects:
        if not isinstance(entry, dict):
            raise RouterConfigError("Every registered project must be an object")
        project_id = entry.get("id")
        if not isinstance(project_id, str) or not PROJECT_ID_RE.fullmatch(project_id):
            raise RouterConfigError(f"Invalid project id: {project_id!r}")
        if project_id in ids:
            raise RouterConfigError(f"Duplicate project id: {project_id}")
        ids.add(project_id)
        if not isinstance(entry.get("name"), str) or not entry["name"].strip():
            raise RouterConfigError(f"{project_id}.name must be a nonempty string")
        root = entry.get("root")
        if not isinstance(root, str) or not root.strip():
            raise RouterConfigError(f"{project_id}.root must be a nonempty relative path")
        portable = root.replace("\\", "/")
        if Path(portable).is_absolute() or PureWindowsPath(root).drive or ".." in portable.split("/"):
            raise RouterConfigError(f"{project_id}.root must stay relative to the vault")
        normalized_root = normalize_path(root)
        if normalized_root in roots:
            raise RouterConfigError(f"Duplicate project root: {normalized_root}")
        roots.add(normalized_root)
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(item, str) for item in aliases):
            raise RouterConfigError(f"{project_id}.aliases must be a list of strings")
        if not isinstance(entry.get("researchable"), bool):
            raise RouterConfigError(f"{project_id}.researchable must be a boolean")
        if vault is not None:
            relative_to(vault, root, f"{project_id}.root")

    current = next((entry for entry in projects if entry.get("id") == current_id), None)
    if current is None:
        raise RouterConfigError("Current project must be present in project_registry.projects")
    if normalize_path(current.get("root", "")) != normalize_path(project.get("root", "")):
        raise RouterConfigError("Current registered root must match project.root")

    default_mode = policy.get("default_mode")
    if default_mode not in {"project", "research"}:
        raise RouterConfigError("research_policy.default_mode must be project or research")
    shared_layers = policy.get("shared_layers")
    if not isinstance(shared_layers, list) or not all(
        isinstance(layer, str) and layer in layers for layer in shared_layers
    ):
        raise RouterConfigError("shared_layers must name configured layers")
    if "project" in shared_layers:
        raise RouterConfigError("shared_layers must not include the project layer")

    for field in ("current_statuses", "draft_statuses", "non_current_statuses"):
        values = policy.get(field)
        if not isinstance(values, list) or not values or not all(
            isinstance(item, str) and item in STATUS_VALUES for item in values
        ):
            raise RouterConfigError(f"research_policy.{field} must contain known statuses")
    if set(policy["current_statuses"]) & set(policy["non_current_statuses"]):
        raise RouterConfigError("Current and non-current status policies must not overlap")
    explicit = policy.get("explicit_status_options")
    if not isinstance(explicit, dict):
        raise RouterConfigError("explicit_status_options must be an object")
    for name, statuses in explicit.items():
        if not isinstance(name, str) or not isinstance(statuses, list) or not all(
            isinstance(item, str) and item in STATUS_VALUES for item in statuses
        ):
            raise RouterConfigError("explicit_status_options values must be status lists")

    for field in ("max_results", "max_linked_results"):
        value = policy.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 20:
            raise RouterConfigError(f"research_policy.{field} must be an integer from 1 to 20")
    for field in ("allow_inbox_by_default", "allow_archive_by_default"):
        if policy.get(field) is not False:
            raise RouterConfigError(f"{field} must be false")
    if policy.get("write_allowed") is not False:
        raise RouterConfigError("write_allowed must be false")
    return config


def vault_router_file(project_root: Path, vault: Path) -> Path:
    import hashlib
    import os

    key = hashlib.sha256(os.path.normcase(str(vault)).encode()).hexdigest()
    return relative_to(project_root, f".local/brain-router/{key}.json", "local Router registry")


def router_config_path(environment: dict) -> Path:
    local = vault_router_file(Path(environment["project_root"]), Path(environment["vault_root"]))
    return local if local.is_file() else Path(environment["knowledge_pointer"])


def load_registry(path: Path, vault: Path | None = None) -> dict:
    try:
        config = read_object(path)
    except EnvironmentConfigError as exc:
        raise RouterConfigError(str(exc)) from exc
    return validate_registry(config, vault)


def scope_health(config: dict, vault: Path) -> dict:
    validate_registry(config, vault)
    project_roots = []
    missing_roots = []
    missing_indexes = []
    for project in config["project_registry"]["projects"]:
        root = relative_to(vault, project["root"], f"{project['id']}.root")
        root_exists = root.is_dir()
        index_exists = (root / "00_项目索引.md").is_file()
        project_roots.append(
            {
                "id": project["id"],
                "root": project["root"],
                "exists": root_exists,
                "index_exists": index_exists,
            }
        )
        if not root_exists:
            missing_roots.append(project["root"])
        elif not index_exists:
            missing_indexes.append(
                f"{normalize_path(project['root'])}/00_项目索引.md"
            )

    shared_scopes = []
    missing_shared = []
    for layer in config["research_policy"]["shared_layers"]:
        for folder in config["layers"][layer]:
            scope = relative_to(vault, folder, f"layers.{layer}")
            exists = scope.is_dir()
            shared_scopes.append(
                {"layer": layer, "root": folder, "exists": exists}
            )
            if not exists:
                missing_shared.append(folder)
    return {
        "ok": not missing_roots and not missing_shared,
        "project_roots_checked": len(project_roots),
        "project_roots_missing": sorted(missing_roots),
        "project_indexes_missing": sorted(missing_indexes),
        "shared_scopes_checked": len(shared_scopes),
        "shared_scopes_missing": sorted(missing_shared),
        "projects": project_roots,
        "shared_scopes": shared_scopes,
    }


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).casefold()
    return re.sub(r"\s+", " ", value).strip()


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip().lstrip("#") for item in value if str(item).strip()]
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        return [
            item.strip().strip("'\"")
            for item in text[1:-1].split(",")
            if item.strip()
        ]
    return [text.lstrip("#")] if text else []


def tokenize(value: str) -> list[str]:
    normalized = normalize_text(value)
    result = [
        match.group(0)
        for match in ASCII_RE.finditer(normalized)
        if len(match.group(0)) > 1 and match.group(0) not in STOP_WORDS
    ]
    for match in CJK_RE.finditer(normalized):
        text = match.group(0)
        if len(text) == 1:
            result.append(text)
            continue
        if len(text) <= 12:
            result.append(text)
        for size in (2, 3):
            result.extend(
                text[index : index + size]
                for index in range(len(text) - size + 1)
            )
    return result


def iter_markdown(root: Path, vault: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        parent = Path(current)
        dirs[:] = sorted(
            item
            for item in dirs
            if item not in SKIP_DIRS
            and not item.startswith(".")
            and (parent / item).resolve() == parent / item
        )
        for name in sorted(files):
            if name.startswith(".") or not name.casefold().endswith(".md"):
                continue
            path = parent / name
            if path.resolve() == path and path.is_file():
                yield path


def read_scope(scope: Scope, vault: Path) -> tuple[list[Note], list[str]]:
    root = relative_to(vault, scope.root, "project registry root")
    if not root.is_dir():
        return [], [f"Scope unavailable: {scope.root}"]
    notes, skipped = [], []
    for path in iter_markdown(root, vault):
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            skipped.append(path.relative_to(vault).as_posix())
            continue
        if len(raw) > 5_000_000:
            skipped.append(path.relative_to(vault).as_posix())
            continue
        metadata, body = split_frontmatter(raw)
        notes.append(
            Note(
                rel_path=path.relative_to(vault).as_posix(),
                title=str(metadata.get("title") or path.stem),
                note_type=str(metadata.get("type") or ""),
                status=normalize_text(metadata.get("status") or "unspecified"),
                tags=as_list(metadata.get("tags")),
                body=body,
                layer=scope.layer,
                source_project=scope.source_project,
                source_kind=scope.kind,
            )
        )
    return notes, skipped


def lexical_score(note: Note, terms: list[str], query: str) -> float:
    title = Counter(tokenize(note.title))
    path = Counter(tokenize(note.rel_path))
    tags = Counter(tokenize(" ".join(note.tags)))
    body = Counter(tokenize(note.body))
    score = 0.0
    for term in terms:
        score += title[term] * 8
        score += tags[term] * 5
        score += path[term] * 3
        score += min(body[term], 12)
    normalized_query = normalize_text(query)
    if normalized_query and normalized_query in normalize_text(note.title):
        score += 20
    elif normalized_query and normalized_query in normalize_text(note.body):
        score += 5
    if note.status in {"trusted", "reviewed"}:
        score += 1
    return score


def excerpt(note: Note, query: str, maximum: int = 700) -> str:
    blocks = [
        re.sub(r"\s+", " ", block).strip()
        for block in re.split(r"\n\s*\n", note.body)
        if block.strip() and not re.match(r"^#{1,6}\s", block.strip())
    ]
    if not blocks:
        return ""
    terms = set(tokenize(query))
    best = max(blocks, key=lambda block: len(terms & set(tokenize(block))))
    if len(best) <= maximum:
        return best
    return best[: max(maximum - 3, 0)].rstrip() + "..."


def project_is_hub(note: Note, project_root: str) -> bool:
    expected = f"{normalize_path(project_root)}/00_项目索引.md"
    return (
        note.rel_path == expected
        or note.note_type.casefold() in {"index", "project", "项目"}
        and normalize_path(note.rel_path).startswith(normalize_path(project_root) + "/")
    )


def project_scopes(config: dict) -> list[Scope]:
    registry = config["project_registry"]
    current_id = registry["current_project_id"]
    current = next(
        item for item in registry["projects"] if item["id"] == current_id
    )
    scopes = [Scope("project", current["root"], current_id, "current_project")]
    if normalize_text(current["name"]) == "jarvis":
        scopes.append(
            Scope("project", "05 规则/JARVIS", current_id, "current_project_rule")
        )
    for layer in config["research_policy"]["shared_layers"]:
        for folder in config["layers"][layer]:
            scopes.append(Scope(layer, folder, None, "shared"))
    return scopes


def status_filter(config: dict, allowed_statuses: set[str] | None = None) -> set[str]:
    policy = config["research_policy"]
    return set(allowed_statuses or policy["current_statuses"])


def select_research_projects(
    config: dict,
    requested: str | None,
) -> tuple[list[dict], str]:
    projects = config["project_registry"]["projects"]
    current_id = config["project_registry"]["current_project_id"]
    by_key = {}
    for project in projects:
        keys = {
            normalize_text(project["id"]),
            normalize_text(project["name"]),
            *(normalize_text(alias) for alias in project.get("aliases", [])),
        }
        for key in keys:
            by_key[key] = project
    if requested and requested.strip():
        selected, unknown = [], []
        for raw in requested.split(","):
            key = normalize_text(raw)
            if not key:
                continue
            project = by_key.get(key)
            if project is None:
                unknown.append(raw.strip())
                continue
            if (
                project["id"] != current_id
                and not project.get("researchable", False)
            ):
                unknown.append(raw.strip())
                continue
            if project not in selected:
                selected.append(project)
        if unknown:
            raise RouterConfigError(
                "Unknown or non-researchable projects: " + ", ".join(unknown)
            )
        if not selected:
            raise RouterConfigError("At least one research project must be selected")
        return selected, "explicit"
    candidates = [
        project
        for project in projects
        if project["id"] != current_id and project.get("researchable", False)
    ]
    return candidates, "auto_candidates"


def research_statuses(
    config: dict,
    *,
    include_archived: bool,
    include_superseded: bool,
    include_drafts: bool,
) -> set[str]:
    policy = config["research_policy"]
    allowed = set(policy["current_statuses"])
    explicit = policy["explicit_status_options"]
    if include_archived:
        allowed.update(explicit.get("archived", []))
    if include_superseded:
        allowed.update(explicit.get("superseded", []))
    if include_drafts:
        allowed.update(explicit.get("draft", []))
    return allowed


def research_scopes(config: dict, projects: list[dict]) -> list[Scope]:
    current_id = config["project_registry"]["current_project_id"]
    scopes = []
    for project in projects:
        kind = (
            "current_project_rule"
            if project["id"] == current_id
            else "research_project"
        )
        scopes.append(Scope("project", project["root"], project["id"], kind))
        if project["id"] == current_id and normalize_text(project["name"]) == "jarvis":
            scopes.append(
                Scope("project", "05 规则/JARVIS", current_id, "current_project_rule")
            )
    for layer in config["research_policy"]["shared_layers"]:
        for folder in config["layers"][layer]:
            scopes.append(Scope(layer, folder, None, "shared"))
    return scopes


def link_targets(body: str) -> list[str]:
    targets = []
    for match in WIKILINK_RE.finditer(body):
        target = match.group(1).split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            targets.append(target)
    return targets


def resolve_link(
    target: str,
    source_path: str,
    by_path: dict[str, Note],
    by_stem: dict[str, list[Note]],
) -> Note | None:
    normalized = normalize_path(target)
    normalized = normalized[:-3] if normalized.casefold().endswith(".md") else normalized
    direct = by_path.get(normalized)
    if direct:
        return direct
    source_parent = Path(source_path).parent.as_posix()
    relative = normalize_path(
        os.path.normpath(os.path.join(source_parent, normalized)).replace("\\", "/")
    )
    direct = by_path.get(relative)
    if direct:
        return direct
    matches = by_stem.get(normalize_text(Path(normalized).stem), [])
    return matches[0] if len(matches) == 1 else None


def conflict_entries(notes: list[Note]) -> list[dict]:
    groups: dict[str, list[Note]] = {}
    for note in notes:
        title = normalize_text(note.title)
        if (
            not title
            or title in {"index", "readme", "首页"}
            or title.endswith("项目索引")
            or title.endswith("记忆索引")
        ):
            continue
        groups.setdefault(title, []).append(note)
    conflicts = []
    for title, items in sorted(groups.items()):
        if len(items) < 2:
            continue
        projects = {
            item.source_project or "shared"
            for item in items
        }
        statuses = {item.status for item in items}
        if len(projects) < 2 and len(statuses) < 2:
            continue
        conflicts.append(
            {
                "kind": "duplicate_title",
                "title": items[0].title,
                "source_projects": sorted(projects),
                "statuses": sorted(statuses),
                "paths": sorted(item.rel_path for item in items),
                "resolution": "not_merged",
            }
        )
    return conflicts


def context_result(
    note: Note,
    query: str,
    score: float | None,
    selection_reason: str,
    current: bool = True,
) -> dict:
    payload = {
        "title": note.title,
        "path": note.rel_path,
        "layer": note.layer,
        "source_project": note.source_project or "shared",
        "source_kind": note.source_kind,
        "status": note.status,
        "type": note.note_type,
        "current": current,
        "selection_reason": selection_reason,
        "excerpt": excerpt(note, query),
    }
    if score is not None:
        payload["score"] = round(score, 4)
    return payload


def build_project_context(
    config: dict,
    vault: Path,
    query: str,
    limit: int | None = None,
) -> dict:
    validate_registry(config, vault)
    policy = config["research_policy"]
    requested_limit = limit or int(policy["max_results"])
    if not 1 <= requested_limit <= 20:
        raise RouterConfigError("limit must be from 1 to 20")
    current_id = config["project_registry"]["current_project_id"]
    current = next(
        item
        for item in config["project_registry"]["projects"]
        if item["id"] == current_id
    )
    query = query.strip() or " ".join([current["name"], *current.get("aliases", [])])
    allowed_statuses = status_filter(config)
    scopes = project_scopes(config)
    notes, unavailable, skipped = [], [], []
    for scope in scopes:
        found, missing = read_scope(scope, vault)
        notes.extend(found)
        unavailable.extend(missing)
    eligible = [note for note in notes if note.status in allowed_statuses]
    blocked_status_count = Counter(
        note.status for note in notes if note.status not in allowed_statuses
    )
    terms = list(dict.fromkeys(tokenize(query)))
    ranked = []
    for note in eligible:
        score = lexical_score(note, terms, query)
        if score > 0:
            ranked.append((score, note))
    ranked.sort(key=lambda item: (-item[0], item[1].rel_path.casefold()))

    selected: list[tuple[Note, float | None, str]] = []
    seen = set()
    hubs = sorted(
        (
            note
            for note in eligible
            if project_is_hub(note, current["root"])
            and note.source_kind == "current_project"
        ),
        key=lambda note: (
            note.rel_path
            != f"{normalize_path(current['root'])}/00_项目索引.md",
            note.rel_path.casefold(),
        ),
    )
    for hub in hubs[:1]:
        if len(selected) >= requested_limit:
            break
        selected.append((hub, None, "current_project_hub"))
        seen.add(hub.rel_path)
    for score, note in ranked:
        if len(selected) >= requested_limit:
            break
        if note.rel_path in seen:
            continue
        reason = (
            "current_project_rule_match"
            if note.source_kind == "current_project_rule"
            else "shared_layer_match"
            if note.source_kind == "shared"
            else "current_project_match"
        )
        selected.append((note, score, reason))
        seen.add(note.rel_path)

    blocked_projects = sorted(
        item["id"]
        for item in config["project_registry"]["projects"]
        if item["id"] != current_id
    )
    evidence_gaps = list(unavailable)
    if not selected:
        evidence_gaps.append(
            f"No eligible current-project or shared note matched query: {query}"
        )
    pack = {
        "schema_version": 1,
        "mode": "project",
        "query": query,
        "retrieved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "write_allowed": False,
        "current_project": current_id,
        "requested_projects": [current_id],
        "included_projects": sorted(
            {
                note.source_project
                for note, _, _ in selected
                if note.source_project and note.source_project != "shared"
            }
        ),
        "included_layers": sorted({note.layer for note, _, _ in selected}),
        "allowed_statuses": sorted(allowed_statuses),
        "requested_limit": requested_limit,
        "result_count": len(selected),
        "results": [
            context_result(note, query, score, reason)
            for note, score, reason in selected
        ],
        "exclusions": {
            "blocked_projects": blocked_projects,
            "blocked_layers": ["inbox", "archive"],
            "status_counts": dict(sorted(blocked_status_count.items())),
            "not_selected_count": max(len(ranked) - len(selected), 0),
            "unreadable_or_large": sorted(skipped),
        },
        "conflicts": [],
        "evidence_gaps": evidence_gaps,
    }
    return pack


def build_research_context(
    config: dict,
    vault: Path,
    query: str,
    *,
    projects: str | None = None,
    limit: int | None = None,
    include_archived: bool = False,
    include_superseded: bool = False,
    include_drafts: bool = False,
) -> dict:
    validate_registry(config, vault)
    policy = config["research_policy"]
    requested_limit = limit or int(policy["max_results"])
    if not 1 <= requested_limit <= 20:
        raise RouterConfigError("limit must be from 1 to 20")
    selected_projects, selection_mode = select_research_projects(config, projects)
    requested_query = query.strip()
    if not requested_query:
        requested_query = " ".join(
            [project["name"] for project in selected_projects]
            + config["research_policy"]["shared_layers"]
        )
    allowed_statuses = research_statuses(
        config,
        include_archived=include_archived,
        include_superseded=include_superseded,
        include_drafts=include_drafts,
    )
    scopes = research_scopes(config, selected_projects)
    notes, unavailable, skipped = [], [], []
    for scope in scopes:
        found, missing = read_scope(scope, vault)
        notes.extend(found)
        unavailable.extend(missing)
    eligible = [note for note in notes if note.status in allowed_statuses]
    blocked_status_count = Counter(
        note.status for note in notes if note.status not in allowed_statuses
    )
    terms = list(dict.fromkeys(tokenize(requested_query)))
    matched = [
        (lexical_score(note, terms, requested_query), note)
        for note in eligible
    ]
    matched = [(score, note) for score, note in matched if score > 0]
    matched.sort(key=lambda item: (-item[0], item[1].rel_path.casefold()))

    selected: list[tuple[Note, float | None, str, str | None]] = []
    seen = set()

    def reason_for(note: Note) -> str:
        if note.source_kind == "shared":
            return (
                "shared_topic_match"
                if note.layer == "domain"
                else "shared_resource_match"
            )
        if note.source_kind == "current_project_rule":
            return "project_rule_match"
        return "research_project_match"

    def add(note: Note, score: float | None, reason: str) -> bool:
        if len(selected) >= requested_limit or note.rel_path in seen:
            return False
        selected.append((note, score, reason, None))
        seen.add(note.rel_path)
        return True

    shared_matches = [
        (score, note) for score, note in matched if note.source_kind == "shared"
    ]
    project_slots_available = sum(
        any(note.source_project == project_id for _, note in matched)
        for project_id in [project["id"] for project in selected_projects]
    )
    max_shared = min(
        2,
        max(requested_limit - project_slots_available, 0),
    )
    for score, note in shared_matches[:max_shared]:
        add(note, score, reason_for(note))

    project_ids = [project["id"] for project in selected_projects]
    for project_id in project_ids:
        for score, note in matched:
            if note.source_project == project_id:
                add(note, score, reason_for(note))
                break
    for score, note in matched:
        add(note, score, reason_for(note))

    all_by_path = {note.rel_path: note for note in eligible}
    by_name: dict[str, list[Note]] = {}
    for note in eligible:
        for key in {
            normalize_text(Path(note.rel_path).stem),
            normalize_text(note.title),
        }:
            if key:
                by_name.setdefault(key, []).append(note)
    linked_added = 0
    linked_gaps = []
    for seed, _, _, _ in list(selected):
        if (
            len(selected) >= requested_limit
            or linked_added >= int(policy["max_linked_results"])
        ):
            break
        for target in link_targets(seed.body):
            if (
                len(selected) >= requested_limit
                or linked_added >= int(policy["max_linked_results"])
            ):
                break
            linked = resolve_link(target, seed.rel_path, all_by_path, by_name)
            if linked is None:
                linked_gaps.append(f"Unresolved in-scope link: {target}")
                continue
            if linked.rel_path in seen or linked.status not in allowed_statuses:
                continue
            if (
                linked.source_project == seed.source_project
                and linked.layer == seed.layer
            ):
                continue
            if add(linked, None, "linked_cross_scope_evidence"):
                selected[-1] = (linked, None, "linked_cross_scope_evidence", seed.rel_path)
                linked_added += 1

    conflict_notes = {
        note.rel_path: note
        for _, note in matched
    }
    conflict_notes.update({note.rel_path: note for note, _, _, _ in selected})
    conflicts = conflict_entries(list(conflict_notes.values()))
    evidence_gaps = list(dict.fromkeys(unavailable + linked_gaps))
    if selection_mode == "auto_candidates" and not selected_projects:
        evidence_gaps.append("No researchable projects are registered")
    if not selected:
        evidence_gaps.append(
            f"No eligible research note matched query: {requested_query}"
        )
    results = []
    for note, score, reason, via in selected:
        item = context_result(
            note,
            requested_query,
            score,
            reason,
            current=note.status in policy["current_statuses"],
        )
        if via:
            item["via"] = via
        if note.status not in policy["current_statuses"]:
            item["status_warning"] = "non_current"
        results.append(item)
    blocked_projects = sorted(
        project["id"]
        for project in config["project_registry"]["projects"]
        if project["id"] not in project_ids
    )
    pack = {
        "schema_version": 1,
        "mode": "research",
        "query": requested_query,
        "retrieved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "write_allowed": False,
        "project_selection": selection_mode,
        "requested_projects": project_ids,
        "included_projects": sorted(
            {
                note.source_project
                for note, _, _, _ in selected
                if note.source_project and note.source_project != "shared"
            }
        ),
        "included_layers": sorted({note.layer for note, _, _, _ in selected}),
        "allowed_statuses": sorted(allowed_statuses),
        "requested_limit": requested_limit,
        "max_linked_results": int(policy["max_linked_results"]),
        "result_count": len(results),
        "results": results,
        "exclusions": {
            "blocked_projects": blocked_projects,
            "blocked_layers": ["inbox", "archive"],
            "status_counts": dict(sorted(blocked_status_count.items())),
            "not_selected_count": max(
                len({note.rel_path for _, note in matched} - seen), 0
            ),
            "unreadable_or_large": sorted(skipped),
        },
        "conflicts": conflicts,
        "evidence_gaps": evidence_gaps,
    }
    return pack


def common_parser(name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--config",
        default="",
        help="Explicit project pointer; defaults to the resolved project pointer.",
    )
    parser.add_argument("--connector-vault", help="Actual vault root reported by an external connector.")
    parser.add_argument("--query", default="", help="Concise task goal and key terms.")
    parser.add_argument("--limit", type=int, help="Maximum Context Pack results.")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-config", help="Validate registry and policy.")
    check.add_argument("--config", default="")
    check.add_argument("--connector-vault")
    commands.add_parser(
        "project",
        parents=[common_parser("project")],
        help="Build strict current-project context.",
    )
    research = commands.add_parser(
        "research",
        parents=[common_parser("research")],
        help="Research an explicit or auto-selected cross-project scope.",
    )
    research.add_argument(
        "--projects",
        default="",
        help="Comma-separated project ids or aliases; omitted means auto candidates.",
    )
    research.add_argument("--include-archived", action="store_true")
    research.add_argument("--include-superseded", action="store_true")
    research.add_argument("--include-drafts", action="store_true")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from resolve_environment import resolve_environment

        environment = resolve_environment(connector_vault=args.connector_vault)
        vault = Path(environment["vault_root"])
        if args.config:
            config_path = Path(args.config).expanduser().resolve()
        else:
            config_path = router_config_path(environment)
        config = load_registry(config_path, vault)
        if args.command == "project":
            pack = build_project_context(config, vault, args.query, args.limit)
            print(json.dumps(pack, ensure_ascii=False, indent=2))
            return 0 if pack["results"] else 3
        if args.command == "research":
            pack = build_research_context(
                config,
                vault,
                args.query,
                projects=args.projects,
                limit=args.limit,
                include_archived=args.include_archived,
                include_superseded=args.include_superseded,
                include_drafts=args.include_drafts,
            )
            print(json.dumps(pack, ensure_ascii=False, indent=2))
            return 0 if pack["results"] else 3
    except (RouterConfigError, EnvironmentConfigError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    health = scope_health(config, vault)
    payload = {
        "ok": health["ok"],
        "configuration_valid": True,
        "current_project_id": config["project_registry"]["current_project_id"],
        "registered_projects": len(config["project_registry"]["projects"]),
        "default_mode": config["research_policy"]["default_mode"],
        "write_allowed": config["research_policy"]["write_allowed"],
        "scope_health": health,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if health["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
