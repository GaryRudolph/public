#!/usr/bin/env python3
"""Split-combine orchestrator for personal-whisper-split-combine-db.

Thin wrapper around the shared `whisper_edit` engine. Calls split and combine
IN-PROCESS — does NOT shell out to or re-invoke the split or combine skills.
Exposes three subcommands:

    python3 scripts/run.py identify  [--recording 1|2] [--title STR] [--date DATE] [--db PATH]
    python3 scripts/run.py plan      --recording1 HEX --recording2 HEX [--split-ms MS] [--db PATH]
    python3 scripts/run.py apply     [--split-plan PATH] [--combine-plan PATH] [--no-process-check]

Scenario:
    Recording 1 = meeting1 + head of meeting2
    Recording 2 = tail of meeting2

    plan splits Recording 1 → Split 1 (meeting1) + head-fragment
    plan combines head-fragment + Recording 2 → meeting2-combined

    apply executes both plans in sequence; prints a retain-vs-delete summary.

Safety: never run `apply` against the live MacWhisper DB while MacWhisper is
running. Use --db + --no-process-check for backup-copy validation only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB_ROOT = HERE.parent.parent / "lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from whisper_edit import (  # noqa: E402
    MacWhisperRunningError,
    WhisperEditError,
    apply,
    db,
    identify,
    load_bundle,
    plan_combine,
    plan_split,
    split,
)
from whisper_edit.backup import DEFAULT_BACKUP_ROOT  # noqa: E402
from whisper_edit.engine import DEFAULT_PLAN_ROOT, OperationPlan  # noqa: E402
from whisper_edit.model import (  # noqa: E402
    Bundle,
    MediaFile,
    OwnerKind,
    RecordedMeeting,
    SessionKind,
    SessionRow,
    Speaker,
    TranscriptLine,
    VoiceMemo,
)

LIVE_DB = db.DEFAULT_DB_PATH
SPLIT_PLAN_FILENAME = "split-plan.json"
COMBINE_PLAN_FILENAME = "combine-plan.json"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _NotRunningChecker:
    """Process checker that always reports MacWhisper as NOT running.

    Use ONLY when operating against a backup copy — never against the live DB.
    """

    def is_macwhisper_running(self) -> bool:
        return False


def _resolve_db(args_db: str | None) -> Path:
    return Path(args_db) if args_db else LIVE_DB


def _ms_to_human(ms: int | None) -> str:
    if ms is None:
        return "unknown"
    s = ms // 1000
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{sec:02d}s"
    if m:
        return f"{m}m{sec:02d}s"
    return f"{sec}s"


def _write_named_plan(plan: OperationPlan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")


def _clone_plan_to_bundle(
    clone_plan: "whisper_edit.clone.ClonePlan",
    source_kind: SessionKind,
    external_media_dir: Path,
) -> Bundle:
    """Build a minimal Bundle proxy from a ClonePlan for combine planning.

    The proxy uses the ClonePlan's staged audio paths as media file paths.
    The staged files exist on disk after plan_split returns (they were created
    by stage_target_audio). The combine plan can then reference those staged
    paths as source audio for the concatenation.
    """
    session = SessionRow(
        id_hex=clone_plan.new_session_id_hex,
        date_created=clone_plan.created_at,
        user_chosen_title=clone_plan.final_title,
        ai_title=None,
        recorded_meeting_id_hex=(clone_plan.parent_id_hex if source_kind == SessionKind.MEETING else None),
        voice_memo_id_hex=(clone_plan.parent_id_hex if source_kind == SessionKind.VOICE_MEMO else None),
        system_audio_recording_id_hex=None,
        playback_duration=(
            clone_plan.expected_duration_ms / 1000.0
            if clone_plan.expected_duration_ms is not None
            else None
        ),
        raw={},
    )

    lines = tuple(
        TranscriptLine(
            id_hex=lp.id_hex,
            start_ms=lp.start_ms,
            end_ms=lp.end_ms,
            text=lp.text,
            speaker_id_hex=lp.speaker_id_hex,
            words_json=lp.words_json,
            is_favorite=lp.is_favorite,
        )
        for lp in clone_plan.lines
    )

    media_files = tuple(
        MediaFile(
            id_hex=mp.id_hex,
            filename=mp.filename,
            type=mp.media_type,
            playback_type=mp.playback_type,
            file_extension=mp.file_extension,
            owner_kind=(
                OwnerKind.SESSION
                if mp.owner_column == "sessionID"
                else OwnerKind.PARENT
            ),
            owner_id_hex=mp.owner_id_hex,
            path=Path(mp.staged_source),
        )
        for mp in clone_plan.media
    )

    speakers = tuple(
        Speaker(id_hex=sid, name=f"(proxy-{sid[:8]})", color=None, is_stub=True)
        for sid in clone_plan.speaker_links
    )

    recorded_meeting = None
    voice_memo = None
    if source_kind == SessionKind.MEETING and clone_plan.parent_id_hex:
        recorded_meeting = RecordedMeeting(
            id_hex=clone_plan.parent_id_hex,
            title=clone_plan.final_title,
            duration=(
                clone_plan.expected_duration_ms / 1000.0
                if clone_plan.expected_duration_ms is not None
                else None
            ),
            raw=dict(clone_plan.parent_row) if clone_plan.parent_row else {},
        )
    elif source_kind == SessionKind.VOICE_MEMO and clone_plan.parent_id_hex:
        voice_memo = VoiceMemo(
            id_hex=clone_plan.parent_id_hex,
            title=clone_plan.final_title,
            raw=dict(clone_plan.parent_row) if clone_plan.parent_row else {},
        )

    return Bundle(
        session=session,
        recorded_meeting=recorded_meeting,
        voice_memo=voice_memo,
        media_files=media_files,
        transcript_lines=lines,
        speakers=speakers,
        external_media_dir=external_media_dir,
    )


# ---------------------------------------------------------------------------
# identify
# ---------------------------------------------------------------------------


def cmd_identify(args: argparse.Namespace) -> int:
    db_path = _resolve_db(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        return 1

    rec_label = args.recording or ""
    label_str = f" (Recording {rec_label})" if rec_label else ""

    candidates = identify(
        db_path,
        title=args.title or None,
        date=args.date or None,
        time=args.time or None,
        limit=args.limit,
    )

    if not candidates:
        print(f"No matching sessions found{label_str}.")
        return 0

    print(f"Found {len(candidates)} candidate(s){label_str}:\n")
    for i, c in enumerate(candidates):
        rec = c.record
        dt_str = rec.date_created or "unknown date"
        reasons = f"  [{', '.join(c.reasons)}]" if c.reasons else ""
        print(f"  [{i}] {rec.title}")
        print(f"       id   : {rec.id_hex}")
        print(f"       date : {dt_str}")
        print(f"       kind : {rec.kind}")
        print(f"       score: {c.score:.3f}{reasons}")
        print()

    if rec_label in ("1", "2"):
        other = "2" if rec_label == "1" else "1"
        print(f"Use this id with --recording{rec_label} in the plan step.")
        print(f"Then run: python3 scripts/run.py identify --recording {other} ...")
    else:
        print("Use ids with: python3 scripts/run.py plan --recording1 <id1> --recording2 <id2>")
    return 0


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


def cmd_plan(args: argparse.Namespace) -> int:
    db_path = _resolve_db(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        return 1

    try:
        bundle1 = load_bundle(db_path, args.recording1)
    except Exception as exc:
        print(f"ERROR loading recording 1 ({args.recording1}): {exc}", file=sys.stderr)
        return 1

    try:
        bundle2 = load_bundle(db_path, args.recording2)
    except Exception as exc:
        print(f"ERROR loading recording 2 ({args.recording2}): {exc}", file=sys.stderr)
        return 1

    plan_root = Path(args.plan_root) if args.plan_root else DEFAULT_PLAN_ROOT
    include_merged = not args.no_merged_multitrack

    # Determine split point
    split_ms: int | None = args.split_ms
    if split_ms is None:
        print("Auto-detecting split candidates in recording 1...")
        candidates = split.detect_split_candidates(bundle1)
        if not candidates:
            print(
                "ERROR: No split candidates detected automatically in recording 1.\n"
                "Pass --split-ms <milliseconds> to specify the boundary explicitly.\n"
                "Review the transcript to find a suitable pause between meetings.",
                file=sys.stderr,
            )
            return 1
        print(f"Found {len(candidates)} split candidate(s) in recording 1:\n")
        for i, sc in enumerate(candidates):
            print(f"  [{i}] {_ms_to_human(sc.split_ms)} ({sc.split_ms} ms)  score={sc.score:.3f}  reason={sc.reason}")
            if sc.before_context:
                last = sc.before_context[-1]
                print(f"       before: \"{last.text[:80]}\"")
            if sc.after_context:
                first = sc.after_context[0]
                print(f"       after : \"{first.text[:80]}\"")
            print()
        idx = getattr(args, "candidate", 0) or 0
        if idx >= len(candidates):
            print(
                f"ERROR: --candidate {idx} out of range (0..{len(candidates)-1})",
                file=sys.stderr,
            )
            return 1
        chosen = candidates[idx]
        split_ms = chosen.split_ms
        print(f"Using candidate [{idx}]: {_ms_to_human(split_ms)} ({split_ms} ms)  {chosen.reason}\n")

    print(
        f"Step 1/2: Planning split of recording 1:\n"
        f"  title     : {bundle1.title}\n"
        f"  split at  : {_ms_to_human(split_ms)} ({split_ms} ms)\n"
        f"  → Split 1 (Meeting 1) + head fragment\n"
    )

    try:
        split_op_plan = plan_split(
            bundle1,
            db_path=db_path,
            split_ms=split_ms,
            include_merged_multitrack=include_merged,
            plan_root=plan_root,
        )
    except (ValueError, WhisperEditError) as exc:
        print(f"ERROR planning split: {exc}", file=sys.stderr)
        return 1

    print("Split plan:")
    print(split_op_plan.summary())

    split_plan_path = plan_root / SPLIT_PLAN_FILENAME
    _write_named_plan(split_op_plan, split_plan_path)
    print(f"Split plan written to: {split_plan_path}\n")

    # The head fragment is clone_plans[1] (Split 2 = head of meeting2).
    head_clone_plan = split_op_plan.clone_plans[1]
    head_fragment_id = head_clone_plan.new_session_id_hex
    source_kind = bundle1.kind

    # Build a Bundle proxy for the head fragment using the split's staged audio.
    # The staged files were created by plan_split (stage_target_audio is called
    # at plan time) so they exist on disk right now.
    from whisper_edit import engine as _eng  # noqa: E402

    head_bundle = _clone_plan_to_bundle(
        head_clone_plan,
        source_kind=source_kind,
        external_media_dir=_eng.external_media_dir_for(db_path),
    )

    print(
        f"Step 2/2: Planning combine:\n"
        f"  A: head fragment (from split)  [{head_fragment_id}]\n"
        f"  B: recording 2 — {bundle2.title}  [{bundle2.session.id_hex}]\n"
        f"  → Meeting 2 Combined\n"
    )

    try:
        combine_op_plan = plan_combine(
            head_bundle,
            bundle2,
            db_path=db_path,
            include_merged_multitrack=include_merged,
            plan_root=plan_root,
        )
    except (ValueError, WhisperEditError) as exc:
        print(f"ERROR planning combine: {exc}", file=sys.stderr)
        print(
            "Hint: recording 1 and recording 2 must be the same kind (both meetings\n"
            "or both voice memos) and must have the same audio track roles.",
            file=sys.stderr,
        )
        return 1

    print("Combine plan:")
    print(combine_op_plan.summary())

    combine_plan_path = plan_root / COMBINE_PLAN_FILENAME
    _write_named_plan(combine_op_plan, combine_plan_path)
    print(f"Combine plan written to: {combine_plan_path}\n")

    # Retain-vs-delete forecast
    split1_title = split_op_plan.clone_plans[0].final_title
    head_title = head_clone_plan.final_title
    combined_title = combine_op_plan.clone_plans[0].final_title

    print("=" * 60)
    print("RETAIN-VS-DELETE FORECAST (nothing deleted until you do it manually)")
    print("=" * 60)
    print("\nNew sessions that will be created:")
    print(f"  KEEP — {split1_title}  (Meeting 1)")
    print(f"  KEEP — {combined_title}  (Meeting 2 Combined)")
    print(f"  INTERIM — {head_title}  (head fragment — delete after verifying)")
    print("\nAfter verifying in MacWhisper, you MAY manually delete:")
    print(f"  - Recording 1 (original): {bundle1.session.id_hex}")
    print(f"  - Recording 2 (original): {bundle2.session.id_hex}")
    print(f"  - Head fragment (intermediate): {head_fragment_id}")
    print(f"\nThis tool NEVER deletes anything. Delete originals manually in MacWhisper.")
    print(f"\nCombine plan's staged audio references the split staging dir:")
    print(f"  Do NOT delete the staging dir between plan and apply.")
    print(f"  Split staging: {split_op_plan.staging_dir}")
    print(f"  Combine staging: {combine_op_plan.staging_dir}")
    return 0


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------


def cmd_apply(args: argparse.Namespace) -> int:
    plan_root = DEFAULT_PLAN_ROOT

    split_plan_path = Path(args.split_plan) if args.split_plan else (plan_root / SPLIT_PLAN_FILENAME)
    combine_plan_path = Path(args.combine_plan) if args.combine_plan else (plan_root / COMBINE_PLAN_FILENAME)

    for label, path in [("split", split_plan_path), ("combine", combine_plan_path)]:
        if not path.exists():
            print(f"ERROR: {label} plan not found at {path}", file=sys.stderr)
            print("Run 'python3 scripts/run.py plan ...' first.", file=sys.stderr)
            return 1

    try:
        split_op_plan = OperationPlan.read(split_plan_path)
        combine_op_plan = OperationPlan.read(combine_plan_path)
    except Exception as exc:
        print(f"ERROR reading plans: {exc}", file=sys.stderr)
        return 1

    process_checker = _NotRunningChecker() if args.no_process_check else None
    backup_root = Path(args.backup_root) if args.backup_root else DEFAULT_BACKUP_ROOT

    if args.no_process_check:
        print("WARNING: MacWhisper process check bypassed (backup-copy mode)\n")

    # Step 1: Apply split
    print("Step 1/2: Applying split plan...")
    print(f"  sources  : {', '.join(split_op_plan.source_session_ids)}")
    print(f"  targets  : {len(split_op_plan.clone_plans)} new session(s)\n")

    try:
        split_result = apply(
            split_op_plan,
            process_checker=process_checker,
            backup_root=backup_root,
        )
    except MacWhisperRunningError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "\nQuit MacWhisper fully (not just close the window) and re-run.\n"
            "For backup-copy validation, pass --no-process-check.",
            file=sys.stderr,
        )
        return 1
    except WhisperEditError as exc:
        print(f"ERROR (split): {exc}", file=sys.stderr)
        return 1

    print(split_result.summary())
    if not split_result.ok:
        print("ERROR: split verification failed — aborting before combine.", file=sys.stderr)
        print("The split sessions may be partially written. Check the backup to restore if needed.")
        return 2

    # Step 2: Apply combine
    print("\nStep 2/2: Applying combine plan...")
    print(f"  sources  : {', '.join(combine_op_plan.source_session_ids)}")
    print(f"  targets  : {len(combine_op_plan.clone_plans)} new session(s)\n")

    try:
        combine_result = apply(
            combine_op_plan,
            process_checker=process_checker,
            backup_root=backup_root,
        )
    except MacWhisperRunningError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except WhisperEditError as exc:
        print(f"ERROR (combine): {exc}", file=sys.stderr)
        return 1

    print(combine_result.summary())
    all_ok = split_result.ok and combine_result.ok

    # Extract created session IDs
    split1_id = split_result.results[0].new_session_id_hex if split_result.results else "unknown"
    head_id = split_result.results[1].new_session_id_hex if len(split_result.results) > 1 else "unknown"
    combined_id = combine_result.results[0].new_session_id_hex if combine_result.results else "unknown"

    print("\n" + "=" * 60)
    print("RETAIN-VS-DELETE SUMMARY")
    print("=" * 60)
    print("\nNew sessions created — VERIFY in MacWhisper before deleting anything:")
    print(f"  KEEP — Meeting 1      : session {split1_id}")
    print(f"  KEEP — Meeting 2      : session {combined_id}")
    print(f"  INTERIM (head frag)   : session {head_id}")
    print("    (Delete head fragment manually in MacWhisper once you've verified Meeting 2)")
    print("\nOriginals (still untouched — delete manually in MacWhisper when ready):")
    for sid in split_op_plan.source_session_ids:
        print(f"  - Recording 1 source  : {sid}")
    for sid in combine_op_plan.source_session_ids:
        if sid not in list(split_op_plan.source_session_ids) and sid != head_id:
            print(f"  - Recording 2 source  : {sid}")
    print("\nEngine staging dirs (safe to delete right now):")
    print(f"  - {split_result.staging_dir}")
    print(f"  - {combine_result.staging_dir}")
    print("\nThis tool NEVER deletes anything. All cleanup is manual inside MacWhisper.")

    if not all_ok:
        print("\nWARNING: one or more verifications failed. Check output above.", file=sys.stderr)
        return 2
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description=(
            "Split-then-combine two MacWhisper recordings in-process "
            "(identify → plan → apply)."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # identify
    p_id = sub.add_parser("identify", help="Find and rank sessions matching hints.")
    p_id.add_argument("--recording", metavar="1|2", help="Which recording you're identifying (display only).")
    p_id.add_argument("--db", metavar="PATH", help="Path to main.sqlite (default: live DB).")
    p_id.add_argument("--title", metavar="STR", help="Title fragment (fuzzy).")
    p_id.add_argument("--date", metavar="YYYY-MM-DD", help="Boost sessions on this date.")
    p_id.add_argument("--time", metavar="HH:MM", help="Boost sessions near this time (local).")
    p_id.add_argument("--limit", type=int, default=10, metavar="N", help="Max candidates (default 10).")

    # plan
    p_plan = sub.add_parser("plan", help="Build both dry-run plans (split + combine) in-process.")
    p_plan.add_argument("--recording1", required=True, metavar="HEX", help="Recording 1 (meeting1 + head of meeting2). 32-char hex.")
    p_plan.add_argument("--recording2", required=True, metavar="HEX", help="Recording 2 (tail of meeting2). 32-char hex.")
    p_plan.add_argument("--db", metavar="PATH", help="Path to main.sqlite (default: live DB).")
    p_plan.add_argument("--split-ms", type=int, metavar="MS", help="Split boundary in ms from recording 1 start.")
    p_plan.add_argument("--candidate", type=int, default=0, metavar="N", help="Auto-detected split candidate index (default 0).")
    p_plan.add_argument("--no-merged-multitrack", action="store_true", help="Skip mergedMultitrack audio reconstruction.")
    p_plan.add_argument("--plan-root", metavar="DIR", help=f"Directory for plan JSON files + staging (default {DEFAULT_PLAN_ROOT}).")

    # apply
    p_apply = sub.add_parser("apply", help="Execute both plans in sequence.")
    p_apply.add_argument("--split-plan", metavar="PATH", help=f"Path to split plan (default: <plan-root>/{SPLIT_PLAN_FILENAME}).")
    p_apply.add_argument("--combine-plan", metavar="PATH", help=f"Path to combine plan (default: <plan-root>/{COMBINE_PLAN_FILENAME}).")
    p_apply.add_argument("--no-process-check", action="store_true", help="Bypass MacWhisper-running guard (backup-copy testing only).")
    p_apply.add_argument("--backup-root", metavar="DIR", help="Where to store the pre-write backup.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd == "identify":
        return cmd_identify(args)
    if args.cmd == "plan":
        return cmd_plan(args)
    if args.cmd == "apply":
        return cmd_apply(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
