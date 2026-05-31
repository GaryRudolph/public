"""Human-readable summary of a planned or applied operation.

`report.py` only formats text. It never deletes anything and it never tells the
caller that the engine deleted anything — per the safety contract the source
session is always retained, and the user removes originals manually inside
MacWhisper after they have verified the new sessions (§1).

"Files safe to delete" therefore lists only engine-owned temporary artifacts
(the staging directory); the source recording's rows and audio are always under
"originals to retain".
"""

from __future__ import annotations

from typing import Sequence

from .backup import BackupManifest
from .clone import ClonePlan, CloneResult
from .verify import VerificationReport


def render_plan_summary(
    op: str,
    source_session_ids: Sequence[str],
    clone_plans: Sequence[ClonePlan],
    *,
    staging_dir: str | None = None,
    backup_media_count: int = 0,
) -> str:
    """Summarize a dry-run plan (no writes performed yet)."""
    lines: list[str] = []
    lines.append(f"Operation: {op}")
    lines.append(f"Source session(s) (RETAINED, never deleted): {', '.join(source_session_ids)}")
    lines.append("")
    lines.append(f"New sessions to create: {len(clone_plans)}")
    for plan in clone_plans:
        lines.append(f"  - {plan.final_title}")
        lines.append(f"      session id : {plan.new_session_id_hex}")
        if plan.parent_table:
            lines.append(f"      {plan.parent_table}: {plan.parent_id_hex}")
        lines.append(f"      lines      : {len(plan.lines)}")
        lines.append(f"      speakers   : {len(plan.speaker_links)}")
        lines.append(f"      duration   : {_fmt_ms(plan.expected_duration_ms)}")
        for m in plan.media:
            lines.append(f"      audio      : {m.filename}  ({_fmt_ms(m.expected_duration_ms)})")
    lines.append("")
    lines.append(f"Files that will be backed up before any write: {backup_media_count} media + main.sqlite")
    if staging_dir:
        lines.append(f"Staged audio (temp, safe to delete after apply): {staging_dir}")
    lines.append("")
    lines.append("No database or audio has been modified yet. Approve to apply.")
    return "\n".join(lines)


def render_apply_summary(
    op: str,
    source_session_ids: Sequence[str],
    results: Sequence[CloneResult],
    verifications: Sequence[VerificationReport],
    *,
    manifest: BackupManifest | None = None,
    staging_dir: str | None = None,
) -> str:
    """Summarize a completed apply, including verification status."""
    lines: list[str] = []
    lines.append(f"Operation applied: {op}")
    if manifest is not None:
        lines.append(f"Backup: {manifest.backup_dir}")
    lines.append("")

    lines.append("Created sessions:")
    for result in results:
        lines.append(f"  - session {result.new_session_id_hex}")
        if result.parent_id_hex:
            lines.append(f"      parent : {result.parent_id_hex}")
        lines.append(
            f"      rows   : {result.inserted_lines} lines, "
            f"{result.inserted_media} media, {result.inserted_speaker_links} speaker links"
        )
        for path in result.written_files:
            lines.append(f"      file   : {path}")
    lines.append("")

    lines.append("Verification:")
    all_ok = True
    for report in verifications:
        status = "OK" if report.ok else "FAILED"
        lines.append(f"  - {report.session_id_hex}: {status}")
        for check in report.failures():
            all_ok = False
            lines.append(f"      ! {check.name}: {check.detail}")
    if all_ok:
        lines.append("  all checks passed")
    lines.append("")

    lines.append("Originals to retain (NOT deleted by this tool):")
    for sid in source_session_ids:
        lines.append(f"  - source session {sid} and its audio remain untouched")
    lines.append("  Delete the originals manually inside MacWhisper once you've verified the new sessions.")
    lines.append("")

    lines.append("Safe to delete (engine temp only):")
    if staging_dir:
        lines.append(f"  - staging dir {staging_dir}")
    else:
        lines.append("  - (none)")
    if not all_ok and manifest is not None:
        lines.append("")
        lines.append(f"Verification failed — restore from {manifest.backup_dir} if needed.")
    return "\n".join(lines)


def _fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "unknown"
    seconds = ms // 1000
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"
