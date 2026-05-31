#!/usr/bin/env python3
"""Combine entry point for personal-whisper-combine-db.

Thin wrapper around the shared `whisper_edit` engine. Exposes three subcommands:

    python3 scripts/run.py identify  [--label a|b] [--title STR] [--date YYYY-MM-DD] [--db PATH]
    python3 scripts/run.py plan      --session-a HEX --session-b HEX [--title STR] [--db PATH]
    python3 scripts/run.py apply     [--plan PATH] [--no-process-check]

`plan` and `apply` are separated so the agent can show the dry-run summary and
ask for confirmation before any database or audio write occurs.

Safety: never run `apply` against the live MacWhisper DB while MacWhisper is
running. Use --db + --no-process-check for backup-copy validation only.
"""

from __future__ import annotations

import argparse
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
)
from whisper_edit.backup import DEFAULT_BACKUP_ROOT  # noqa: E402
from whisper_edit.engine import DEFAULT_PLAN_ROOT, PLAN_FILENAME, OperationPlan  # noqa: E402

LIVE_DB = db.DEFAULT_DB_PATH


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


# ---------------------------------------------------------------------------
# identify
# ---------------------------------------------------------------------------


def cmd_identify(args: argparse.Namespace) -> int:
    db_path = _resolve_db(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        return 1

    label = args.label or ""
    label_str = f" (session {label.upper()})" if label else ""

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

    if label.lower() in ("a", "b"):
        other = "b" if label.lower() == "a" else "a"
        print(f"Use the id value with --session-{label.lower()} in the plan step.")
        print(f"Then run: python3 scripts/run.py identify --label {other} ...")
    else:
        print("Use the id values with: python3 scripts/run.py plan --session-a <idA> --session-b <idB>")
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
        bundle_a = load_bundle(db_path, args.session_a)
    except Exception as exc:
        print(f"ERROR loading session A ({args.session_a}): {exc}", file=sys.stderr)
        return 1

    try:
        bundle_b = load_bundle(db_path, args.session_b)
    except Exception as exc:
        print(f"ERROR loading session B ({args.session_b}): {exc}", file=sys.stderr)
        return 1

    plan_root = Path(args.plan_root) if args.plan_root else DEFAULT_PLAN_ROOT
    include_merged = not args.no_merged_multitrack

    dur_a = _ms_to_human(bundle_a.duration_ms())
    dur_b = _ms_to_human(bundle_b.duration_ms())
    print(
        f"Planning combine:\n"
        f"  A: {bundle_a.title}  ({dur_a})  [{bundle_a.session.id_hex}]\n"
        f"  B: {bundle_b.title}  ({dur_b})  [{bundle_b.session.id_hex}]\n"
        f"  merged trk: {include_merged}\n"
    )

    if args.title:
        print(f"  custom title: {args.title}\n")

    try:
        op_plan = plan_combine(
            bundle_a,
            bundle_b,
            db_path=db_path,
            include_merged_multitrack=include_merged,
            plan_root=plan_root,
        )
    except (ValueError, WhisperEditError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(op_plan.summary())
    print(f"Plan written to: {plan_root / PLAN_FILENAME}")
    return 0


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------


def cmd_apply(args: argparse.Namespace) -> int:
    plan_root = DEFAULT_PLAN_ROOT
    plan_path = Path(args.plan) if args.plan else (plan_root / PLAN_FILENAME)
    if not plan_path.exists():
        print(f"ERROR: plan file not found at {plan_path}", file=sys.stderr)
        return 1

    try:
        op_plan = OperationPlan.read(plan_path)
    except Exception as exc:
        print(f"ERROR reading plan: {exc}", file=sys.stderr)
        return 1

    process_checker = _NotRunningChecker() if args.no_process_check else None
    backup_root = Path(args.backup_root) if args.backup_root else DEFAULT_BACKUP_ROOT

    print(f"Applying plan: {op_plan.op}")
    print(f"  sources  : {', '.join(op_plan.source_session_ids)}")
    print(f"  targets  : {len(op_plan.clone_plans)} new session(s)")
    print(f"  db       : {op_plan.db_path}")
    if args.no_process_check:
        print("  WARNING  : MacWhisper process check bypassed (backup-copy mode)")
    print()

    try:
        result = apply(
            op_plan,
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
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(result.summary())
    if not result.ok:
        print("WARNING: verification failed — check the output above.", file=sys.stderr)
        return 2
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Combine two MacWhisper sessions into one (identify → plan → apply).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # identify
    p_id = sub.add_parser("identify", help="Find and rank sessions matching hints.")
    p_id.add_argument("--label", metavar="a|b", help="Which session you're identifying (display only).")
    p_id.add_argument("--db", metavar="PATH", help="Path to main.sqlite (default: live DB).")
    p_id.add_argument("--title", metavar="STR", help="Title fragment (fuzzy).")
    p_id.add_argument("--date", metavar="YYYY-MM-DD", help="Boost sessions on this date.")
    p_id.add_argument("--time", metavar="HH:MM", help="Boost sessions near this time (local).")
    p_id.add_argument("--limit", type=int, default=10, metavar="N", help="Max candidates (default 10).")

    # plan
    p_plan = sub.add_parser("plan", help="Build a dry-run combine plan (no writes).")
    p_plan.add_argument("--session-a", required=True, metavar="HEX", help="Session A (plays first). 32-char hex.")
    p_plan.add_argument("--session-b", required=True, metavar="HEX", help="Session B (plays second). 32-char hex.")
    p_plan.add_argument("--db", metavar="PATH", help="Path to main.sqlite (default: live DB).")
    p_plan.add_argument("--title", metavar="STR", help="Custom title for the combined session.")
    p_plan.add_argument("--no-merged-multitrack", action="store_true", help="Skip mergedMultitrack audio reconstruction.")
    p_plan.add_argument("--plan-root", metavar="DIR", help=f"Directory for plan.json + staging (default {DEFAULT_PLAN_ROOT}).")

    # apply
    p_apply = sub.add_parser("apply", help="Execute the latest plan.json.")
    p_apply.add_argument("--plan", metavar="PATH", help="Path to plan.json (default: <plan-root>/plan.json).")
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
