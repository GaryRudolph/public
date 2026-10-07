#!/usr/bin/env python3
"""Tally real token usage for personal-plan-orchestrate on Claude Code.

Reads the transcripts Claude Code writes under a session directory
(~/.claude/projects/<project-slug>/<session-id>/), groups usage by plan row
(wave-N, wave-N-fix, wave-N-fix2, ..., the matching review-wave rows, and
with --parent-window an orchestrator row) and resolved model, and prices it at the
list rates in plan-execution.md's Model price table, so the table stays the
single source of rates.

Usage follows plan-execution.md "Token accounting - source precedence": one
call per message.id, from its line with stop_reason, which carries the final
counts. A call with no such line (almost every Opus call in a subagent file)
logs a streaming placeholder (1-24) as output_tokens: its input-side counts
are kept, its output is estimated at 1,000 tokens, and its token line is
labeled (output est.) and ends with session <id>.

With --check-routing, exit 2 when an agent ran on another model than its
tier's (an availableModels substitution, or a wrong alias).
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_SKILL = Path(__file__).resolve().parents[1]
ORG = _SKILL.name.removesuffix("-plan-orchestrate")
DEFAULT_TABLE = _SKILL.parent / f"{ORG}-standards/standards/plan-execution.md"
ROW_RE = re.compile(r"^\|\s*`([^`]+)`(?:\s*/\s*`[^`]+`)?(?:\s*\(([^)]*)\))?\s*\|[^|]*\|\s*\$([\d.]+)\s*\|\s*\$([\d.]+)\s*\|\s*\$([\d.]+)\s*\|")
# A fix-up of wave N is N-fix, then N-fix2, N-fix3 (plan-execution.md "Fix-up waves"); never N-fix1 or N-fix02.
LABEL_RE = re.compile(r"^(?:(Review|Draft|Judge)\b[^W]*)?Wave (\d+(?:-fix(?:[2-9]|[1-9]\d+)?)?) of \d+ \[(\w+)\] (.+?)(?: \(retry\))?$")
OUTPUT_EST = 1_000  # tokens per call without a stop_reason line (plan-execution.md)


def load_rates(table_path):
    rates = {}
    in_table = False
    for line in Path(table_path).read_text().splitlines():
        if line.startswith("### Model price table"):
            in_table = True
        elif in_table and line.startswith("### "):
            break
        elif in_table:
            m = ROW_RE.match(line)
            if m and (m.group(2) in (None, "standard")):
                rates[m.group(1)] = tuple(float(m.group(i)) for i in (3, 4, 5))
    if not rates:
        sys.exit(f"no Model price table rows found in {table_path}")
    return rates


def rate_for(model, rates):
    keys = [k for k in rates if model.startswith(k)]
    return rates[max(keys, key=len)] if keys else None


def load_aliases(table_path):
    """Tier -> Claude Code alias, from the model picker's Claude Code row."""
    row = next(l for l in Path(table_path).read_text().splitlines() if l.startswith("| Claude Code |"))
    cells = [c.strip() for c in row.strip("|").split("|")][1:5]
    out = {t: re.search(r"`/model (\w+)`", c).group(1) for t, c in zip(("xdeep", "deep", "exec", "fast"), cells)}
    alt = re.search(r"alt: `/model (\w+)`", cells[0])
    if alt:
        out["fable"] = alt.group(1)
    return out


def row_for(label):
    m = LABEL_RE.match(label or "")
    if not m:
        return label or "unlabelled", None
    kind, wave, tier, group = m.groups()
    prefix = "review-wave" if kind == "Review" else "wave"
    # Workers run on their tier's model; reviewers, drafts and judges on Opus.
    expect = tier if kind is None else "deep"
    return f"{prefix}-{wave} {re.sub(r'[^A-Za-z0-9.]+', '-', group).strip('-')}", expect


def calls_of(records):
    """Yield (model, usage, estimated) once per assistant message.

    A message is written once per content block, and every copy carries the
    same input and cache counts. The copy with stop_reason carries the final
    output; without one, output is a streaming placeholder, so estimate it.
    """
    final, last = {}, {}
    for n, rec in records:
        msg = rec.get("message")
        if rec.get("type") != "assistant" or not isinstance(msg, dict) or not msg.get("usage"):
            continue
        key = msg.get("id") or n
        last[key] = (msg.get("model", "unknown"), msg["usage"])
        if msg.get("stop_reason"):
            final[key] = last[key]
    for key, (model, usage) in last.items():
        if key in final:
            yield (*final[key], False)
        else:
            yield model, {**usage, "output_tokens": OUTPUT_EST}, True


def records_of(path):
    for n, line in enumerate(path.read_text().splitlines()):
        try:
            yield n, json.loads(line)
        except ValueError:
            continue


def window(path, start, end):
    """Main-transcript records after the launch result of run `start` (or the session start) through
    the launch result of run `end` (or the end): the parent's work between two launches."""
    inside = start == "start"
    for n, rec in records_of(path):
        if rec.get("isSidechain"):
            continue
        rid = (rec.get("toolUseResult") or {}).get("runId") if isinstance(rec.get("toolUseResult"), dict) else None
        if inside:
            yield n, rec
            if rid and rid == end:
                return
        elif rid and rid == start:
            inside = True


def add(acc, usage, estimated):
    acc["estimated_calls"] += estimated
    split = usage.get("cache_creation") or {}
    w5 = split.get("ephemeral_5m_input_tokens")
    w1 = split.get("ephemeral_1h_input_tokens", 0)
    if w5 is None:
        w5 = usage.get("cache_creation_input_tokens", 0)
    acc["input"] += usage.get("input_tokens", 0)
    acc["cache_read"] += usage.get("cache_read_input_tokens", 0)
    acc["write_5m"] += w5
    acc["write_1h"] += w1
    acc["output"] += usage.get("output_tokens", 0)


def sig(n):
    """Two significant figures with k or M, as plan-execution.md's token line format asks."""
    for div, unit in ((1_000_000, "M"), (1_000, "k")):
        if n >= div:
            v = float(f"{n / div:.2g}")
            return f"{v:g}{unit}"
    return f"{float(f'{n:.2g}'):g}" if n else "0"


def cost(acc, rate):
    if rate is None:
        return None
    in_rate, cached_rate, out_rate = rate
    return (acc["input"] * in_rate + acc["cache_read"] * cached_rate + acc["write_5m"] * in_rate * 1.25
            + acc["write_1h"] * in_rate * 2.0 + acc["output"] * out_rate) / 1_000_000


def transcripts(session_dir, runs, parent):
    if parent:
        start, _, end = parent["window"].partition(":")
        yield parent["row"], None, window(session_dir.with_suffix(".jsonl"), start, end or "end")
    roots = [session_dir / "subagents" / "workflows" / r for r in runs] if runs else [session_dir / "subagents"]
    for root in roots:
        for path in sorted(root.rglob("agent-*.jsonl")):
            meta = path.with_name(path.name.replace(".jsonl", ".meta.json"))
            label = json.loads(meta.read_text()).get("description") if meta.exists() else None
            yield (*row_for(label), records_of(path))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--session-dir", required=True, type=Path, help="~/.claude/projects/<slug>/<session-id>")
    ap.add_argument("--run", action="append", default=[], help="workflow run id; repeat; default: every subagent")
    ap.add_argument("--parent-window", metavar="START:END",
                    help="also tally the parent between two launches: run ids, or start / end")
    ap.add_argument("--parent-row", default="orchestrator", metavar="ROW",
                    help='row and group for the parent line, e.g. "orchestrator-wave-2 m1-s4"')
    ap.add_argument("--table", type=Path, default=DEFAULT_TABLE, help="plan-execution.md with the Model price table")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check-routing", action="store_true", help="exit 2 if an agent ran on another model than its tier's")
    a = ap.parse_args()

    rates = load_rates(a.table)
    aliases = load_aliases(a.table)
    rows = defaultdict(lambda: defaultdict(int))
    misrouted = []
    parent = a.parent_window and {"window": a.parent_window, "row": a.parent_row}
    for row, expect, recs in transcripts(a.session_dir, a.run, parent):
        for model, usage, estimated in calls_of(recs):
            add(rows[(row, model)], usage, estimated)
            if expect and aliases.get(expect, "?") not in model and (row, model) not in misrouted:
                misrouted.append((row, model))
    session = a.session_dir.name

    out, total = [], 0.0
    for (row, model), acc in sorted(rows.items(), key=lambda kv: (kv[0][0] != "orchestrator", kv[0])):
        c = cost(acc, rate_for(model, rates))
        total += c or 0
        out.append({"row": row, "model": model, **acc, "cost": c, "session": session})
    if a.json:
        print(json.dumps({"rows": out, "total_cost": total, "misrouted": misrouted}, indent=1))
    else:
        for r in out:
            w = f"~{sig(r['write_5m'])}" + (f" 5m + ~{sig(r['write_1h'])} 1h" if r["write_1h"] else "")
            c = "n/a" if r["cost"] is None else f"~${r['cost']:.2f}"
            est = f" (output est.) session {r['session']}" if r["estimated_calls"] else ""
            print(f"tokens {r['row']} ({r['model']}): input ~{sig(r['input'])} / cache read ~{sig(r['cache_read'])} / cache write {w} / output ~{sig(r['output'])} | {c} API-equiv{est}")
        print(f"total: ~${total:.2f} API-equiv")
        for row, model in misrouted:
            print(f"MISROUTED: {row} ran on {model}", file=sys.stderr)
    if a.check_routing and misrouted:
        sys.exit(2)


if __name__ == "__main__":
    main()
