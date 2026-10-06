#!/usr/bin/env python3
"""Compute the next dispatch unit of a tagged plan and the STOP gates before it.

Harness-neutral: every orchestrate parent runs it before each dispatch, and on
Claude Code the plan-segment workflow refuses to spawn unless the approvals
cover the gates it reports (the PreToolUse hook re-runs it from disk).

Reads only the plan file: wave markers, tagged headings and their (done)
markers, the Kickoff Status and mode lines, the Cost table, the Review log
and the Token log.

Every gate derives from the plan in every mode. The mode only splits them:
in gated mode every gate stops; in unattended mode gates 2, 3, 4, a planned
wave's gate 7, and gate 1 on an automatic fix-up within the mode line's cap
become checkpoints (logged, not asked), and the rest stop. The cost guard
(gate-guard) and an unconfirmed mode (gate-mode) stop in every mode.

Fix-ups come from the Review log. The k-th CONCERNS line in a row for a group
of wave N makes the next unit its fix-up, labeled N-fix for k = 1 and N-fix<k>
after (plan-execution.md "Fix-up waves"). A check_wave.py failure is logged as
a CONCERNS line whose note starts "check_wave.py:", so it starts or extends
the same streak, and it is gate 1. A streak of two or more is gate 1 too.
A PASS ends the streak, and so does a WAIVED line, which carries Gary's
answer to that gate 1 verbatim (the hook checks the words).

Usage: plan_state.py <plan.md>     prints one JSON object
"""

import json
import re
import sys
from pathlib import Path

ORDER = {"fast": 0, "exec": 1, "deep": 2, "xdeep": 3}
# A fix-up of wave N is N-fix, then N-fix2, N-fix3 (plan-execution.md "Fix-up waves"); never N-fix1 or N-fix02.
FIX = r"-fix(?:[2-9]|[1-9]\d+)?"
WAVE_RE = re.compile(r"^--- WAVE (\d+)(" + FIX + r")? \[(xdeep|deep|exec|fast)\] ---\s*$")
HEADING_RE = re.compile(r"^(#+)\s+(.*?)\s*$")
TAG_RE = re.compile(r"\[(xdeep|deep|exec|fast)\]")
DONE_RE = re.compile(r"\(done\)\s*$")
MILESTONE_RE = re.compile(r"^(?:m(\d+)\b|milestone\s+(\d+)\b)", re.I)
BLOCKED_RE = re.compile(r"BLOCKED at gate ([\w-]+)")
# A fix-up's review is logged as wave-N-fix, wave-N-fix2, ...; it counts toward wave N's group.
# WAIVED is never a review: it records Gary's answer to a gate 1, verbatim, and ends the streak.
REVIEW_RE = re.compile(
    r"^\s*(?:[-*]\s+)?`?review wave-(\d+)(?:" + FIX + r")? \((.+?)\) (\S+)\.\.(\S+): (PASS|CONCERNS|WAIVED) - (.*) - (\d{4}-\d\d-\d\d)`?\s*$")
REVIEW_START_RE = re.compile(r"^\s*(?:[-*]\s+)?`?review wave-")
# Kickoff mode line. Gary's words come last, verbatim, so they may hold any character:
#   mode: unattended | proposed unattended (CLAUDE_CODE_REMOTE=true) | guard 3x min $50 | fixups 2 | confirmed 2026-10-06 session <id>: <words>
MODE_RE = re.compile(r"^mode:\s*(gated|unattended|pending)\b(.*)$")
CONFIRMED_RE = re.compile(r"\|\s*confirmed (\d{4}-\d\d-\d\d) session (\S+?): (.*)$")
PROPOSED_RE = re.compile(r"\|\s*proposed (gated|unattended)(?: \(([^)]*)\))?")
GUARD_RE = re.compile(r"\|\s*guard (\d+(?:\.\d+)?)x(?: min \$(\d+(?:\.\d+)?))?(?=\s|\||$)")
FIXUPS_RE = re.compile(r"\|\s*fixups (\d+)\b")
COST_ROW_RE = re.compile(r"^\|\s*(\d+(?:" + FIX + r")?) \[(?:xdeep|deep|exec|fast)\][^|]*\|[^|]*\|\s*(~?\$([\d.]+)|\u2014|-)\s*\|")
COST_TOTAL_RE = re.compile(r"^\|\s*\*\*Total\*\*\s*\|[^|]*\|\s*~?\$([\d.]+)\s*\|")
TOKEN_RE = re.compile(r"^\s*(?:[-*]\s+)?`?tokens \S+ .*\|\s*(?:~\$([\d.]+)|n/a) API-equiv")
DEFAULT_GUARD = 3.0  # stop when projected spend passes this multiple of the expected total...
DEFAULT_GUARD_MIN = 50.0  # ...and this floor in API-equiv dollars, whichever is higher
DEFAULT_FIXUPS = 2  # automatic fix-ups per group, unattended
CHECK_NOTE = "check_wave.py:"  # a Review log note that records a failed check, not a review
UNATTENDED_CHECKPOINTS = {"gate-2", "gate-3", "gate-4"}


def milestone_of(text):
    m = MILESTONE_RE.match(text)
    return f"m{m.group(1) or m.group(2)}" if m else None


def fix_label(wave, k):
    return f"{wave}-fix" if k == 1 else f"{wave}-fix{k}"


def mode_of(line):
    m = MODE_RE.match(line)
    if not m:
        return None
    rest, c = m.group(2), CONFIRMED_RE.search(m.group(2))
    head = rest[:c.start()] if c else rest  # the words after "confirmed" are Gary's, never fields
    p, g, f = PROPOSED_RE.search(head), GUARD_RE.search(head), FIXUPS_RE.search(head)
    return {"value": m.group(1) if c else "pending", "proposed": p and p.group(1), "signal": p and p.group(2),
            "guard": float(g.group(1)) if g else DEFAULT_GUARD,
            "guard_min": float(g.group(2)) if g and g.group(2) else DEFAULT_GUARD_MIN, "fixups": int(f.group(1)) if f else DEFAULT_FIXUPS,
            "date": c and c.group(1), "session": c and c.group(2), "words": c and c.group(3).strip()}


def parse(text):
    errors, steps, reviews = [], [], []
    status, mode, wave, fence, kickoff_fence = None, None, None, False, False
    enclosing = {}  # heading level -> milestone of the latest heading at that level
    markers = []
    section = None  # the current "## " section, lowercased
    cost = {"rows": {}, "total": None, "actual": 0.0}
    in_cost = False
    for no, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence, kickoff_fence = not fence, False
            continue
        if fence:
            kickoff_fence = kickoff_fence or "--- KICKOFF:" in line
            if kickoff_fence and status is None and line.strip().startswith("Status:"):
                status = line.strip()
            if kickoff_fence and mode is None:
                mode = mode_of(line.strip())
            continue
        if line.startswith("**Cost ("):
            in_cost = True
            continue
        if in_cost:
            if line.startswith("|"):
                r, t = COST_ROW_RE.match(line), COST_TOTAL_RE.match(line)
                if r:
                    cost["rows"][r.group(1)] = float(r.group(3)) if r.group(3) else None
                elif t:
                    cost["total"] = float(t.group(1))
                continue
            if line.strip() and not line.startswith("Expected values"):
                in_cost = False
        if line.startswith("## "):
            section = line.strip().lower()
        if section == "## review log":
            m = REVIEW_RE.match(line)
            if m:
                reviews.append({"wave": int(m.group(1)), "group": m.group(2), "from": m.group(3), "to": m.group(4),
                                "verdict": m.group(5), "note": m.group(6)})
            elif REVIEW_START_RE.match(line):
                errors.append(f"line {no}: a Review log line the grammar doesn't parse: {line.strip()[:80]!r}")
            continue
        if section == "## token log":
            m = TOKEN_RE.match(line)
            if m and m.group(1):
                cost["actual"] += float(m.group(1))
            continue
        m = WAVE_RE.match(line)
        if m:
            wave = {"n": int(m.group(1)), "tier": m.group(3), "label": m.group(1) + (m.group(2) or ""),
                    "fix": bool(m.group(2))}
            markers.append(wave)
            continue
        if line.startswith("--- WAVE"):
            errors.append(f"line {no}: {line.strip()!r} is not a wave marker (N, N-fix, or N-fix<k> for k of 2 or more)")
            continue
        h = HEADING_RE.match(line)
        if not h:
            continue
        level, body = len(h.group(1)), h.group(2)
        tag = TAG_RE.search(body)
        if not tag:
            enclosing = {k: v for k, v in enclosing.items() if k < level}
            enclosing[level] = milestone_of(body)
            continue
        prefix = body[:tag.start()].strip().rstrip("-:.").strip()
        title = DONE_RE.sub("", body[tag.end():]).strip()
        sid = prefix or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        ms = milestone_of(prefix) or next((v for k, v in sorted(enclosing.items(), reverse=True) if k < level and v), None)
        if wave is None:
            errors.append(f"line {no}: tagged step {sid} comes before any wave marker")
            continue
        steps.append({"id": sid, "tag": tag.group(1), "done": bool(DONE_RE.search(body)), "wave": wave["n"],
                      "label": wave["label"], "tier": wave["tier"], "milestone": ms, "line": no})
    return status, mode, cost, markers, steps, reviews, errors


def units_of(steps):
    """Consecutive steps under the same marker and in the same milestone: one dispatch unit."""
    units = []
    for s in steps:
        if units and units[-1]["label"] == s["label"] and units[-1]["milestone"] == s["milestone"]:
            units[-1]["steps"].append(s)
        else:
            units.append({"wave": s["wave"], "label": s["label"], "tier": s["tier"], "milestone": s["milestone"],
                          "steps": [s]})
    return units


def state(text):
    status, mode, cost, markers, steps, reviews, errors = parse(text)
    ns = [w["n"] for w in markers if not w["fix"]]  # a fix-up marker reuses its wave's number
    if ns != list(range(1, len(ns) + 1)):
        errors.append(f"wave markers are numbered {ns}, expected 1..{len(ns)} in order")
    for s in steps:
        if ORDER[s["tag"]] > ORDER[s["tier"]]:
            errors.append(f"{s['id']}: [{s['tag']}] step inside a [{s['tier']}] wave (the <= constraint)")
        if s["tier"] == "xdeep" and s["tag"] != "xdeep":
            errors.append(f"{s['id']}: [{s['tag']}] step inside an [xdeep] wave; re-run the no-thrash pass")
    seen = set()
    for s in steps:
        if s["id"] in seen:
            errors.append(f"step id {s['id']} appears twice")
        seen.add(s["id"])
    if not steps:
        errors.append("no tagged steps")

    out = {"version": 3, "t": len(ns), "done": sum(s["done"] for s in steps), "total": len(steps),
           "status": status, "mode": mode, "blocked": None, "concerns": [], "prev": None, "next": None, "gates": [],
           "stops": [], "checkpoints": [], "waivers": [], "cost": None, "milestones": any(s["milestone"] for s in steps),
           "errors": errors}
    m = BLOCKED_RE.search(status or "")
    if m:
        out["blocked"] = "gate-" + m.group(1)

    # Review log: the trailing run of CONCERNS per (wave, group), with its notes oldest first.
    streak, last = {}, {}
    for r in reviews:
        key = (r["wave"], r["group"])
        streak[key] = streak.get(key, []) + [r["note"]] if r["verdict"] == "CONCERNS" else []
        last[key] = r
    out["concerns"] = [{"wave": k[0], "group": k[1], "count": len(notes), "note": last[k]["note"], "notes": notes,
                        "source": "check" if last[k]["note"].startswith(CHECK_NOTE) else "review",
                        "from": last[k]["from"], "to": last[k]["to"]} for k, notes in streak.items() if notes]
    out["waivers"] = [{"wave": r["wave"], "group": r["group"], "words": r["note"]} for r in reviews if r["verdict"] == "WAIVED"]
    cap = mode["fixups"] if mode else DEFAULT_FIXUPS
    if cap < 1:
        errors.append(f"fixups {cap} on the mode line: the cap counts the first fix-up, so it is 1 or more")

    units = units_of(steps)
    gates = []
    if out["blocked"]:
        gates.append(out["blocked"])
    if out["concerns"]:
        first = min(c["wave"] for c in out["concerns"])
        k = max(c["count"] for c in out["concerns"] if c["wave"] == first)
        mine = [c for c in out["concerns"] if c["wave"] == first and c["count"] == k]  # the longest streak goes first
        u = next((u for u in units if u["label"] == str(first)), None)
        out["next"] = {"kind": "fixup", "wave": first, "label": fix_label(first, k), "fix": k,
                       "tier": u["tier"] if u else None, "milestone": u["milestone"] if u else None,
                       "groups": sorted(c["group"] for c in mine), "steps": [], "start": False}
        if k >= 2 or any(c["source"] == "check" for c in mine):
            gates.append("gate-1")  # a failed check, or a fix-up that drew CONCERNS again
        if u and u["tier"] == "xdeep":
            gates.append("gate-7")  # every [xdeep] dispatch; a fix-up row is unplanned (expected "—")
        if u is None:
            errors.append(f"Review log names wave {first}, which the plan has no steps for")
    else:
        idx = next((i for i, s in enumerate(steps) if not s["done"]), None)
        if idx is not None:
            u = next(u for u in units if steps[idx] in u["steps"])
            later_done = [s["id"] for s in steps[idx + 1:] if s["done"] and s not in u["steps"]]
            if later_done:
                errors.append(f"steps marked done after the first open step {steps[idx]['id']}: {', '.join(later_done)}")
            start = u["steps"][0] is steps[idx] and not any(s["done"] for s in u["steps"])
            pu = None
            if start and idx > 0:
                pu = next(x for x in units if steps[idx - 1] in x["steps"])
            elif not start:
                pu = u
            out["prev"] = pu and {"wave": pu["wave"], "tier": pu["tier"], "milestone": pu["milestone"]}
            out["next"] = {"kind": "wave", "wave": u["wave"], "label": u["label"], "fix": 0, "tier": u["tier"],
                           "milestone": u["milestone"], "steps": [s["id"] for s in u["steps"] if not s["done"]],
                           "groups": [], "start": start}
            if start and pu:
                if pu["milestone"] != u["milestone"] and (pu["milestone"] or u["milestone"]):
                    gates.append("gate-4")
                if ORDER[pu["tier"]] <= ORDER["exec"] and ORDER[u["tier"]] >= ORDER["deep"]:
                    gates.append("gate-3" if pu["tier"] == "fast" else "gate-2")
            wave_started = any(s["done"] for s in steps if s["label"] == u["label"])
            if u["tier"] == "xdeep" and not wave_started:
                gates.append("gate-7")
    nxt = out["next"]
    unattended = bool(mode) and mode["value"] == "unattended"
    if nxt:
        if mode is None or mode["value"] == "pending":
            gates.insert(0, "gate-mode")  # no confirmed answer to the kickoff question: dispatch nothing
        row = cost["rows"].get(nxt["label"])
        spend_next = (row or 0.0) if (nxt["kind"] == "fixup" or nxt["start"]) else 0.0
        guard = mode["guard"] if mode else DEFAULT_GUARD
        guard_min = mode["guard_min"] if mode else DEFAULT_GUARD_MIN
        out["cost"] = {"expected_total": cost["total"], "actual": round(cost["actual"], 2), "next_expected": row,
                       "projected": round(cost["actual"] + spend_next, 2), "guard": guard, "guard_min": guard_min,
                       "limit": None, "tripped": False}
        if cost["total"]:
            out["cost"]["limit"] = round(max(guard * cost["total"], guard_min), 2)
            out["cost"]["tripped"] = out["cost"]["projected"] > out["cost"]["limit"]
            if out["cost"]["tripped"]:
                gates.append("gate-guard")
        elif unattended:
            errors.append("unattended mode needs the Cost table's Total row for the cost guard")
    if errors:
        gates.insert(0, "gate-0")
    out["gates"] = list(dict.fromkeys(gates))
    planned = bool(nxt) and nxt["kind"] == "wave" and cost["rows"].get(nxt["label"]) is not None
    auto_fix = bool(nxt) and nxt["kind"] == "fixup" and nxt["fix"] <= cap  # past the cap, gate 1 stops
    soft = UNATTENDED_CHECKPOINTS | ({"gate-7"} if planned else set()) | ({"gate-1"} if auto_fix else set())
    blocked = out["blocked"]
    out["checkpoints"] = [g for g in out["gates"] if unattended and g in soft and g != blocked]
    out["stops"] = [g for g in out["gates"] if g not in out["checkpoints"]]
    return out


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip().splitlines()[-1])
    print(json.dumps(state(Path(sys.argv[1]).read_text()), separators=(",", ":")))


if __name__ == "__main__":
    main()
