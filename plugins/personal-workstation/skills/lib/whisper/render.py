"""Final-note rendering: YAML frontmatter + body sections.

A session JSON (the per-session record produced by the planner and filled
in by the content-generation step) renders into a Markdown string with
this section order:

    ---
    <YAML frontmatter>
    ---

    # <title>

    ## Summary
    ## Action Items     (omitted when empty)
    ## Original notes   (only when a historical match was folded in)
    ## Transcript

The Original notes section is the SPEC v2 addition: when historical.py
finds a >= 70% transcript-overlap candidate, we don't silently replace
it — we render its hand-written body verbatim as a blockquote between
Action Items and Transcript.
"""

from __future__ import annotations

from . import canonical


def _yaml_str(s: str) -> str:
    """Quote a YAML scalar conservatively. We never emit multi-line scalars."""
    if s is None:
        return '""'
    s = str(s)
    needs_quote = (
        not s
        or s[0] in "!&*?|>%@`#-:,[]{}"
        or s.lower() in ("yes", "no", "true", "false", "null", "~")
        or any(ch in s for ch in [":", "#", "\n", "\t"])
        or s.strip() != s
    )
    if needs_quote:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def _yaml_list(items: list[str]) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join(_yaml_str(i) for i in items) + "]"


def render_frontmatter(meta: dict) -> str:
    """Emit a YAML frontmatter block (without leading/trailing `---` lines)."""
    out: list[str] = []
    out.append(f"title: {_yaml_str(meta.get('title', ''))}")
    out.append(f"date: {meta.get('date', '')}")
    if meta.get("time"):
        out.append(f"time: {_yaml_str(meta['time'])}")
    if meta.get("duration"):
        out.append(f"duration: {meta['duration']}")
    out.append(f"type: {meta.get('type', 'other')}")
    out.append(f"speakers: {_yaml_list(meta.get('speakers') or [])}")
    if meta.get("model"):
        out.append(f"model: {meta['model']}")
    out.append(f"tags: {_yaml_list(meta.get('tags') or [])}")
    out.append(f"source: {_yaml_str(meta.get('source', ''))}")
    out.append(f"source_type: {meta.get('source_type', '')}")
    out.append(f"content_hash: {meta.get('content_hash', '')}")
    return "\n".join(out)


def render_transcript(segments: list[dict], speakers: list[str]) -> str:
    """Format segments as `[HH:MM:SS] <speaker>: <text>` lines.

    For single-speaker recordings (voice memos), omit the speaker label per
    SPEC. Stub-speaker names (`Speaker N`) pass through as-is.
    """
    distinct = sorted({s.get("speaker") for s in segments if s.get("speaker")})
    single_speaker = len(distinct) <= 1
    lines: list[str] = []
    for seg in segments:
        ts = canonical.ms_to_hhmmss(int(seg["start_ms"]))
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if single_speaker or not seg.get("speaker"):
            lines.append(f"[{ts}] {text}")
        else:
            lines.append(f"[{ts}] {seg['speaker']}: {text}")
    return "\n".join(lines)


def _blockquote(text: str) -> str:
    """Render `text` as a Markdown blockquote, preserving blank lines."""
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def render_note(session: dict) -> str:
    """Assemble the full Markdown note from a per-session JSON record.

    Expected `session` keys (all required unless noted):

      - title, date, time?, duration_ms?, type, speakers, model?, tags,
        source, source_type, content_hash
      - summary:        str
      - action_items:   list[str]                (optional; section omitted if empty)
      - canonical:      dict with `segments` list
      - historical:     {"body": "<verbatim>"}   (optional; renders ## Original notes)
    """
    meta = {
        "title": session.get("title", ""),
        "date": session.get("date_ymd", ""),
        "time": session.get("time_local") or session.get("time") or "",
        "duration": canonical.format_duration_ms(session.get("duration_ms")),
        "type": session.get("type", "other"),
        "speakers": session.get("speakers") or [],
        "model": session.get("model", ""),
        "tags": session.get("tags") or [],
        "source": session.get("source", ""),
        "source_type": session.get("source_type", ""),
        "content_hash": session.get("content_hash", ""),
    }
    body: list[str] = []
    body.append("---")
    body.append(render_frontmatter(meta))
    body.append("---")
    body.append("")
    body.append(f"# {session.get('title', '')}")
    body.append("")
    body.append("## Summary")
    body.append("")
    body.append((session.get("summary") or "").strip())
    body.append("")

    action_items = [a.strip() for a in (session.get("action_items") or []) if a and a.strip()]
    if action_items:
        body.append("## Action Items")
        body.append("")
        for item in action_items:
            body.append(f"- {item}")
        body.append("")

    historical = session.get("historical") or {}
    original_body = (historical.get("body") or "").strip()
    if original_body:
        body.append("## Original notes")
        body.append("")
        body.append(_blockquote(original_body))
        body.append("")

    body.append("## Transcript")
    body.append("")
    segments = (session.get("canonical") or {}).get("segments") or []
    body.append(render_transcript(segments, session.get("speakers") or []))
    body.append("")
    return "\n".join(body)
