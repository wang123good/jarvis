#!/usr/bin/env python3
"""Prepare and score a generative QA run for the JARVIS Brain."""

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


def tokens(text: str) -> list[str]:
    result = []
    for sequence in HAN_SEQUENCE.findall(text):
        if len(sequence) == 1:
            result.append(sequence)
        else:
            result.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
    result.extend(match.group(0).casefold() for match in ASCII_WORD.finditer(text))
    return result


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


def load_docs(vault: Path):
    docs = []
    df = Counter()
    for current, dirs, files in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            if not name.lower().endswith(".md"):
                continue
            path = Path(current) / name
            text = path.read_text(encoding="utf-8-sig")
            fm, body = split_frontmatter(text)
            counts = Counter(tokens(text))
            docs.append(
                {
                    "path": path.relative_to(vault).as_posix(),
                    "title": fm.get("title") or path.stem,
                    "type": fm.get("type") or "",
                    "status": fm.get("status") or "",
                    "topics": fm.get("topics") or fm.get("topic") or "",
                    "body": body,
                    "counts": counts,
                }
            )
            for token in set(counts):
                df[token] += 1
    return docs, df


def retrieve(question: str, docs: list[dict], df: Counter, limit: int = 6):
    query = list(dict.fromkeys(tokens(question)))
    total = len(docs)
    ranked = []
    for doc in docs:
        score = 0.0
        title_tokens = set(tokens(doc["title"]))
        for token in query:
            count = doc["counts"].get(token, 0)
            if not count:
                continue
            idf = math.log((total + 1) / (df[token] + 1)) + 1
            score += (1 + math.log(count)) * idf
            if token in title_tokens:
                score += 2.0 * idf
            if token in str(doc["topics"]):
                score += 2.0 * idf
        if score:
            ranked.append((score, doc))
    ranked.sort(key=lambda item: (-item[0], item[1]["path"]))
    results = []
    for score, doc in ranked[:limit]:
        excerpt = re.sub(r"\s+", " ", doc["body"]).strip()[:1600]
        results.append(
            {
                "path": doc["path"],
                "title": doc["title"],
                "type": doc["type"],
                "status": doc["status"],
                "score": round(score, 3),
                "excerpt": excerpt,
            }
        )
    return results


def citation_exists(citation: str, vault: Path) -> bool:
    path = Path(citation)
    if not path.is_absolute():
        path = vault / citation
    return path.exists()


def contains_any(text: str, terms: list[str]) -> bool:
    folded = text.casefold()
    return any(term.casefold() in folded for term in terms)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["prepare", "score"], required=True)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--answers")
    args = parser.parse_args()
    vault = Path(args.vault).resolve()
    suite = json.loads(Path(args.suite).read_text(encoding="utf-8"))
    questions = suite["questions"]

    if args.mode == "prepare":
        docs, df = load_docs(vault)
        requests = []
        for question in questions:
            requests.append(
                {
                    **question,
                    "evidence": retrieve(question["question"], docs, df),
                }
            )
        output = {
            "suite_version": suite["version"],
            "model_path": suite["model_path"],
            "question_count": len(requests),
            "instructions": [
                "Answer only from the supplied evidence or explicitly abstain.",
                "Cite at least one exact evidence path for every non-abstention answer.",
                "For abstention questions, set abstained=true and explain the evidence gap.",
            ],
            "questions": requests,
        }
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {"ok": True, "mode": "prepare", "questions": len(requests), "output": args.output},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not args.answers:
        raise RuntimeError("--answers is required in score mode")
    answers = json.loads(Path(args.answers).read_text(encoding="utf-8"))
    answer_by_id = {item["id"]: item for item in answers["answers"]}
    expected_ids = {item["id"] for item in questions}
    missing = sorted(expected_ids - set(answer_by_id))
    unexpected = sorted(set(answer_by_id) - expected_ids)
    results = []
    for question in questions:
        answer = answer_by_id.get(question["id"], {})
        text = str(answer.get("answer") or "")
        citations = [str(item) for item in answer.get("citations", [])]
        citation_valid = all(citation_exists(item, vault) for item in citations)
        groups_satisfied = all(
            any(citation in group for citation in citations)
            for group in question.get("citation_groups", [])
        )
        concepts = question.get("required_concepts", [])
        concept_hits = [contains_any(text, alternatives) for alternatives in concepts]
        concepts_ok = all(concept_hits)
        abstained = bool(answer.get("abstained", False))
        abstention_ok = (
            not question.get("must_abstain", False)
            or (
                abstained
                and contains_any(text, ["没有证据", "无法证明", "证据不足", "不能证明"])
            )
        )
        forbidden = [
            phrase
            for phrase in question.get("must_not_claim", [])
            if phrase.casefold() in text.casefold()
        ]
        passed = (
            bool(text.strip())
            and bool(citations)
            and citation_valid
            and groups_satisfied
            and concepts_ok
            and abstention_ok
            and not forbidden
        )
        results.append(
            {
                "id": question["id"],
                "kind": question["kind"],
                "passed": passed,
                "citations": citations,
                "citation_valid": citation_valid,
                "citation_groups_satisfied": groups_satisfied,
                "required_concepts": concepts,
                "required_concepts_satisfied": concept_hits,
                "abstained": abstained,
                "abstention_ok": abstention_ok,
                "forbidden_claims_found": forbidden,
            }
        )
    passed = sum(1 for item in results if item["passed"])
    report = {
        "suite_version": suite["version"],
        "model_path": suite["model_path"],
        "answer_run_id": answers.get("run_id"),
        "question_count": len(questions),
        "answered_count": len(answer_by_id),
        "missing_questions": missing,
        "unexpected_answers": unexpected,
        "passed": passed,
        "failed": len(questions) - passed,
        "pass_rate": round(passed / len(questions), 4),
        "results": results,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "ok": passed == len(questions) and not missing and not unexpected,
                "question_count": len(questions),
                "answered_count": len(answer_by_id),
                "passed": passed,
                "failed": len(questions) - passed,
                "pass_rate": report["pass_rate"],
                "missing": missing,
                "unexpected": unexpected,
                "output": args.output,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed == len(questions) and not missing and not unexpected else 1


if __name__ == "__main__":
    raise SystemExit(main())
