"""Shared library for the whisper-to-markdown skills.

Two thin per-source entry points live in
`skills/personal-whisper-to-markdown{,-db}/scripts/run.py` and import from
this package. The split is:

- canonical:  source-agnostic transforms (dedup, truncation, hash, slug).
- render:     YAML frontmatter + body assembly, including the Original
              notes section when a historical match is folded in.
- historical: historical-equivalent search + transcript-overlap scoring.
- runner:     plan/write/merge/lookup-tags/report driver shared by both
              entry points.

Everything is stdlib-only (Python 3 on macOS ships /usr/bin/python3).
"""
