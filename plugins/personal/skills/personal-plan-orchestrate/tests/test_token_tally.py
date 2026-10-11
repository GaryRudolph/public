#!/usr/bin/env python3
"""Tests for token_tally.py. Usage: test_token_tally.py <scripts-dir> <plan-execution.md>"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

scripts, table = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
tmp = Path(tempfile.mkdtemp())
sess = tmp / "sess-1"


def call(mid, model, out, stop, inp=10, read=1000, write=100):
    msg = {"id": mid, "model": model, "usage": {"input_tokens": inp, "cache_read_input_tokens": read,
           "cache_creation": {"ephemeral_5m_input_tokens": write, "ephemeral_1h_input_tokens": 0}, "output_tokens": out}}
    if stop:
        msg["stop_reason"] = "end_turn"
    return {"type": "assistant", "message": msg}


def agent(name, label, lines):
    d = sess / "subagents" / "workflows" / "wf_1"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"agent-{name}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    (d / f"agent-{name}.meta.json").write_text(json.dumps({"description": label}))


S, O = "claude-sonnet-5-5", "claude-opus-5-5"
# A Sonnet fix-up worker: call a has a stop_reason copy (exact), call b never does (placeholder 12).
agent("w", "Wave 2-fix of 4 [exec] repo-b m1 s3", [call("a", S, 3, False), call("a", S, 500, True), call("b", S, 12, False), call("b", S, 12, False)])
agent("r", "Review Wave 2-fix of 4 [exec] repo-b m1 s3", [call("c", O, 800, True)])
agent("x", "Wave 2 of 4 [deep] repo-a m1 s2 (retry)", [call("d", O, 9, False)])
agent("f2", "Wave 2-fix2 of 4 [exec] repo-b m1 s3", [call("e", S, 700, True)])
agent("r2", "Review Wave 2-fix2 of 4 [exec] repo-b m1 s3 (retry)", [call("f", O, 600, True)])
agent("h", "Wave 1 of 4 [fast] repo-c m1 s1", [call("g", "claude-haiku-4-5-20251001", 50, True)])
launch = lambda rid: {"type": "user", "toolUseResult": {"status": "async_launched", "runId": rid}, "message": {"content": []}}
(tmp / "sess-1.jsonl").write_text("".join(json.dumps(x) + "\n" for x in [
    call("p1", O, 300, True), launch("wf_1"), call("p2", O, 400, True, inp=20), launch("wf_2"), call("p3", O, 900, True)]))


def tally(*extra):
    out = subprocess.run([sys.executable, "-I", str(scripts / "token_tally.py"), "--session-dir", str(sess), "--table", str(table), *extra],
                         capture_output=True, text=True)
    return out.returncode, out.stdout, out.stderr


tests = []


def test(fn):
    tests.append(fn)
    return fn


@test
def a_call_with_a_stop_reason_line_is_exact_and_one_without_is_estimated():
    rc, out, _ = tally("--json")
    rows = {r["row"]: r for r in json.loads(out)["rows"]}
    w = rows["wave-2-fix repo-b-m1-s3"]
    assert w["output"] == 500 + 1000 and w["estimated_calls"] == 1 and w["input"] == 20, w
    assert rows["review-wave-2-fix repo-b-m1-s3"]["estimated_calls"] == 0


@test
def estimated_lines_say_so_and_name_the_session():
    _, out, _ = tally()
    line = next(l for l in out.splitlines() if l.startswith("tokens wave-2-fix "))
    assert line.endswith("API-equiv (output est.) session sess-1"), line
    review = next(l for l in out.splitlines() if l.startswith("tokens review-wave-2-fix "))
    assert review.endswith("API-equiv"), review


@test
def a_retry_keeps_its_wave_row_and_routes_by_its_own_tier():
    rc, out, err = tally("--check-routing")
    assert "tokens wave-2 repo-a-m1-s2 (claude-opus-5-5)" in out and rc == 0, (rc, err)


@test
def the_parent_line_covers_one_window_between_launches():
    _, out, _ = tally("--json", "--parent-window", "wf_1:wf_2", "--parent-row", "orchestrator-wave-1 m1-s1")
    p = next(r for r in json.loads(out)["rows"] if r["row"].startswith("orchestrator"))
    assert p["row"] == "orchestrator-wave-1 m1-s1" and p["output"] == 400 and p["input"] == 20, p
    _, out, _ = tally("--json", "--parent-window", "start:wf_1", "--parent-row", "orchestrator-kickoff plan-x")
    p = next(r for r in json.loads(out)["rows"] if r["row"].startswith("orchestrator"))
    assert p["output"] == 300, p
    _, out, _ = tally("--json")
    assert not any(r["row"].startswith("orchestrator") for r in json.loads(out)["rows"])


@test
def a_second_fix_up_gets_its_own_rows():
    rc, out, err = tally("--json", "--check-routing")
    rows = {r["row"]: r for r in json.loads(out)["rows"]}
    assert rows["wave-2-fix2 repo-b-m1-s3"]["output"] == 700 and rows["review-wave-2-fix2 repo-b-m1-s3"]["output"] == 600, rows.keys()
    assert rc == 0, err


@test
def labels_outside_the_fix_up_grammar_get_no_row():
    sys.path.insert(0, str(scripts))
    from token_tally import row_for
    assert row_for("Wave 2-fix12 of 4 [exec] repo-b m1 s3") == ("wave-2-fix12 repo-b-m1-s3", "exec")
    for bad in ("Wave 2-fix1 of 4 [exec] repo-b m1 s3", "Wave 2-fix01 of 4 [exec] repo-b m1 s3", "Wave 2-fix0 of 4 [exec] repo-b m1 s3"):
        assert row_for(bad) == (bad, None), row_for(bad)


@test
def a_lines_model_drops_the_date_suffix_and_pricing_uses_the_raw_id():
    rc, out, err = tally("--check-routing")
    line = next(l for l in out.splitlines() if l.startswith("tokens wave-1 repo-c-m1-s1 "))
    assert "(claude-haiku-4-5):" in line and "20251001" not in line and "n/a" not in line, line
    rows = {r["row"]: r for r in json.loads(tally("--json")[1])["rows"]}
    assert (rows["wave-1 repo-c-m1-s1"]["model"], rows["wave-1 repo-c-m1-s1"]["model_id"]) == ("claude-haiku-4-5", "claude-haiku-4-5-20251001")
    assert rc == 0, err


failed = 0
for fn in tests:
    try:
        fn()
        print(f"ok   {fn.__name__}")
    except AssertionError as e:
        failed += 1
        print(f"FAIL {fn.__name__}: {e}")
print(f"{len(tests) - failed}/{len(tests)} passed")
sys.exit(1 if failed else 0)
