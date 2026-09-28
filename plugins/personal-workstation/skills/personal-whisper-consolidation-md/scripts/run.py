#!/usr/bin/env python3
"""Entry point for personal-whisper-consolidation-md.

Scans whisper markdown notes for multi-meeting recordings and applies
agent-confirmed partition decisions to split them into separate files.

Run from this directory as:

    python3 scripts/run.py scan  --workspace ~/Projects/personal/notes
    python3 scripts/run.py apply --workspace ~/Projects/personal/notes

Or with options:

    python3 scripts/run.py scan --workspace ~/Projects/personal/notes \\
        --min-gap-min 5 \\
        --path 2026/04/2026-04-27-some-meeting.md

Subcommands
-----------
scan   Walk workspace notes; run T1-T4 detection; write candidates.json.
apply  Read decisions.json; write split files; remove originals.

State directory: /tmp/whisper_consolidate/
  candidates.json   — output of scan (read by agent for review step)
  decisions.json    — written by agent after review (input to apply)
  report.json       — output of apply
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

from whisper import markdown_split  # noqa: E402

TMP_ROOT = Path("/tmp/whisper_consolidate")
CANDIDATES_FILE = TMP_ROOT / "candidates.json"
DECISIONS_FILE = TMP_ROOT / "decisions.json"
REPORT_FILE = TMP_ROOT / "report.json"


def _ensure_tmp() -> None:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------


def cmd_scan(
    workspace: Path,
    *,
    min_gap_min: float,
    specific_path: Path | None,
    t2_window_lines: int,
    t2_jaccard_max: float,
    t3_max_gap_min: float,
    t4_max_density: float,
    t4_min_span_min: float,
) -> dict:
    _ensure_tmp()
    results = markdown_split.scan_workspace(
        workspace,
        min_gap_s=int(min_gap_min * 60),
        t2_window_lines=t2_window_lines,
        t2_jaccard_max=t2_jaccard_max,
        t3_max_gap_s=int(t3_max_gap_min * 60),
        t4_max_density=t4_max_density,
        t4_min_span_s=int(t4_min_span_min * 60),
        specific_path=specific_path,
    )

    output = {
        "workspace": str(workspace),
        "flagged_count": len(results),
        "notes": [r.to_dict(workspace) for r in results],
        "settings": {
            "min_gap_min": min_gap_min,
            "t2_window_lines": t2_window_lines,
            "t2_jaccard_max": t2_jaccard_max,
            "t3_max_gap_min": t3_max_gap_min,
            "t4_max_density_lines_per_min": t4_max_density,
            "t4_min_span_min": t4_min_span_min,
        },
    }
    _write_json(CANDIDATES_FILE, output)
    return output


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------


def cmd_apply(workspace: Path) -> dict:
    _ensure_tmp()
    decisions_doc = _read_json(DECISIONS_FILE, default={"decisions": []})
    decisions = decisions_doc.get("decisions") or []

    if not decisions:
        msg = (
            f"No decisions found in {DECISIONS_FILE}.\n"
            "Run `scan` first, review candidates.json, then write decisions.json."
        )
        sys.stderr.write(msg + "\n")
        return {"error": msg}

    report = {
        "applied": [],
        "skipped": [],
        "errors": [],
    }

    for decision in decisions:
        note_path = decision.get("note_path", "")
        if not note_path:
            report["errors"].append({"note_path": "", "error": "missing note_path"})
            continue

        action = decision.get("action", "split")
        if action == "skip":
            report["skipped"].append(note_path)
            continue

        result = markdown_split.apply_partition(workspace, decision)

        entry: dict = {
            "note_path": note_path,
            "written": result.written,
            "discarded": result.discarded,
        }
        if result.errors:
            entry["errors"] = result.errors
            report["errors"].append(entry)
        else:
            report["applied"].append(entry)

    _write_json(REPORT_FILE, report)
    return report


# ---------------------------------------------------------------------------
# report (human-readable summary of last apply)
# ---------------------------------------------------------------------------


def cmd_report() -> str:
    report = _read_json(REPORT_FILE, default={})
    lines: list[str] = []

    applied = report.get("applied") or []
    skipped = report.get("skipped") or []
    errors = report.get("errors") or []

    lines.append(f"Applied: {len(applied)}")
    for entry in applied:
        parts_str = " + ".join(entry.get("written") or [])
        discarded = entry.get("discarded") or []
        discard_str = f", {len(discarded)} discarded part(s)" if discarded else ""
        lines.append(f"  {entry['note_path']} -> {parts_str}{discard_str}")

    lines.append(f"Skipped: {len(skipped)}")
    for s in skipped:
        lines.append(f"  {s}")

    lines.append(f"Errors: {len(errors)}")
    for e in errors:
        errs = e.get("errors") or [e.get("error", "unknown")]
        lines.append(f"  {e.get('note_path', '?')}: {'; '.join(errs)}")

    text = "\n".join(lines)
    sys.stdout.write(text + "\n")
    return text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="whisper-consolidation",
        description="Split whisper markdown notes that contain multiple meetings.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # scan
    scan_p = sub.add_parser("scan", help="Detect multi-meeting notes.")
    scan_p.add_argument("--workspace", required=True, help="Notes workspace root.")
    scan_p.add_argument(
        "--min-gap-min", type=float, default=10.0,
        help="T1 silence gap threshold in minutes (default 10).",
    )
    scan_p.add_argument(
        "--path", default=None,
        help="Scan a single note (workspace-relative or absolute path).",
    )
    scan_p.add_argument(
        "--t2-window-lines", type=int, default=markdown_split.DEFAULT_T2_WINDOW_LINES,
        help="T2 sliding window size in lines (default 30).",
    )
    scan_p.add_argument(
        "--t2-jaccard-max", type=float, default=markdown_split.DEFAULT_T2_JACCARD_MAX,
        help="T2 Jaccard threshold for membership turnover (default 0.2).",
    )
    scan_p.add_argument(
        "--t3-max-gap-min", type=float, default=float(markdown_split.DEFAULT_T3_MAX_GAP_S) / 60,
        help="T3 max gap between farewell and greeting in minutes (default 3).",
    )
    scan_p.add_argument(
        "--t4-max-density", type=float, default=markdown_split.DEFAULT_T4_MAX_DENSITY,
        help="T4 max lines/min that counts as sparse (default 2).",
    )
    scan_p.add_argument(
        "--t4-min-span-min", type=float, default=float(markdown_split.DEFAULT_T4_MIN_SPAN_S) / 60,
        help="T4 minimum sustained sparse span in minutes (default 15).",
    )

    # apply
    apply_p = sub.add_parser("apply", help="Write split files from decisions.json.")
    apply_p.add_argument("--workspace", required=True, help="Notes workspace root.")

    # report
    sub.add_parser("report", help="Print human-readable summary of last apply.")

    args = parser.parse_args(argv)
    workspace_str = getattr(args, "workspace", None)
    if workspace_str:
        workspace = Path(workspace_str).expanduser().resolve()

    if args.cmd == "scan":
        specific_path: Path | None = None
        if args.path:
            p = Path(args.path)
            if not p.is_absolute():
                p = workspace / p
            specific_path = p.resolve()

        out = cmd_scan(
            workspace,
            min_gap_min=args.min_gap_min,
            specific_path=specific_path,
            t2_window_lines=args.t2_window_lines,
            t2_jaccard_max=args.t2_jaccard_max,
            t3_max_gap_min=args.t3_max_gap_min,
            t4_max_density=args.t4_max_density,
            t4_min_span_min=args.t4_min_span_min,
        )
        print(json.dumps({
            "flagged": out["flagged_count"],
            "candidates_file": str(CANDIDATES_FILE),
        }))

    elif args.cmd == "apply":
        out = cmd_apply(workspace)
        if "error" in out:
            return 1
        print(json.dumps({
            "applied": len(out.get("applied") or []),
            "skipped": len(out.get("skipped") or []),
            "errors": len(out.get("errors") or []),
            "report_file": str(REPORT_FILE),
        }))

    elif args.cmd == "report":
        cmd_report()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
