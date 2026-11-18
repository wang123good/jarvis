from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_REGISTRY = BASE_DIR / "experience-registry.json"
DEFAULT_REVIEW_LOG = BASE_DIR / "experience-review-log.json"
DEFAULT_SAMPLE_DIR = BASE_DIR / "样本" / "2026"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate JARVIS registry and Obsidian mapping.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--review-log", type=Path, default=DEFAULT_REVIEW_LOG)
    parser.add_argument("--sample-dir", type=Path, default=DEFAULT_SAMPLE_DIR)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError("unterminated frontmatter")
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line or line.startswith((" ", "\t", "- ")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip("'\"")
    return result


def main() -> None:
    args = parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    review_log = json.loads(args.review_log.read_text(encoding="utf-8"))
    experiences = registry.get("experiences", [])
    reviews = review_log.get("reviews", [])

    errors: list[str] = []
    warnings: list[str] = []
    mappings: list[dict] = []
    ids: set[str] = set()
    paths: set[Path] = set()
    approved_reviews = {
        item.get("experience_id"): item
        for item in reviews
        if item.get("decision") == "approved"
    }

    for item in experiences:
        exp_id = str(item.get("experience_id", ""))
        if exp_id in ids:
            errors.append(f"duplicate experience_id: {exp_id}")
        ids.add(exp_id)

        rel_path = str(item.get("obsidian_path", ""))
        note_path = BASE_DIR.parent.parent.parent / rel_path
        note_path = note_path.resolve()
        if note_path in paths:
            errors.append(f"duplicate obsidian_path: {rel_path}")
        paths.add(note_path)
        if not note_path.exists():
            errors.append(f"missing note: {exp_id} -> {rel_path}")
            mappings.append({"experience_id": exp_id, "path": rel_path, "ok": False})
            continue

        try:
            frontmatter = parse_frontmatter(note_path)
        except ValueError as exc:
            errors.append(f"invalid frontmatter: {exp_id}: {exc}")
            mappings.append({"experience_id": exp_id, "path": rel_path, "ok": False})
            continue

        comparisons = {
            "experience_id": exp_id,
            "task_signature": str(item.get("task_signature", "")),
            "title": str(item.get("task_name", "")),
            "status": str(item.get("status", "")),
            "call_frequency": str(item.get("call_frequency", "")),
            "human_review": str(item.get("human_review", "")),
        }
        mismatches = {
            key: {"registry": expected, "note": frontmatter.get(key)}
            for key, expected in comparisons.items()
            if frontmatter.get(key) != expected
        }
        if mismatches:
            errors.append(f"mapping mismatch: {exp_id}: {json.dumps(mismatches, ensure_ascii=False)}")

        review = approved_reviews.get(exp_id)
        if item.get("human_review") == "approved" and review is None:
            errors.append(f"missing approved review: {exp_id}")
        if review and review.get("status_after") != item.get("status"):
            errors.append(
                f"review status mismatch: {exp_id}: {review.get('status_after')} != {item.get('status')}"
            )

        mappings.append(
            {
                "experience_id": exp_id,
                "path": rel_path,
                "title": frontmatter.get("title"),
                "status": frontmatter.get("status"),
                "human_review": frontmatter.get("human_review"),
                "ok": not mismatches,
            }
        )

    actual_notes = {
        path.resolve()
        for path in args.sample_dir.glob("*.md")
        if path.is_file()
    }
    for orphan in sorted(actual_notes - paths):
        errors.append(f"note not represented in registry: {orphan}")

    for review in reviews:
        exp_id = review.get("experience_id")
        if exp_id not in ids:
            errors.append(f"review references unknown experience: {exp_id}")

    report = {
        "checked_at": date.today().isoformat(),
        "registry": args.registry.name,
        "review_log": args.review_log.name,
        "experience_count": len(experiences),
        "review_count": len(reviews),
        "sample_note_count": len(actual_notes),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "mappings": mappings,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
