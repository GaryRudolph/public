---
name: optimize-docs
description: >-
  Audit and optimize documentation for agent consumption. Use when asked to
  optimize docs, run the monthly doc review, or improve agent-friendliness
  of standards and agent rule files.
---

# Optimize Documentation

Periodic review of standards and agent docs to keep them effective for both
humans and AI agents. Run monthly or whenever documentation feels stale.

## Audit checklist

Work through each area and report findings before making changes.

### 1. Context size

- Flag any single file over 300 lines — agents lose focus in long files
- Look for sections that could be split into focused files
- Check that AGENTS.md / SHARED.md stays under 120 lines

### 2. Headings and structure

- Every file should have a clear H1 and logical heading hierarchy
- Headings should be scannable — an agent reading only headings should
  understand the file's purpose and structure
- Avoid deep nesting (H4+ usually means the file should be split)

### 3. Cross-references and links

- Verify all relative links resolve to existing files
- Check for orphaned files not linked from anywhere
- Look for duplicate content across files — consolidate or cross-reference

### 4. Ambiguity and contradictions

- Search for conflicting guidance between files (e.g. standards vs agent rules)
- Flag vague language: "usually", "sometimes", "might want to" — replace with
  clear directives or explicit conditions

### 5. Discoverability (Code SEO)

- Use consistent terminology — pick one term and use it everywhere (don't mix
  "endpoint" / "route" / "path" for the same concept)
- Avoid abbreviations agents might not search for
- Add README.md files in directories that lack them to help agents orient
- Use domain-focused names over technical implementation names

### 6. Brevity

- Remove obvious comments that paraphrase their heading
- Remove stale TODO comments that have been addressed
- Trim boilerplate and filler text — every sentence should earn its tokens

### 7. Freshness

- Flag references to deprecated tools, libraries, or patterns
- Check that version numbers and links to external docs are current
- Verify agent rule files reflect current workflow

## Process

1. **Scan** — read the file tree and skim each standards file
2. **Report** — write findings to `.scratch/doc-audit.md` organized by the
   checklist above, noting file paths and specific issues
3. **Propose** — for each finding, suggest a concrete fix (reword, split, move,
   delete, or add cross-reference)
4. **Wait for approval** — do not make changes until the findings are reviewed
5. **Apply** — make approved changes, one file at a time, with commits at each
   logical step

## What not to change

- Do not rewrite content for style alone — only change what improves agent
  or human comprehension
- Do not change meaning — if guidance seems wrong, flag it for human review
  rather than silently correcting it
