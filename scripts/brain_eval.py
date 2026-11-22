#!/usr/bin/env python3
"""Deterministic lexical retrieval baseline for Brain golden questions."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import Counter
from pathlib import Path


SKIP_DIRS = {".git", ".obsidian", ".trash"}
HAN_SEQUENCE = re.compile(r"[\u3400-\u9fff]+")
ASCII_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_.+-]{1,}")


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
    fm = {}
    for line in header.splitlines():
        if line.startswith((" ", "\t", "#")):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            fm[key.strip()] = value.strip().strip("\"'")
    return fm, normalized[body_start:]


def tokens(text: str) -> list[str]:
    result = []
    for sequence in HAN_SEQUENCE.findall(text):
        if len(sequence) == 1:
            result.append(sequence)
        else:
            result.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
    result.extend(match.group(0).casefold() for match in ASCII_WORD.finditer(text))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True)
    parser.add_argument("--questions", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--phase", choices=["pre", "post"], required=True)
    parser.add_argument("--health-json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    vault = Path(args.vault).resolve()
    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))["questions"]
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    spec_by_id = {item["id"]: item for item in spec["questions"]}
    health = (
        json.loads(Path(args.health_json).read_text(encoding="utf-8"))
        if args.health_json
        else None
    )
    records = []
    df = Counter()
    for current, dirs, files in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            if not name.lower().endswith(".md"):
                continue
            path = Path(current) / name
            text = path.read_text(encoding="utf-8-sig")
            fm, body = split_frontmatter(text)
            record = {
                "path": path.relative_to(vault).as_posix(),
                "title": fm.get("title") or path.stem,
                "type": fm.get("type") or "",
                "status": fm.get("status") or "",
                "topics": fm.get("topics") or fm.get("topic") or "",
                "text": body,
                "token_counts": Counter(tokens(text)),
            }
            records.append(record)
            for token in set(record["token_counts"]):
                df[token] += 1
    total_docs = len(records)
    results = []
    for question in questions:
        qspec = spec_by_id.get(question["id"], {})
        query_text = (
            question["question"]
            + " "
            + " ".join(question.get("expected_topics", []))
            + " "
            + " ".join(qspec.get("query_terms", []))
        )
        query_tokens = list(dict.fromkeys(tokens(query_text)))
        ranked = []
        for record in records:
            score = 0.0
            title_tokens = set(tokens(record["title"]))
            topics_text = str(record["topics"])
            for token in query_tokens:
                frequency = record["token_counts"].get(token, 0)
                if not frequency:
                    continue
                inverse = math.log((total_docs + 1) / (df[token] + 1)) + 1
                score += (1 + math.log(frequency)) * inverse
                if token in title_tokens:
                    score += 2.5 * inverse
                if token in topics_text:
                    score += 3.0 * inverse
            if score:
                ranked.append((score, record))
        ranked.sort(key=lambda item: (-item[0], item[1]["path"]))
        top = []
        for score, record in ranked[:5]:
            expected_match = any(
                topic and topic.casefold() in str(record["topics"]).casefold()
                for topic in question.get("expected_topics", [])
            )
            top.append(
                {
                    "path": record["path"],
                    "title": record["title"],
                    "type": record["type"],
                    "status": record["status"],
                    "topics": record["topics"],
                    "score": round(score, 3),
                    "expected_topic_match": expected_match,
                }
            )
        expected_paths = set(qspec.get(f"{args.phase}_paths", []))
        expected_path_match = any(item["path"] in expected_paths for item in top)
        special = qspec.get("special_check")
        special_passed = None
        if special == "health_expired_zero" and health is not None:
            special_passed = len(health.get("expired_review", [])) == 0
        refusal_terms = qspec.get("refusal_terms", [])
        forbidden_claim_present = any(
            term and any(term in record["text"] for record in records)
            for term in refusal_terms
        )
        evidence_hit = (
            special_passed
            if special
            else (expected_path_match if expected_paths else any(
                item["expected_topic_match"] for item in top
            ))
        )
        results.append(
            {
                **question,
                "query_tokens": query_tokens,
                "top_results": top,
                "expected_topic_match_at_5": any(
                    item["expected_topic_match"] for item in top
                ),
                "expected_path_match_at_5": expected_path_match,
                "expected_paths": sorted(expected_paths),
                "special_check": special,
                "special_check_passed": special_passed,
                "refusal_terms": refusal_terms,
                "forbidden_claim_present": forbidden_claim_present,
                "evidence_hit_at_5": evidence_hit,
            }
        )
    report = {
        "schema_version": 1,
        "vault": str(vault),
        "question_count": len(questions),
        "document_count": total_docs,
        "phase": args.phase,
        "method": "Deterministic bi-gram and word TF-IDF search; not an LLM semantic evaluation.",
        "evidence_hit_at_5": sum(
            1 for item in results if item["evidence_hit_at_5"] is True
        ),
        "unresolved_or_not_applicable": sum(
            1 for item in results if item["evidence_hit_at_5"] is None
        ),
        "forbidden_claims_present": sum(
            1 for item in results if item["forbidden_claim_present"]
        ),
        "results": results,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "question_count": len(questions),
                "document_count": total_docs,
                "phase": args.phase,
                "evidence_hit_at_5": report["evidence_hit_at_5"],
                "unresolved_or_not_applicable": report[
                    "unresolved_or_not_applicable"
                ],
                "forbidden_claims_present": report["forbidden_claims_present"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
