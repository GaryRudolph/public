"""Historical-equivalent search and transcript-overlap scoring.

Before we generate a brand-new note for a recording, we look for any
pre-existing Markdown file on the same date that might already cover the
recording — hand-written notes, exports from another tool, or earlier
transcripts in a different format.

The rule (from SPEC.md):
  - Search scope: only `YYYY/MM/YYYY-MM-DD-*.md` for the recording date.
  - A file is a "historical candidate" iff its frontmatter has no
    `content_hash` (i.e. wasn't written by this skill).
  - Compute the fraction of the new transcript's >= 6-word chunks that
    appear as substrings in the candidate's normalized body.
  - Threshold: >= 0.70 overlap counts as a match.

When a single candidate matches in SPEC v2 we do NOT silently replace —
the matched body is passed to the content-generation step as extra input
and rendered verbatim in the new note's `## Original notes` section.
Replacement of the old file happens at write time.
"""

from __future__ import annotations

import re
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TIMESTAMP_PREFIX_RE = re.compile(r"^\s*\[\d{1,2}:\d{2}(?::\d{2})?\]\s*", re.MULTILINE)
_SPEAKER_PREFIX_RE = re.compile(
    r"^\s*(?:[A-Z][A-Za-z0-9 ._-]{0,40}|Speaker\s*\d+):\s*", re.MULTILINE
)
_WORD_RE = re.compile(r"[a-z0-9]+")


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    """Strip leading `---`-delimited frontmatter. Returns (parsed_meta, body).

    The parser is intentionally minimal — we only need to detect a
    `content_hash:` line. Anything fancier (lists, nested maps) is
    treated as opaque.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def has_our_content_hash(path: Path) -> str | None:
    """Return the file's `content_hash` frontmatter value, or None."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(8192)
    except OSError:
        return None
    meta, _ = split_frontmatter(head)
    if not meta:
        return None
    val = meta.get("content_hash") or ""
    val = val.strip().strip('"').strip("'")
    return val or None


def normalize_for_overlap(text: str) -> str:
    """Lowercase, strip transcript prefixes, collapse whitespace."""
    out = _TIMESTAMP_PREFIX_RE.sub("", text)
    out = _SPEAKER_PREFIX_RE.sub("", out)
    out = out.lower()
    out = " ".join(out.split())
    return out


def transcript_chunks(text: str, min_words: int = 6) -> list[str]:
    """Split normalized text into sentence-like chunks of >= `min_words`.

    We split on punctuation boundaries (period, ?, !) and discard short
    fragments. This is the unit of overlap matching against the candidate
    body — we count what fraction of these chunks appear in the candidate.
    """
    pieces = re.split(r"[.!?]+", text)
    out = []
    for piece in pieces:
        words = _WORD_RE.findall(piece)
        if len(words) >= min_words:
            out.append(" ".join(words))
    return out


def overlap_fraction(new_normalized: str, candidate_normalized: str) -> float:
    """Fraction of new-transcript chunks present as substrings in candidate."""
    chunks = transcript_chunks(new_normalized)
    if not chunks:
        return 0.0
    hits = sum(1 for c in chunks if c in candidate_normalized)
    return hits / len(chunks)


def find_historical_candidates(
    workspace: Path, date_ymd: str, current_content_hash: str
) -> list[Path]:
    """Return same-date markdown files that look like hand-written candidates.

    Excludes files that already carry our frontmatter (any `content_hash`).
    A file whose `content_hash` matches `current_content_hash` is also
    excluded — that's the standard idempotency path, not a historical match.
    """
    year, month, _day = date_ymd.split("-")
    dir_ = Path(workspace) / year / month
    if not dir_.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(dir_.glob(f"{date_ymd}-*.md")):
        existing_hash = has_our_content_hash(p)
        if existing_hash is None:
            out.append(p)
        # Files with our content_hash (matching or not) are handled by the
        # standard idempotency decision tree, not by this historical search.
    return out


def extract_handwritten_body(path: Path) -> str:
    """Read the file and strip leading `---` frontmatter if any."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    _meta, body = split_frontmatter(text)
    return body.strip()


def match_historical(
    workspace: Path,
    date_ymd: str,
    current_content_hash: str,
    new_transcript_text: str,
    threshold: float = 0.7,
) -> dict | None:
    """Find a single matching historical file. Returns dict or None.

    Result shape on a single hit:

        {
          "path":     "<workspace-relative path>",
          "abs_path": "<absolute path>",
          "overlap":  <float>,
          "body":     "<verbatim hand-written body, frontmatter stripped>",
        }

    On zero or multiple matches: returns None and (for multiple) the
    caller can re-call with a lower threshold or surface the ambiguity in
    the run summary by re-walking the candidate list themselves.
    """
    candidates = find_historical_candidates(workspace, date_ymd, current_content_hash)
    if not candidates:
        return None
    new_norm = normalize_for_overlap(new_transcript_text)
    hits: list[tuple[Path, float, str]] = []
    for cand in candidates:
        body = extract_handwritten_body(cand)
        cand_norm = normalize_for_overlap(body)
        overlap = overlap_fraction(new_norm, cand_norm)
        if overlap >= threshold:
            hits.append((cand, overlap, body))
    if len(hits) != 1:
        return None
    path, overlap, body = hits[0]
    return {
        "path": str(path.relative_to(Path(workspace))),
        "abs_path": str(path),
        "overlap": overlap,
        "body": body,
    }


def all_historical_matches(
    workspace: Path,
    date_ymd: str,
    current_content_hash: str,
    new_transcript_text: str,
    threshold: float = 0.7,
) -> list[dict]:
    """Return every candidate >= threshold. Used to detect ambiguity."""
    candidates = find_historical_candidates(workspace, date_ymd, current_content_hash)
    new_norm = normalize_for_overlap(new_transcript_text)
    out = []
    for cand in candidates:
        body = extract_handwritten_body(cand)
        cand_norm = normalize_for_overlap(body)
        overlap = overlap_fraction(new_norm, cand_norm)
        if overlap >= threshold:
            out.append({
                "path": str(cand.relative_to(Path(workspace))),
                "abs_path": str(cand),
                "overlap": overlap,
                "body": body,
            })
    return out
