"""Driver shared by both whisper-to-markdown skills.

The two per-skill `scripts/run.py` entry points each pass us a callable
that yields `source_record` dicts from their respective source (SQLite
or `.whisper` ZIPs). Everything downstream — canonical building, content
overlay, slug recompute, tag reconciliation, write — lives here so the
skills can't diverge.

Subcommands (driven by each per-skill `run.py`):

    plan          - bootstrap or refresh per-session JSONs from source +
                    overlay any content_*.json that already exists.
                    Idempotent. Always run twice in the standard flow:
                    once before content generation (provisional titles),
                    once after (final titles + final slugs).
    merge         - reconcile raw tags across content batches against the
                    workspace vocabulary; emit `merged_tag_additions.json`
                    listing new tags that need confirmation.
    lookup-tags propose  - emit `lookup_queue.json` for the agent's
                    interactive WebSearch + AskQuestion pass.
    lookup-tags apply    - read agent decisions, rewrite per-session
                    tags, append to `tags.md`.
    write         - decision tree -> render -> write. Handles historical
                    replacement via `git mv`/`git rm` and `touch -r`.
    report        - print the run summary.

Source-record contract (yielded by the per-skill iterator):

    {
      "session_key":           "<stable, filename-safe id>",
      "source":                "macwhisper-db:<uuid>" or "<filename>.whisper",
      "source_type":           "db" | "file",
      "date_iso_utc":          "<ISO 8601 with millis>",
      "type":                  "voice-memo" | "meeting" | "other",
      "model":                 "<transcription model>",
      "raw_segments":          [ {start_ms, end_ms, speaker, text}, ... ],
      "all_speakers":          ["Speaker 1", "Kevin", ...],
      "duration_sec":          int | None,
      "provisional_title":     "<best-effort title from source>",
      "macwhisper_title_hint": "<raw MacWhisper title for subagent context>",
      "macwhisper_tags":       [str, ...],
      "truncate_keys":         [str, ...],   # ordered keys to check in config.truncate
      "source_mtime":          float | None,
    }
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from . import canonical, historical, render

TMP_ROOT = Path("/tmp/whisper_plan")
SESSIONS_DIR = TMP_ROOT / "sessions"
CONTENT_DIR = TMP_ROOT / "content"
PLAN_FILE = TMP_ROOT / "plan.json"
LOOKUP_QUEUE_FILE = TMP_ROOT / "lookup_queue.json"
LOOKUP_DECISIONS_FILE = TMP_ROOT / "lookup_decisions.json"
MERGED_TAG_ADDITIONS_FILE = TMP_ROOT / "merged_tag_additions.json"
REPORT_FILE = TMP_ROOT / "report.json"

SourceIterator = Callable[[Path], Iterable[dict]]


# ---------------------------------------------------------------------------
# tmp helpers
# ---------------------------------------------------------------------------


def _ensure_tmp() -> None:
    for d in (TMP_ROOT, SESSIONS_DIR, CONTENT_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _session_path(session_key: str) -> Path:
    return SESSIONS_DIR / f"{session_key}.json"


def _load_session(session_key: str) -> dict | None:
    return _read_json(_session_path(session_key))


def _save_session(session: dict) -> None:
    _write_json(_session_path(session["session_key"]), session)


# ---------------------------------------------------------------------------
# Content overlay (subagent output)
# ---------------------------------------------------------------------------


def _load_all_content() -> dict:
    """Merge every `content/content*.json` and `content/inline*.json` file.

    Later files win on per-session keys; tag_additions are unioned.
    """
    merged_sessions: dict[str, dict] = {}
    merged_additions: dict[str, str] = {}
    if not CONTENT_DIR.is_dir():
        return {"sessions": merged_sessions, "tag_additions": merged_additions}
    for p in sorted(CONTENT_DIR.glob("*.json")):
        data = _read_json(p, default={}) or {}
        for sk, payload in (data.get("sessions") or {}).items():
            merged_sessions[sk] = payload
        for tag, gloss in (data.get("tag_additions") or {}).items():
            if tag not in merged_additions and gloss:
                merged_additions[tag] = gloss
    return {"sessions": merged_sessions, "tag_additions": merged_additions}


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


def _format_time_local(date_iso_utc: str) -> str:
    """Best-effort HH:MM in local time. Fall back to UTC if tz unavailable."""
    try:
        dt_utc = canonical.parse_iso_utc(date_iso_utc)
    except (ValueError, TypeError):
        return ""
    try:
        local = dt_utc.astimezone()
    except (ValueError, OSError):
        local = dt_utc
    return local.strftime("%H:%M")


def _date_ymd(date_iso_utc: str) -> str:
    try:
        dt_utc = canonical.parse_iso_utc(date_iso_utc)
    except (ValueError, TypeError):
        return ""
    try:
        local = dt_utc.astimezone()
    except (ValueError, OSError):
        local = dt_utc
    return local.strftime("%Y-%m-%d")


def _compute_slug_and_path(
    title: str,
    date_ymd: str,
    session_key: str,
    sessions_by_date: dict[str, list[tuple[str, str]]],
) -> tuple[str, str]:
    """Compute (slug, workspace-relative out_path), disambiguating per date.

    `sessions_by_date[date_ymd]` is the list of `(slug, session_key)` already
    claimed for this date (excluding the current session_key, which we don't
    want colliding with itself across plan re-runs).
    """
    base = canonical.slugify(title)
    same_day = sessions_by_date.setdefault(date_ymd, [])
    claimed = {slug for slug, sk in same_day if sk != session_key}
    final = canonical.disambiguate_slug(base, claimed)
    same_day.append((final, session_key))
    year, month, _day = date_ymd.split("-")
    return final, f"{year}/{month}/{date_ymd}-{final}.md"


def _resolve_existing_note(workspace: Path, content_hash_value: str, out_path: str) -> dict | None:
    """Look for a workspace note whose content_hash matches ours.

    First check the canonical out_path; if not there, scan that day's
    folder for any file with our hash. Returns a record describing what
    to do, or None when no existing note carries this hash.
    """
    target = workspace / out_path
    if target.exists():
        existing_hash = historical.has_our_content_hash(target)
        if existing_hash == content_hash_value:
            return {"path": str(target.relative_to(workspace)), "abs_path": str(target),
                    "matched_hash": True}
    # Search the same-date directory for any note with this hash (handles
    # the case where the user renamed the file or the title changed).
    date_dir = target.parent
    if date_dir.is_dir():
        for p in sorted(date_dir.glob("*.md")):
            if historical.has_our_content_hash(p) == content_hash_value:
                return {"path": str(p.relative_to(workspace)), "abs_path": str(p),
                        "matched_hash": True}
    return None


def _resolve_existing_note_different_hash(workspace: Path, out_path: str) -> dict | None:
    target = workspace / out_path
    if not target.exists():
        return None
    existing_hash = historical.has_our_content_hash(target)
    if existing_hash:
        return {"path": str(target.relative_to(workspace)), "abs_path": str(target),
                "existing_hash": existing_hash}
    return None


def cmd_plan(workspace: Path, iter_source_records: SourceIterator) -> dict:
    """First and second plan pass. Same code path for both; idempotent."""
    _ensure_tmp()
    cfg = canonical.load_workspace_config(workspace)
    content_overlay = _load_all_content()
    overlay_sessions = content_overlay["sessions"]

    summary = {
        "workspace": str(workspace),
        "tmp_root": str(TMP_ROOT),
        "config_path": str(workspace / canonical.CONFIG_FILENAME),
        "self_mic_speakers": cfg["self_mic_speakers"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sessions": [],
        "skipped": [],
    }

    sessions_by_date: dict[str, list[tuple[str, str]]] = {}
    written_session_keys: list[str] = []

    for rec in iter_source_records(workspace):
        sk = rec["session_key"]
        try:
            truncate_after = canonical.truncate_after_ms_for(cfg, *rec.get("truncate_keys", []))
            cdict, duration_ms = canonical.build_canonical(
                date_iso_utc=rec["date_iso_utc"],
                raw_segments=rec["raw_segments"],
                self_mic_speakers=cfg["self_mic_speakers"],
                truncate_after_ms=truncate_after,
            )
        except Exception as e:
            summary["skipped"].append({"session_key": sk, "reason": f"build_canonical failed: {e}"})
            continue

        chash = canonical.content_hash(cdict)
        date_ymd = _date_ymd(rec["date_iso_utc"])
        time_local = _format_time_local(rec["date_iso_utc"])

        existing = _load_session(sk) or {}
        overlay = overlay_sessions.get(sk) or {}
        final_title = (
            overlay.get("title")
            or existing.get("title")
            or rec.get("provisional_title")
            or ""
        )
        slug, out_path = _compute_slug_and_path(final_title, date_ymd, sk, sessions_by_date)

        speakers_in_segments = sorted({s["speaker"] for s in cdict["segments"] if s.get("speaker")})

        # Carry forward existing fields (historical match, content from previous merge)
        session = {
            "session_key": sk,
            "source": rec["source"],
            "source_type": rec["source_type"],
            "date_iso_utc": rec["date_iso_utc"],
            "date_ymd": date_ymd,
            "time_local": time_local,
            "type": rec["type"],
            "model": rec.get("model", ""),
            "duration_ms": duration_ms if duration_ms is not None else (
                int(rec["duration_sec"] * 1000) if rec.get("duration_sec") else None
            ),
            "speakers": speakers_in_segments,
            "canonical": cdict,
            "content_hash": chash,
            "provisional_title": rec.get("provisional_title", ""),
            "title": final_title,
            "slug": slug,
            "out_path": out_path,
            "source_mtime": rec.get("source_mtime"),
            "summary": overlay.get("summary") or existing.get("summary"),
            "action_items": overlay.get("action_items") or existing.get("action_items") or [],
            "raw_tags": overlay.get("tags") or existing.get("raw_tags") or [],
            "tags": existing.get("tags") or list(overlay.get("tags") or []),
            "tags_proposed_new": existing.get("tags_proposed_new") or [],
            "macwhisper_tags": rec.get("macwhisper_tags") or [],
            "macwhisper_title_hint": rec.get("macwhisper_title_hint") or "",
            "historical": existing.get("historical"),
            "historical_ambiguous": existing.get("historical_ambiguous") or [],
            "config_applied": {
                "self_mic_speakers": cfg["self_mic_speakers"],
                "truncate_after_ms": truncate_after,
            },
            "status": existing.get("status") or "planned",
            "notes": existing.get("notes") or [],
        }

        # Decide the planned action and look up matching/historical notes.
        existing_match = _resolve_existing_note(workspace, chash, out_path)
        if existing_match:
            session["existing_note"] = existing_match
            session["action"] = "skip-existing-match"
        else:
            session["existing_note"] = _resolve_existing_note_different_hash(workspace, out_path)
            if session["existing_note"]:
                session["action"] = "regenerate"
            else:
                # Look for a hand-written historical equivalent (only when no
                # existing note carries our hash).
                if not session.get("historical"):
                    transcript_text = "\n".join(
                        f"[{canonical.ms_to_hhmmss(s['start_ms'])}] {s.get('speaker') or ''}: {s['text']}"
                        for s in cdict["segments"] if s.get("text")
                    )
                    matches = historical.all_historical_matches(
                        workspace, date_ymd, chash, transcript_text
                    )
                    if len(matches) == 1:
                        session["historical"] = matches[0]
                        session["action"] = "historical-replace"
                    elif len(matches) > 1:
                        session["historical_ambiguous"] = [m["path"] for m in matches]
                        session["action"] = "historical-ambiguous-skip"
                    else:
                        session["action"] = "create"
                else:
                    session["action"] = "historical-replace"

        _save_session(session)
        written_session_keys.append(sk)
        summary["sessions"].append({
            "session_key": sk,
            "title": final_title,
            "slug": slug,
            "out_path": out_path,
            "action": session["action"],
            "content_hash": chash,
        })

    summary["session_keys"] = written_session_keys
    _write_json(PLAN_FILE, summary)
    return summary


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


def _parse_tags_md(path: Path) -> dict:
    """Parse `tags.md` into {tag_name: gloss} preserving order.

    The format is a Markdown file grouped under `## <category>` headings,
    one bullet per tag: ``- `tag-name` — gloss``. We don't care about
    categories for canonicalization, only the set of known tags.
    """
    out: dict[str, str] = {}
    if not path.exists():
        return out
    bullet_re = re.compile(r"^\s*-\s*`([a-z0-9][a-z0-9-]*)`\s*(?:[—-]\s*(.*))?$")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = bullet_re.match(line)
        if m:
            out[m.group(1)] = (m.group(2) or "").strip()
    return out


def _canonicalize_tag(tag: str, vocab: dict[str, str]) -> str | None:
    """Try to map a raw tag to a vocabulary entry. Returns the canonical
    tag name, or None if no unambiguous match.

    Rules:
      1. Exact match in vocab -> that tag.
      2. The raw tag is a prefix of exactly one vocab entry up to the next
         hyphen (e.g. `nick` -> `nick-foo` when only one `nick-*` exists).
      3. Otherwise None.
    """
    t = tag.strip().lower()
    if not t:
        return None
    if t in vocab:
        return t
    matches = [v for v in vocab if v == t or v.startswith(t + "-")]
    if len(matches) == 1:
        return matches[0]
    return None


_PERSON_HINT_RE = re.compile(r"^[a-z]+(?:-[a-z]+){0,2}$")


def _looks_like_person(tag: str) -> bool:
    """Heuristic: a tag looks like a person if it's `first` or `first-last`."""
    return bool(_PERSON_HINT_RE.match(tag))


def cmd_merge(workspace: Path) -> dict:
    """Reconcile raw tags across content batches; emit per-session `tags` and
    a `merged_tag_additions.json` for the lookup-tags step.
    """
    _ensure_tmp()
    tags_md = _parse_tags_md(workspace / "tags.md")
    overlay = _load_all_content()
    overlay_sessions = overlay["sessions"]
    overlay_additions = overlay["tag_additions"]

    per_session_keys = [p.stem for p in SESSIONS_DIR.glob("*.json")]
    canonicalized = 0
    new_tags: dict[str, dict] = {}

    for sk in per_session_keys:
        session = _load_session(sk)
        if not session:
            continue
        raw_tags = overlay_sessions.get(sk, {}).get("tags") or session.get("raw_tags") or []
        seen: list[str] = []
        ambiguous: list[str] = []
        for t in raw_tags:
            t_lower = t.strip().lower()
            if not t_lower:
                continue
            canonical_name = _canonicalize_tag(t_lower, tags_md)
            if canonical_name:
                if canonical_name not in seen:
                    seen.append(canonical_name)
            else:
                if t_lower not in seen:
                    seen.append(t_lower)
                if _looks_like_person(t_lower):
                    ambiguous.append(t_lower)
                entry = new_tags.setdefault(t_lower, {
                    "tag": t_lower,
                    "gloss_proposals": [],
                    "sessions": [],
                    "looks_like_person": _looks_like_person(t_lower),
                })
                gloss = overlay_additions.get(t_lower)
                if gloss and gloss not in entry["gloss_proposals"]:
                    entry["gloss_proposals"].append(gloss)
                entry["sessions"].append({
                    "session_key": sk,
                    "title": session.get("title") or session.get("provisional_title"),
                    "type": session.get("type"),
                    "speakers": session.get("speakers", []),
                    "macwhisper_title_hint": session.get("macwhisper_title_hint", ""),
                })

        session["raw_tags"] = raw_tags
        session["tags"] = seen
        session["tags_proposed_new"] = [t for t in seen if t not in tags_md]
        canonicalized += 1
        _save_session(session)

    _write_json(MERGED_TAG_ADDITIONS_FILE, {
        "tag_additions": list(new_tags.values()),
        "workspace_vocab_size": len(tags_md),
    })

    return {
        "canonicalized_sessions": canonicalized,
        "new_tags": list(new_tags.keys()),
        "merged_tag_additions": str(MERGED_TAG_ADDITIONS_FILE),
    }


# ---------------------------------------------------------------------------
# lookup-tags
# ---------------------------------------------------------------------------


def cmd_lookup_tags_propose(workspace: Path) -> dict:
    """Emit `lookup_queue.json` listing person tags that need confirmation."""
    _ensure_tmp()
    merged = _read_json(MERGED_TAG_ADDITIONS_FILE, default={"tag_additions": []})
    queue = []
    for entry in merged.get("tag_additions", []):
        if not entry.get("looks_like_person"):
            continue
        queue.append({
            "tag": entry["tag"],
            "gloss_proposals": entry.get("gloss_proposals", []),
            "sessions": entry.get("sessions", []),
            "status": "pending",
        })
    _write_json(LOOKUP_QUEUE_FILE, {"queue": queue})
    return {"queue_size": len(queue), "queue_file": str(LOOKUP_QUEUE_FILE)}


def _append_tags_md(workspace: Path, additions: list[tuple[str, str]]) -> None:
    """Append new tags to `tags.md` under a `## People` section.

    Additive only — we never delete or rename. If the People section
    exists, append below the last bullet in it. Otherwise create the
    section at the end of the file.
    """
    if not additions:
        return
    tags_path = workspace / "tags.md"
    text = tags_path.read_text(encoding="utf-8") if tags_path.exists() else ""

    lines = text.splitlines()
    insert_at = len(lines)
    # Find "## People" and the next "## " header (or EOF)
    for i, line in enumerate(lines):
        if line.strip().lower() == "## people":
            insert_at = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    insert_at = j
                    break
            break
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("## People")
        lines.append("")
        insert_at = len(lines)

    # Trim trailing blank lines inside the People section so we append cleanly.
    while insert_at > 0 and not lines[insert_at - 1].strip():
        insert_at -= 1

    new_lines = [f"- `{tag}` — {gloss}" for tag, gloss in additions]
    lines[insert_at:insert_at] = new_lines
    if insert_at == len(lines) - len(new_lines):
        lines.append("")
    tags_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def cmd_lookup_tags_apply(workspace: Path) -> dict:
    """Apply `lookup_decisions.json` to per-session tags and `tags.md`.

    Decisions schema:
        {
          "decisions": [
            { "tag": "nick", "action": "rename", "new_name": "nick-holcomb",
              "gloss": "Nick Holcomb — Agerpoint backend engineer" },
            { "tag": "carl", "action": "rename", "new_name": "karl-steddom",
              "gloss": "" },                              # gloss optional if existing
            { "tag": "someone", "action": "keep",
              "gloss": "Someone — single-name reference, no last name known" },
            { "tag": "noise",  "action": "skip" }
          ]
        }
    """
    _ensure_tmp()
    decisions_doc = _read_json(LOOKUP_DECISIONS_FILE, default={"decisions": []})
    decisions = decisions_doc.get("decisions") or []
    rename_map: dict[str, str | None] = {}
    new_glosses: list[tuple[str, str]] = []

    existing_vocab = _parse_tags_md(workspace / "tags.md")

    for d in decisions:
        tag = (d.get("tag") or "").strip().lower()
        action = (d.get("action") or "").strip().lower()
        if not tag or not action:
            continue
        if action == "rename":
            new_name = (d.get("new_name") or "").strip().lower()
            if not new_name:
                continue
            rename_map[tag] = new_name
            gloss = (d.get("gloss") or "").strip()
            if gloss and new_name not in existing_vocab:
                new_glosses.append((new_name, gloss))
                existing_vocab[new_name] = gloss
        elif action == "keep":
            rename_map[tag] = tag
            gloss = (d.get("gloss") or "").strip()
            if gloss and tag not in existing_vocab:
                new_glosses.append((tag, gloss))
                existing_vocab[tag] = gloss
        elif action == "skip":
            rename_map[tag] = None  # drop this tag from sessions

    updated_sessions = 0
    for sk_path in sorted(SESSIONS_DIR.glob("*.json")):
        session = _read_json(sk_path)
        if not session:
            continue
        tags = list(session.get("tags") or [])
        changed = False
        new_tags: list[str] = []
        for t in tags:
            if t in rename_map:
                target = rename_map[t]
                if target is None:
                    changed = True
                    continue
                if target != t:
                    changed = True
                if target not in new_tags:
                    new_tags.append(target)
            else:
                if t not in new_tags:
                    new_tags.append(t)
        if changed:
            session["tags"] = new_tags
            session["tags_proposed_new"] = [t for t in new_tags if t not in existing_vocab]
            _save_session(session)
            updated_sessions += 1

    if new_glosses:
        _append_tags_md(workspace, new_glosses)

    return {
        "updated_sessions": updated_sessions,
        "renames": rename_map,
        "tags_md_additions": [t for t, _ in new_glosses],
    }


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


def _is_git_repo(workspace: Path) -> bool:
    return (workspace / ".git").exists()


def _git(workspace: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", "-C", str(workspace), *args],
        capture_output=True, text=True
    )
    return proc.returncode, proc.stdout, proc.stderr


def _touch_mtime(target: Path, mtime: float | None, source_path: Path | None = None) -> None:
    if mtime is not None:
        try:
            os.utime(target, (mtime, mtime))
        except OSError:
            pass
        return
    if source_path and source_path.exists():
        try:
            st = source_path.stat()
            os.utime(target, (st.st_atime, st.st_mtime))
        except OSError:
            pass


def cmd_write(workspace: Path) -> dict:
    """Decision tree -> render -> write. Handles git mv / git rm / touch."""
    _ensure_tmp()
    result = {
        "created": [], "regenerated": [], "skipped": [], "errors": [],
        "historical_replaced": [], "historical_ambiguous": [],
        "source_only_updates": [],
    }
    for sk_path in sorted(SESSIONS_DIR.glob("*.json")):
        session = _read_json(sk_path)
        if not session:
            continue
        sk = session["session_key"]
        out_path = workspace / session["out_path"]
        action = session.get("action", "create")

        if action == "skip-existing-match":
            existing = session.get("existing_note") or {}
            existing_abs = Path(existing.get("abs_path") or out_path)
            try:
                head = existing_abs.read_text(encoding="utf-8")
            except OSError:
                result["errors"].append({"session_key": sk, "error": "missing existing note"})
                continue
            meta, body = historical.split_frontmatter(head)
            current_source = (meta or {}).get("source", "").strip().strip('"').strip("'")
            current_source_type = (meta or {}).get("source_type", "").strip().strip('"').strip("'")
            if current_source != session["source"] or current_source_type != session["source_type"]:
                rebuilt: list[str] = ["---"]
                for k, v in (meta or {}).items():
                    if k == "source":
                        rebuilt.append(f'source: "{session["source"]}"')
                    elif k == "source_type":
                        rebuilt.append(f"source_type: {session['source_type']}")
                    else:
                        rebuilt.append(f"{k}: {v}")
                rebuilt.append("---")
                rebuilt.append("")
                rebuilt.append(body.lstrip())
                existing_abs.write_text("\n".join(rebuilt), encoding="utf-8")
                result["source_only_updates"].append(str(existing_abs.relative_to(workspace)))
            else:
                result["skipped"].append(str(existing_abs.relative_to(workspace)))
            session["status"] = "skipped"
            _save_session(session)
            continue

        if action == "historical-ambiguous-skip":
            result["historical_ambiguous"].append({
                "session_key": sk,
                "title": session.get("title"),
                "candidates": session.get("historical_ambiguous", []),
            })
            session["status"] = "skipped"
            _save_session(session)
            continue

        if not session.get("title"):
            result["errors"].append({
                "session_key": sk,
                "error": "no title — run the content generation step before write",
            })
            continue
        if session.get("summary") is None:
            result["errors"].append({
                "session_key": sk,
                "error": "no summary — run the content generation step before write",
            })
            continue

        markdown = render.render_note(session)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")
        _touch_mtime(out_path, session.get("source_mtime"))
        rel = str(out_path.relative_to(workspace))

        if action == "regenerate":
            result["regenerated"].append(rel)
        elif action == "historical-replace":
            hist = session.get("historical") or {}
            hist_abs = Path(hist.get("abs_path", ""))
            if hist_abs and hist_abs.exists() and hist_abs != out_path:
                if _is_git_repo(workspace):
                    rc, _, err = _git(workspace, "rm", "-f",
                                      str(hist_abs.relative_to(workspace)))
                    if rc != 0:
                        try:
                            hist_abs.unlink()
                        except OSError:
                            pass
                else:
                    try:
                        hist_abs.unlink()
                    except OSError:
                        pass
            result["historical_replaced"].append({
                "old": hist.get("path"),
                "new": rel,
                "overlap": hist.get("overlap"),
            })
        else:
            result["created"].append(rel)

        session["status"] = "written"
        _save_session(session)

    _write_json(REPORT_FILE, result)
    return result


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def cmd_report(workspace: Path) -> str:
    """Print a human-readable run summary based on REPORT_FILE."""
    report = _read_json(REPORT_FILE, default={})
    plan = _read_json(PLAN_FILE, default={})
    merge_data = _read_json(MERGED_TAG_ADDITIONS_FILE, default={"tag_additions": []})

    def section(label: str, items: list, fmt=lambda x: f"  - {x}") -> list[str]:
        if not items:
            return [f"{label}: 0"]
        lines = [f"{label}: {len(items)}"]
        for item in items:
            lines.append(fmt(item))
        return lines

    out: list[str] = []
    out.append(f"Workspace: {plan.get('workspace', workspace)}")
    out.append(f"Sessions planned: {len(plan.get('sessions', []))}")
    out.append(f"Skipped (planner): {len(plan.get('skipped', []))}")
    out.append("")

    out += section("Created", report.get("created", []))
    out += section("Regenerated", report.get("regenerated", []))
    out += section(
        "Historical replaced",
        report.get("historical_replaced", []),
        fmt=lambda x: f"  - {x.get('old')} → {x.get('new')} (overlap {x.get('overlap', 0):.2f})",
    )
    out += section(
        "Ambiguous (skipped)",
        report.get("historical_ambiguous", []),
        fmt=lambda x: f"  - {x.get('session_key')}: {', '.join(x.get('candidates', []))}",
    )
    out += section("Source-only frontmatter rewrites", report.get("source_only_updates", []))
    out += section("Unchanged (skipped)", report.get("skipped", []))
    out += section("Errors", report.get("errors", []),
                   fmt=lambda x: f"  - {x.get('session_key')}: {x.get('error')}")
    out.append("")
    new_tags = [t["tag"] for t in merge_data.get("tag_additions", [])]
    if new_tags:
        out.append(f"New tags proposed: {', '.join(sorted(new_tags))}")
    else:
        out.append("New tags proposed: none")

    text = "\n".join(out)
    sys.stdout.write(text + "\n")
    return text


# ---------------------------------------------------------------------------
# entry-point helper used by both per-skill run.py scripts
# ---------------------------------------------------------------------------


def main(argv: list[str], iter_source_records: SourceIterator) -> int:
    """Argparse-driven entry. The per-skill `run.py` calls this with its own
    source iterator. Returns a process exit code.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="whisper-runner",
                                     description="Whisper-to-Markdown driver")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_workspace(p):
        p.add_argument("--workspace", required=True,
                       help="path to the notes workspace root")

    add_workspace(sub.add_parser("plan"))
    add_workspace(sub.add_parser("merge"))
    add_workspace(sub.add_parser("write"))
    add_workspace(sub.add_parser("report"))

    lookup = sub.add_parser("lookup-tags")
    lookup_sub = lookup.add_subparsers(dest="phase", required=True)
    add_workspace(lookup_sub.add_parser("propose"))
    add_workspace(lookup_sub.add_parser("apply"))

    args = parser.parse_args(argv)
    workspace = Path(args.workspace).expanduser().resolve()

    if args.cmd == "plan":
        out = cmd_plan(workspace, iter_source_records)
        print(json.dumps({"sessions": len(out.get("sessions", [])),
                          "skipped": len(out.get("skipped", []))}))
    elif args.cmd == "merge":
        out = cmd_merge(workspace)
        print(json.dumps(out, indent=2))
    elif args.cmd == "write":
        out = cmd_write(workspace)
        print(json.dumps({k: len(v) if isinstance(v, list) else v
                          for k, v in out.items()}))
    elif args.cmd == "report":
        cmd_report(workspace)
    elif args.cmd == "lookup-tags":
        if args.phase == "propose":
            out = cmd_lookup_tags_propose(workspace)
            print(json.dumps(out, indent=2))
        elif args.phase == "apply":
            out = cmd_lookup_tags_apply(workspace)
            print(json.dumps(out, indent=2))
    return 0
