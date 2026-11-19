# Existing-note maintenance

Use this mode for selected existing Obsidian notes. Its deliverable is a traceable maintenance proposal, followed by application only within the user's approved changes. This is an instruction workflow; no general vault-maintenance writer is bundled. `scripts/curate.py` remains the exported-thread writer and must not be used for arbitrary notes.

## Scope and source custody

Resolve the requested vault/project and concrete note whitelist before reading bodies. A project request does not imply all-vault or raw-chat access. Record the run ID, allowed read/write roots, intended outputs, budget and stopping conditions supplied by the current task. Reuse relevant prior results only after checking their current sources.

Freeze an inventory with canonical path, SHA-256, snapshot location, and stable run-local ID for every selected source. Record coverage as inspected, proposed change, skipped or blocked, with reasons. A line reference must identify the frozen version and manifest; a bare run-local ID is insufficient outside that run.

Inspect known sync manifests, generated indexes, human-owned records and approved documents that bind source hashes. Mark these dependencies as protected by default, including tag-only edits. If changing a protected note is necessary, propose the dependent updates and obtain the corresponding authorization before applying them. Do not edit a tracking manifest merely to hide drift, or treat an instruction-level protection list as enforced access isolation.

Use the project's actual templates for new drafts. Ordinary notes need real note paths, hashes and source locations, not fabricated `source_thread`, `source_raw` or thread-to-task mappings. If a template requires export-only fields, select a compatible template or propose a schema adaptation rather than fill false values. Preserve existing schemas for edited notes.

## Diagnose before changing

Produce a report of metadata issues, ambiguous/unresolved links, isolated pages, duplicate subjects, conflicts and stale claims. State whether checks cover the selected project, the whole vault, attachments, heading/block anchors, and generated content. An unresolved reference within the selected scope is not proof that its target is globally missing.

Retain historical evidence and quarantined references; do not restore removed samples simply to make links resolve. Do not rewrite a historical statement into the current rule without preserving its temporal meaning. Report normative conflicts separately from mechanical tag/link changes.

Use `$obsidian-kb` when scoped retrieval is needed and available, and `$obsidian-markdown` for Obsidian syntax. Read their actual instructions before use. Existing search/CLI tools may aid checks; do not assume an untested CLI, plugin or third-party skill is installed.

## Controlled tags

Start with the existing vocabulary and its consumers. Propose a small topic vocabulary with definitions, inclusion/exclusion boundaries and existing-tag mappings. Separate subject tags from project, asset-type and lifecycle tags. Record each proposed assignment's reason and source; counts alone do not establish classification quality.

Preserve old tags and unrelated properties unless replacements are explicitly in the approved diff. Case normalization, aliases, synonyms and historical names can affect queries and sync; inspect known dependencies before proposing a merge. A project's ten-tag list is an example to reuse only in that project, not a universal ontology.

For mechanical edits, parse frontmatter to compare semantics and preserve the original bytes outside the intended change when feasible. Check body text and non-tag properties, including aliases and nested values. Refuse an unsupported representation instead of forcing a broad rewrite. Notes without frontmatter need an explicit proposal for adding it; never let a tag-block edit consume an adjacent field or delimiter.

## Semantic links and navigation

Search for existing subject pages and aliases before creating a new page. For every new or replaced link, provide the source, target and relationship: for example, supporting evidence, a prerequisite, an applicable decision, or a contrasting limitation. Resolve the intended target uniquely; disambiguate duplicate titles with vault-relative paths. Validate heading/block anchors if used, or disclose that they remain unchecked.

Add an index/MOC entry or return path when useful for discovery. Do not mechanically add reciprocal links or connect every co-occurring term. Keep draft targets visibly distinguishable from reviewed knowledge. Extra links and a denser graph do not prove improved understanding.

Separate necessary navigation additions from substantive body rewrites in the diff. Protect historical conclusions and human edits; a valid target does not by itself justify a semantic connection.

## Topic gaps and drafts

Maintain a ledger with subject, existing/alias pages, source locations, missing content, classification, proposed action and validation limits:

| Class | Evidence state | Action |
| --- | --- | --- |
| A | Content already exists but is scattered or poorly connected | Reuse pages; propose summaries, links or navigation |
| B | Selected sources support a missing synthesis | Create a focused, template-complete draft with provenance |
| C | Original evidence is absent or inadequate | List research/experiment questions and needed sources |

For A/B, distinguish observed facts, source reports, inference, counterexamples and unverified claims. State when original experiments were not rerun. Preserve source hashes and precise locations; do not turn a synthesis into a new capability claim. New drafts remain unreviewed and carry appropriate uncertainty. Do not raise `status`, `confidence`, or `last_verified` merely because maintenance ran; follow any expressly approved lifecycle changes separately.

For C, do not use model recall as verified evidence. Conduct external research or new experiments only within the actual task's authorization and budget. Topic knowledge does not inherently require a Skill; formal experience eligibility follows the current project's registry policy. Do not publish registry or profile changes as a side effect of note maintenance.

## Review package and approved application

Provide a readable per-file summary plus exact diff. Include source coverage, vocabulary/assignment reasons, semantic link reasons and resolution results, gap ledger, protected/skipped notes, proposed target hashes, current baseline hashes and limitations. Staging and backup locations must be outside the formal note targets. Keep candidate generation separate from actual application and from user acceptance.

Where the task requires specific-diff approval, wait for it; existing applicable approval can be used without asking again. Record what files and changes it covers. Do not infer authorization for unrelated edits from a general organization request. If the user authorizes only a report or candidates, do not write formal targets.

Before applying, recheck the approved diff, source and target baselines, protected dependencies, canonical target paths and staged hashes. New-note targets must still be absent. Stop affected files on drift or conflict; preserve the user's current version and report differences. Never silently merge or broaden an approved proposal.

Back up existing targets and record the absence of new targets. Use one writer and a per-file journal; apply the exact approved bytes, then verify resulting hashes. Multi-file writes are not an atomic transaction. On partial failure, report completed/failed/unknown steps and inspect real state before resuming; do not blindly replay. Rollback must check for later human changes and handle newly created files explicitly.

After application, verify unchanged protected notes, unrelated metadata/body preservation, the approved link targets and actual source coverage. Compare diagnosed issues before/after and distinguish new regressions from retained gaps. Avoid date-only rewrites on unchanged sources. Repeat-run skipping depends on matching source and output hashes, not merely a prior success flag.

Deliver the actual changed-file list, backups, journal, validation evidence, remaining issues and acceptance status. State whether reading-view rendering, global graph checks or recovery tests occurred. A file/hash check does not prove semantic quality, automatic concurrency control, crash recovery, or future adherence by an agent.
