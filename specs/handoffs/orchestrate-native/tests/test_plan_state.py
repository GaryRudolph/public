#!/usr/bin/env python3
"""Tests for plan_state.py. Usage: test_plan_state.py <scripts-dir>"""

import sys

sys.path.insert(0, sys.argv[1])
from plan_state import kickoff_prompt, state  # noqa: E402

KICK = """```
--- KICKOFF: begin orchestration at [deep] ---

  Status: {status}

  review: every-wave (log-only)
{mode}
#### s9 - [deep] example heading inside the fence is ignored
```
"""


GATED = "  mode: gated | proposed gated (no runner signal) | guard 2x | confirmed 2026-10-06 session s1: gated"
UNATTENDED = "  mode: unattended | proposed unattended (CLAUDE_CODE_REMOTE=true) | guard 2x | confirmed 2026-10-06 session s1: yes"
COST = """
**Cost (API-equiv, Claude Code models)**

| wave | expected tokens | expected $ |
|---|---|---|
| 1 [fast] m1 s1-s3 | ~3.4M | ~$0.90 |
| 2 [exec] m1 s4-s5 | ~4.0M | ~$1.6 |
| 3 [deep] m2 s1 | ~6.1M | ~$3.2 |
| 4 [xdeep] m2 s2-s3 | ~19M | ~$14 |
| orchestrator | ~6M | ~$5.0 |
| **Total** | ~38M | ~$25 |

Expected values are estimates, good to about 2-3× per wave.
"""


def plan(body, status="0/4 groups done | last review: — | current: m1 s1-s3 [fast] | updated 2026-10-06", log="",
         mode=GATED, cost=COST, tokens=""):
    text = KICK.format(status=status, mode=mode) + cost + "# Plan: x\n\n## m1 - Files\n\n" + body
    if log:
        text += "\n## Review log\n\n" + log
    if tokens:
        text += "\n## Token log\n\n" + tokens
    return text


BASE = """--- WAVE 1 [fast] ---
#### m1.s1 - [fast] One{d1}
#### m1.s2 - [fast] Two{d2}
#### m1.s3 - [fast] Three{d3}

--- WAVE 2 [exec] ---
#### m1.s4 - [exec] Four{d4}
#### m1.s5 - [fast] Five, folded{d5}

## m2 - Logic

--- WAVE 3 [deep] ---
#### m2.s1 - [deep] Decide{d6}

--- WAVE 4 [xdeep] ---
#### m2.s2 - [xdeep] Protocol{d7}
#### m2.s3 - [xdeep] Migration{d8}
"""


def marked(n):
    return BASE.format(**{f"d{i}": " (done)" if i <= n else "" for i in range(1, 9)})


tests = []


def test(fn):
    tests.append(fn)
    return fn


@test
def fresh_plan_starts_at_wave_1_with_no_gates():
    s = state(plan(marked(0)))
    assert s["errors"] == [], s["errors"]
    assert s["t"] == 4 and s["total"] == 8
    assert s["next"]["wave"] == 1 and s["next"]["steps"] == ["m1.s1", "m1.s2", "m1.s3"] and s["next"]["start"]
    assert s["prev"] is None and s["gates"] == []


@test
def fast_to_exec_in_one_milestone_needs_no_gate():
    s = state(plan(marked(3)))
    assert s["next"]["wave"] == 2 and s["next"]["tier"] == "exec" and s["gates"] == []
    assert s["prev"] == {"wave": 1, "tier": "fast", "milestone": "m1"}


@test
def exec_to_deep_across_a_milestone_needs_gates_4_and_2():
    s = state(plan(marked(5)))
    assert s["next"]["wave"] == 3 and s["next"]["milestone"] == "m2"
    assert s["gates"] == ["gate-4", "gate-2"], s["gates"]


@test
def deep_to_xdeep_needs_gate_7_only_at_wave_start():
    assert state(plan(marked(6)))["gates"] == ["gate-7"]
    s = state(plan(marked(7)))
    assert s["next"]["steps"] == ["m2.s3"] and not s["next"]["start"] and s["gates"] == []


@test
def a_blocked_status_line_is_a_gate_to_approve():
    s = state(plan(marked(1), status="1/4 groups done | BLOCKED at gate 5 (canary) | updated 2026-10-06"))
    assert s["blocked"] == "gate-5" and s["gates"] == ["gate-5"]
    assert s["next"]["steps"] == ["m1.s2", "m1.s3"] and not s["next"]["start"]


@test
def one_concerns_line_schedules_a_fix_up_and_two_need_gate_1():
    one = "review wave-2 (repo-b m1 s4) 846932b..518e99f: CONCERNS - gamma lacks a newline - 2026-10-06\n"
    s = state(plan(marked(5), log=one))
    assert s["next"]["kind"] == "fixup" and s["next"]["groups"] == ["repo-b m1 s4"] and s["gates"] == []
    assert s["concerns"][0]["from"] == "846932b"
    two = one + "review wave-2 (repo-b m1 s4) 846932b..9abcdef: CONCERNS - still no newline - 2026-10-06\n"
    assert state(plan(marked(5), log=two))["gates"] == ["gate-1"]
    fixed = two + "review wave-2 (repo-b m1 s4) 846932b..1234567: PASS - newline added - 2026-10-06\n"
    s = state(plan(marked(5), log=fixed))
    assert s["next"]["kind"] == "wave" and s["next"]["wave"] == 3


@test
def a_tag_above_its_wave_is_gate_0():
    s = state(plan(marked(0).replace("#### m1.s4 - [exec] Four", "#### m1.s4 - [deep] Four")))
    assert s["gates"][0] == "gate-0" and any("<= constraint" in e for e in s["errors"])


@test
def a_step_before_any_wave_marker_is_gate_0():
    s = state(plan("#### m1.s0 - [exec] Early\n" + marked(0)))
    assert s["gates"][0] == "gate-0"


@test
def a_wave_that_spans_milestones_splits_into_units_with_gate_4():
    body = "--- WAVE 1 [exec] ---\n#### m1.s1 - [exec] A (done)\n#### m2.s1 - [exec] B\n"
    s = state(plan(body))
    assert s["next"]["wave"] == 1 and s["next"]["milestone"] == "m2" and s["next"]["start"]
    assert s["gates"] == ["gate-4"]


@test
def milestone_comes_from_the_enclosing_heading_when_ids_lack_it():
    body = "--- WAVE 1 [exec] ---\n#### s1 - [exec] A (done)\n\n## m2 - Next\n\n--- WAVE 2 [exec] ---\n#### s2 - [exec] B\n"
    s = state(plan(body))
    assert s["next"]["milestone"] == "m2" and s["gates"] == ["gate-4"]


@test
def done_steps_after_the_first_open_step_are_gate_0():
    s = state(plan(marked(0).replace("Four", "Four (done)")))
    assert s["gates"][0] == "gate-0"


@test
def a_finished_plan_has_no_next_unit():
    s = state(plan(marked(8)))
    assert s["next"] is None and s["gates"] == []


@test
def misnumbered_wave_markers_are_gate_0():
    s = state(plan(marked(0).replace("WAVE 3", "WAVE 5")))
    assert s["gates"][0] == "gate-0"


@test
def a_plan_with_no_confirmed_mode_dispatches_nothing():
    assert state(plan(marked(0), mode=""))["stops"] == ["gate-mode"]
    pending = "  mode: pending | proposed unattended (CLAUDE_CODE_REMOTE=true) | guard 2x"
    s = state(plan(marked(0), mode=pending))
    assert s["mode"]["value"] == "pending" and s["mode"]["proposed"] == "unattended" and s["stops"] == ["gate-mode"]
    assert state(plan(marked(8), mode=""))["gates"] == []  # nothing left to dispatch


@test
def the_mode_line_keeps_the_words_verbatim():
    m = state(plan(marked(0), mode="  mode: unattended | proposed gated (no runner signal) | guard 3x | confirmed 2026-10-06 session ab-12: unattended | no stops, thanks"))["mode"]
    assert m == {"value": "unattended", "proposed": "gated", "signal": "no runner signal", "guard": 3.0, "guard_min": 50.0, "fixups": 2,
                 "date": "2026-10-06", "session": "ab-12", "via": "answer", "words": "unattended | no stops, thanks"}
    m = state(plan(marked(0), mode="  mode: gated | guard 2x | fixups 3 | confirmed 2026-10-06 session s1: gated, guard 9x, fixups 9"))["mode"]
    assert (m["guard"], m["fixups"]) == (2.0, 3)  # fields come only from before "confirmed"


@test
def gated_mode_stops_at_every_gate():
    s = state(plan(marked(5)))
    assert s["stops"] == ["gate-4", "gate-2"] and s["checkpoints"] == []


@test
def unattended_mode_turns_review_and_milestone_gates_into_checkpoints():
    s = state(plan(marked(5), mode=UNATTENDED))
    assert s["gates"] == ["gate-4", "gate-2"] and s["checkpoints"] == ["gate-4", "gate-2"] and s["stops"] == []


@test
def unattended_gate_7_is_a_checkpoint_only_on_a_planned_xdeep_wave():
    assert state(plan(marked(6), mode=UNATTENDED))["checkpoints"] == ["gate-7"]
    unplanned = COST.replace("| 4 [xdeep] m2 s2-s3 | ~19M | ~$14 |\n", "")
    assert state(plan(marked(6), mode=UNATTENDED, cost=unplanned))["stops"] == ["gate-7"]


@test
def an_xdeep_fix_up_is_gate_7_and_stops_unattended():
    log = "review wave-4 (repo-a m2 s2-s3) 1111111..2222222: CONCERNS - replay window - 2026-10-06\n"
    s = state(plan(marked(8), log=log, mode=UNATTENDED))
    assert s["next"]["kind"] == "fixup" and s["next"]["label"] == "4-fix"
    assert s["stops"] == ["gate-7"] and s["checkpoints"] == []


@test
def a_blocked_gate_stops_even_unattended():
    s = state(plan(marked(5), status="5/8 | BLOCKED at gate 4 (milestone) | updated 2026-10-06", mode=UNATTENDED))
    assert "gate-4" in s["stops"] and "gate-2" in s["checkpoints"]


@test
def unattended_needs_the_cost_table():
    s = state(plan(marked(0), mode=UNATTENDED, cost=""))
    assert s["stops"][0] == "gate-0" and any("Cost table" in e for e in s["errors"])


@test
def the_cost_guard_trips_on_projected_spend_in_every_mode():
    under = "tokens wave-1 repo-a-m1-s1-s3 (claude-haiku-4-5): input ~1k / cache read ~1M / cache write ~0.1M / output ~20k | ~$30.00 API-equiv\n"
    s = state(plan(marked(5), tokens=under))
    assert s["cost"]["actual"] == 30.0 and s["cost"]["next_expected"] == 3.2 and s["cost"]["projected"] == 33.2
    assert not s["cost"]["tripped"]  # 33.2 <= 2 x 25
    over = under.replace("$30.00", "$48.00")
    for mode in (GATED, UNATTENDED):
        s = state(plan(marked(5), tokens=over, mode=mode))
        assert s["cost"]["tripped"] and "gate-guard" in s["stops"], s
    raised = UNATTENDED.replace("guard 2x", "guard 3x")
    assert "gate-guard" not in state(plan(marked(5), tokens=over, mode=raised))["gates"]


@test
def the_cost_guard_never_trips_below_its_floor():
    small = COST.replace("~$25 |", "~$10 |")
    under = "tokens wave-1 repo-a-m1-s1-s3 (claude-haiku-4-5): input ~1k / cache read ~1M / cache write ~0.1M / output ~20k | ~$40.00 API-equiv\n"
    s = state(plan(marked(5), tokens=under, mode=UNATTENDED.replace("guard 2x", "guard 3x min $50"), cost=small))
    assert s["cost"]["limit"] == 50.0 and s["cost"]["projected"] == 43.2 and not s["cost"]["tripped"], s["cost"]  # past 3 x 10, under $50
    over = under.replace("$40.00", "$47.00")
    s = state(plan(marked(5), tokens=over, mode=UNATTENDED.replace("guard 2x", "guard 3x min $50"), cost=small))
    assert s["cost"]["tripped"] and "gate-guard" in s["stops"], s["cost"]  # 50.2 > max(30, 50)
    big = COST.replace("~$25 |", "~$78 |")
    s = state(plan(marked(5), tokens=under.replace("$40.00", "$200.00"), mode=UNATTENDED.replace("guard 2x", "guard 3x min $50"), cost=big))
    assert s["cost"]["limit"] == 234.0 and not s["cost"]["tripped"], s["cost"]  # 3 x 78 wins over the floor
    default = UNATTENDED.replace(" | guard 2x", "")
    assert state(plan(marked(5), tokens=under, mode=default, cost=small))["cost"]["limit"] == 50.0  # defaults: 3x, $50


@test
def a_continuation_adds_nothing_to_the_projection():
    over = "tokens wave-4 repo-a-m2-s2-s3 (claude-opus-5-5): input ~1k / cache read ~1M / cache write ~0.1M / output ~20k | ~$45.00 API-equiv (output est.) session s1\n"
    s = state(plan(marked(7), tokens=over, mode=UNATTENDED))
    assert not s["next"]["start"] and s["cost"]["projected"] == 45.0 and not s["cost"]["tripped"]


@test
def a_fix_up_review_logged_as_wave_n_fix_resets_the_streak():
    log = ("review wave-2 (repo-b m1 s4) 846932b..518e99f: CONCERNS - gamma lacks a newline - 2026-10-06\n"
           "review wave-2-fix (repo-b m1 s4) 846932b..1234567: PASS - newline added - 2026-10-06\n")
    s = state(plan(marked(5), log=log))
    assert s["next"]["kind"] == "wave" and s["next"]["wave"] == 3
    again = log.replace("PASS - newline added", "CONCERNS - still no newline")
    assert state(plan(marked(5), log=again))["stops"] == ["gate-1"]


# ---- v4: automatic fix-ups (unattended), fix-up numbering ----

C1 = "review wave-2 (repo-b m1 s4) 846932b..518e99f: CONCERNS - gamma lacks a newline - 2026-10-06\n"
CHECK1 = "review wave-2 (repo-b m1 s4) 846932b..518e99f: CONCERNS - check_wave.py: repo-b: m1.s4 has no commit - 2026-10-06\n"


def again(n, note="still wrong"):
    return f"review wave-2-fix{'' if n == 1 else n} (repo-b m1 s4) 846932b..{n}{n}{n}{n}{n}{n}{n}: CONCERNS - {note} - 2026-10-06\n"


@test
def check_failure_unattended_is_an_automatic_fix_up():
    s = state(plan(marked(5), log=CHECK1, mode=UNATTENDED))
    n = s["next"]
    assert (n["kind"], n["label"], n["fix"], n["groups"]) == ("fixup", "2-fix", 1, ["repo-b m1 s4"]), n
    assert s["concerns"][0]["source"] == "check" and s["concerns"][0]["note"].startswith("check_wave.py: repo-b")
    assert s["gates"] == ["gate-1"] and s["checkpoints"] == ["gate-1"] and s["stops"] == [], s


@test
def check_failure_gated_still_stops():
    s = state(plan(marked(5), log=CHECK1))
    assert s["next"]["label"] == "2-fix" and s["stops"] == ["gate-1"] and s["checkpoints"] == []


@test
def a_first_review_concerns_needs_no_gate_in_either_mode():
    for mode in (GATED, UNATTENDED):
        s = state(plan(marked(5), log=C1, mode=mode))
        assert s["next"]["label"] == "2-fix" and s["gates"] == [] and s["concerns"][0]["source"] == "review"


@test
def concerns_twice_unattended_is_fix_up_2():
    s = state(plan(marked(5), log=C1 + again(1), mode=UNATTENDED))
    assert (s["next"]["label"], s["next"]["fix"]) == ("2-fix2", 2)
    assert s["checkpoints"] == ["gate-1"] and s["stops"] == []
    assert s["concerns"][0]["notes"] == ["gamma lacks a newline", "still wrong"]


@test
def a_check_failure_after_a_concerns_extends_the_streak():
    log = C1 + "review wave-2-fix (repo-b m1 s4) 846932b..9abcdef: CONCERNS - check_wave.py: repo-b: 9abcdef has a Co-authored-by line - 2026-10-06\n"
    s = state(plan(marked(5), log=log, mode=UNATTENDED))
    assert s["next"]["label"] == "2-fix2" and s["checkpoints"] == ["gate-1"] and s["concerns"][0]["source"] == "check"


@test
def a_third_failure_stops_unattended():
    s = state(plan(marked(5), log=C1 + again(1) + again(2), mode=UNATTENDED))
    assert (s["next"]["label"], s["next"]["fix"]) == ("2-fix3", 3)
    assert s["stops"] == ["gate-1"] and s["checkpoints"] == []


@test
def concerns_twice_gated_still_stops():
    s = state(plan(marked(5), log=C1 + again(1)))
    assert s["next"]["label"] == "2-fix2" and s["stops"] == ["gate-1"]


@test
def the_fix_up_cap_comes_from_the_mode_line():
    three = UNATTENDED.replace("guard 2x", "guard 2x | fixups 3")
    assert state(plan(marked(5), log=C1 + again(1) + again(2), mode=three))["checkpoints"] == ["gate-1"]
    assert state(plan(marked(5), log=C1 + again(1) + again(2) + again(3), mode=three))["stops"] == ["gate-1"]
    one = UNATTENDED.replace("guard 2x", "guard 2x | fixups 1")
    assert state(plan(marked(5), log=C1 + again(1), mode=one))["stops"] == ["gate-1"]
    zero = UNATTENDED.replace("guard 2x", "guard 2x | fixups 0")
    s = state(plan(marked(5), log=C1, mode=zero))
    assert s["stops"][0] == "gate-0" and any("fixups 0" in e for e in s["errors"])


@test
def a_pass_on_fix_up_2_ends_the_streak():
    log = C1 + again(1) + "review wave-2-fix2 (repo-b m1 s4) 846932b..7777777: PASS - fixed - 2026-10-06\n"
    s = state(plan(marked(5), log=log, mode=UNATTENDED))
    assert s["next"]["kind"] == "wave" and s["next"]["wave"] == 3 and s["concerns"] == []


@test
def the_longest_streak_goes_first():
    other = "review wave-2 (repo-c m1 s5) 1111111..2222222: CONCERNS - delta - 2026-10-06\n"
    s = state(plan(marked(5), log=C1 + other + again(1), mode=UNATTENDED))
    assert s["next"]["groups"] == ["repo-b m1 s4"] and s["next"]["label"] == "2-fix2"
    log = C1 + other + again(1) + "review wave-2-fix2 (repo-b m1 s4) 846932b..7777777: PASS - fixed - 2026-10-06\n"
    s = state(plan(marked(5), log=log, mode=UNATTENDED))
    assert s["next"]["groups"] == ["repo-c m1 s5"] and s["next"]["label"] == "2-fix" and s["gates"] == []


@test
def an_xdeep_fix_up_2_still_stops_at_gate_7():
    log = ("review wave-4 (repo-a m2 s2-s3) 1111111..2222222: CONCERNS - replay window - 2026-10-06\n"
           "review wave-4-fix (repo-a m2 s2-s3) 1111111..3333333: CONCERNS - still open - 2026-10-06\n")
    s = state(plan(marked(8), log=log, mode=UNATTENDED))
    assert s["next"]["label"] == "4-fix2" and s["stops"] == ["gate-7"] and s["checkpoints"] == ["gate-1"]


@test
def fix_up_cost_rows_are_unplanned_and_the_guard_still_applies():
    cost = COST.replace("| 3 [deep] m2 s1 |", "| 2-fix [exec] repo-b m1 s4 | — | — |\n| 2-fix2 [exec] repo-b m1 s4 | — | — |\n| 3 [deep] m2 s1 |")
    spent = "tokens wave-2-fix repo-b-m1-s4 (claude-sonnet-5-5): input ~1k / cache read ~1M / cache write ~0.1M / output ~20k | ~$20.00 API-equiv\n"
    s = state(plan(marked(5), log=C1 + again(1), mode=UNATTENDED, cost=cost, tokens=spent))
    assert s["cost"]["next_expected"] is None and s["cost"]["projected"] == 20.0 and s["cost"]["expected_total"] == 25
    assert s["stops"] == []
    over = spent.replace("$20.00", "$51.00")
    s = state(plan(marked(5), log=C1 + again(1), mode=UNATTENDED, cost=cost, tokens=over))
    assert s["stops"] == ["gate-guard"] and s["checkpoints"] == ["gate-1"]


@test
def a_fix_up_marker_keeps_the_numbering_and_labels_its_unit():
    body = marked(5).replace("## m2 - Logic", "--- WAVE 2-fix [exec] ---\n#### m1.s6 - [exec] Newline fix\n\n## m2 - Logic")
    s = state(plan(body, mode=UNATTENDED))
    assert s["errors"] == [] and s["t"] == 4, s["errors"]
    assert (s["next"]["kind"], s["next"]["label"], s["next"]["wave"], s["next"]["steps"]) == ("wave", "2-fix", 2, ["m1.s6"])
    assert s["checkpoints"] == [] and s["stops"] == []


@test
def a_waived_line_ends_the_streak_and_is_listed():
    waive = "review wave-2-fix (repo-b m1 s4) 846932b..1111111: WAIVED - waive it - the newline doesn't matter - 2026-10-06\n"
    for mode in (GATED, UNATTENDED):
        s = state(plan(marked(5), log=CHECK1 + again(1) + waive, mode=mode))
        assert s["next"]["kind"] == "wave" and s["next"]["wave"] == 3 and s["concerns"] == [], s["next"]
        assert s["waivers"] == [{"wave": 2, "group": "repo-b m1 s4", "words": "waive it - the newline doesn't matter"}]
    assert state(plan(marked(5), log=C1))["waivers"] == []


@test
def fix_up_labels_outside_the_grammar_are_gate_0():
    body = marked(5).replace("## m2 - Logic", "--- WAVE 2-fix1 [exec] ---\n#### m1.s6 - [exec] Newline fix\n\n## m2 - Logic")
    s = state(plan(body))
    assert s["stops"][0] == "gate-0" and any("2-fix1" in e and "not a wave marker" in e for e in s["errors"]), s["errors"]
    s = state(plan(marked(5), log=C1.replace("wave-2 ", "wave-2-fix1 ")))
    assert s["stops"][0] == "gate-0" and any("doesn't parse" in e for e in s["errors"]), s["errors"]
    s = state(plan(body.replace("2-fix1 [exec]", "2-fix10 [exec]")))
    assert s["errors"] == [] and s["next"]["label"] == "2-fix10", s["errors"]


# ---- v6: the Kickoff prompt carries the confirmed mode ----

def prompted(mode_line, prompt_mode):
    """A Kickoff block with its prompt; prompt_mode None leaves the prompt's mode line out, as before the kickoff answer."""
    lines = ["Read specs/handoffs/plan-x.md. The plan is already tagged.",
             "On branch feature/x (task branch): subagents commit each finished step."]
    lines += [f"Run in {prompt_mode} mode."] if prompt_mode else []
    lines += ["Run the personal-plan-orchestrate skill from the top."]
    return mode_line + "\n\n  Prompt to paste into the next chat:\n" + "".join(f"    {x}\n" for x in lines) + "\n---"


BY_PROMPT = "  mode: unattended | proposed unattended (CLAUDE_CODE_REMOTE=true) | guard 2x | confirmed 2026-10-07 session b2 by Kickoff prompt: Run in unattended mode."


@test
def the_kickoff_prompt_carries_the_confirmed_mode():
    s = state(plan(marked(0), mode=prompted(UNATTENDED, "unattended")))
    assert s["errors"] == [] and s["prompt_mode"] == "unattended" and s["mode"]["via"] == "answer", s["errors"]
    text = plan(marked(0), mode=prompted(BY_PROMPT, "unattended"))
    s = state(text)
    assert s["errors"] == [] and (s["mode"]["via"], s["mode"]["session"], s["mode"]["words"]) == ("prompt", "b2", "Run in unattended mode.")
    assert kickoff_prompt(text).splitlines()[2] == "Run in unattended mode." and len(kickoff_prompt(text).splitlines()) == 4
    pending = "  mode: pending | proposed unattended (CLAUDE_CODE_REMOTE=true) | guard 2x"
    s = state(plan(marked(0), mode=prompted(pending, None)))
    assert s["errors"] == [] and s["prompt_mode"] is None and s["stops"] == ["gate-mode"]
    assert state(plan(marked(0)))["prompt_mode"] is None and kickoff_prompt(plan(marked(0))) is None


@test
def a_kickoff_prompt_that_disagrees_with_the_mode_line_is_gate_0():
    for mode_line, prompt_mode, why in ((UNATTENDED, "gated", "names gated mode, but the confirmed mode is unattended"),
                                        (GATED, None, "has no mode line, but the confirmed mode is gated"),
                                        ("  mode: pending | proposed gated (no runner signal)", "gated", "no mode is confirmed yet")):
        s = state(plan(marked(0), mode=prompted(mode_line, prompt_mode)))
        assert s["stops"][0] == "gate-0" and any(why in e for e in s["errors"]), s["errors"]
    s = state(plan(marked(0), mode=prompted(GATED, "gated").replace("Run in gated mode.", "Run in gated mode, please.")))
    assert s["prompt_mode"] is None and s["stops"][0] == "gate-0"  # only the exact line counts


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
