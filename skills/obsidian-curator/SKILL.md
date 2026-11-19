---
name: obsidian-curator
description: Curate exported Codex evidence or organize existing Obsidian notes with controlled tags, semantic links, and evidence-backed topic drafts. Use for knowledge administration and task retrospectives, not retrieval-only questions.
---

# Obsidian curator

Choose the mode from the actual input:

- **Exported Codex evidence:** use the workflow below and its existing `scripts/curate.py` writer.
- **Filtered business-dialogue export or manually selected dialogue:** follow codex-memory-sync's `references/transcript-retention.md`, then use the existing-note workflow for sourced candidates. Business exports use a separate `obsidian-business-links.json`; preserve source locators and selection limits, and do not route them through `curate.py` or invent its legacy full-export provenance.
- **Existing vault notes:** read [references/vault-maintenance.md](references/vault-maintenance.md) for scoped inventory, report-only diagnosis, tag vocabulary, semantic integration, topic gaps, and approved application. This mode does not use `curate.py`: that writer requires exported thread provenance and a sync manifest.
- **Mixed input:** keep each source's provenance and ownership rules; do not invent thread IDs for ordinary notes or route maintenance edits through the exporter.

Apply the current project's scope, templates, authorization and governance rules. Project-specific tag lists, experience-registration policies and budgets are inputs, not global defaults of this skill. The skill does not authorize scanning additional chats, promoting drafts, installing frameworks, or publishing new reusable capabilities.

## Exported Codex evidence

Use `$codex-memory-sync` for selected-source retention rules and `$obsidian-kb` for scoped prior knowledge. Exact full export is an explicitly authorized investigation/reproduction exception, not a prerequisite for normal note organization. The workflow in this section applies to existing or expressly approved full exports only. Read the actual templates referenced by `scripts/curate.py` in the linked vault's `06_模板`. Templates control headings and required metadata; the writer rejects unresolved placeholders and non-draft derived content.

The mapping manifest lives in the project's `.codex/` or, for a lean project, `.agents/skills/project-memory/control/`. The writer shares the exporter's directory resolver; preserve existing control files and do not recreate root metadata after cleanup.

Read the exported desktop projection and rollout messages of selected threads. One chat may contain several tasks; greeting-only chats need none. Do not deduplicate forks solely by title; compare lineage, source and task intent. Identify task goals, scope changes, steps, decisions, failed attempts, evaluation and remaining gaps. Cite `source_raw` and source record numbers/desktop item IDs. Distinguish user acceptance, observed tool evidence, model self-report and fresh verification. Never infer user satisfaction from silence.

Prepare a batch JSON: `project_dir`, `notes` (each `path`, `template` filename, `fields` object, and `sections` mapping exact heading text to Markdown), and `tasks` mapping thread IDs to arrays of `{task_id,note,status,source_hash}`. Each task must match the manifest's current source hash and note frontmatter. Supply `source_thread`, `source_raw`, and `source_hash`; cards and resources also need provenance. Include substantial sections; unavailable detail is explicitly recorded as such. See the installed pilot batch for a working example at `D:\codex-project\Knowledge-Steward\batches`.

```powershell
python "$env:USERPROFILE\.codex\skills\obsidian-curator\scripts\curate.py" --batch "D:\codex-project\Knowledge-Steward\batches\ai-hardness.json"
```

Writer preserves all template headings, replaces default business placeholders, and fills absent sections with a disclosed gap. This enforces structure, not semantic quality. Keep each card focused on one rule and its applicability, counterexample and uncertainty. Domain books organize cards; do not turn one chat into an authoritative textbook. Resource notes describe actual sources, not invented bibliographies. Generated files and manual edits have conflict checks. New findings or updated sources require a new draft path if a human has edited the prior note.

Validate with sync `verify` and project retrieval. If the same task is moved to a replacement draft, an edited prior draft is recorded in `human_owned_notes` with its previous generated hash and observed hash; it is preserved, no longer auto-managed, and remains unreviewed. This records custody, not acceptance of its content. Run writers serially; there is no interprocess lock. Human review is pending until explicitly supplied; never promote to reviewed/trusted automatically. Report coverage, stale drafts, conflicts, attachment gaps and GUI-rendering limitations.
