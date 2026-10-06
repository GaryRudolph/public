// Runs plan-segment.js against fake agent()/parallel()/pipeline() to check
// the gate and routing logic without spawning anything.
// Usage: node plan-segment-test.mjs <plan-segment.js>
import { readFileSync } from 'node:fs'
import assert from 'node:assert/strict'

const src = readFileSync(process.argv[2], 'utf8')
if (/\bimport\s*\(|Date\.now\(|Math\.random\(|new Date\(\s*\)/.test(src)) throw new Error('script uses a forbidden API')
const metaMatch = src.match(/^export const meta = (\{[\s\S]*?\n\})\n/)
assert.ok(metaMatch, 'meta must be the first statement')
assert.ok(!/[`$]|\.\.\.|\(/.test(metaMatch[1].replace(/'[^']*'/g, "''")), 'meta must be a pure literal')
const body = src.slice(metaMatch[0].length)
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const run = new AsyncFunction('agent', 'parallel', 'pipeline', 'phase', 'log', 'args', 'budget', body)

const DONE = { status: 'done', changed: 'x', decided: 'y', surprises: 'none', artifact: '/a.md', commits: ['abc1234'] }
async function harness(args, behave = {}) {
  const calls = []
  const agent = async (prompt, opts) => {
    calls.push({ ...opts, prompt })
    const kind = opts.label.split(' ')[0]
    if (behave[kind]) return behave[kind](opts, prompt)
    if (kind === 'Wave') return DONE
    if (kind === 'Review') return { verdict: 'PASS', note: 'ok', findings: [] }
    if (kind === 'Draft') return { design: 'd', risks: 'r' }
    if (kind === 'Judge') return { pick: 1, synthesis: 'syn' }
    throw new Error(`unexpected agent ${opts.label}`)
  }
  const parallel = async thunks => Promise.all(thunks.map(t => t().catch(() => null)))
  const pipeline = async (items, ...stages) => Promise.all(items.map(async (item, i) => {
    let v = item
    for (const [k, s] of stages.entries()) {
      try { v = await (k === 0 ? s(item, item, i) : s(v, item, i)) } catch { return null }
    }
    return v
  }))
  const result = await run(agent, parallel, pipeline, () => {}, () => {}, structuredClone(args), { total: null, spent: () => 0, remaining: () => Infinity })
  return { result, calls }
}

const unit = (wave, tier, steps, extra = {}) => ({ kind: 'wave', wave, tier, milestone: 'm1', steps, groups: [], start: true, ...extra })
const GATED = { value: 'gated', proposed: 'gated', signal: 'no runner signal', guard: 2, fixups: 2, date: '2026-10-06', session: 's1', words: 'gated' }
const UNATT = { value: 'unattended', proposed: 'unattended', signal: 'CLAUDE_CODE_REMOTE=true', guard: 2, fixups: 2, date: '2026-10-06', session: 's1', words: 'unattended' }
const st = (next, gates = [], extra = {}) => ({ version: 3, t: 4, done: 0, total: 9, status: null, mode: GATED, blocked: null, concerns: [], prev: null, next, gates, stops: gates, checkpoints: [], cost: null, milestones: true, errors: [], ...extra })
const un = (next, stops = [], checkpoints = [], extra = {}) => st(next, [...stops, ...checkpoints], { mode: UNATT, stops, checkpoints, ...extra })
const G = (dir, steps, extra = {}) => ({ workdir: dir, steps, spec: 'spec', acceptance: 'ac', standards: [], branch: 'feature/x', from: 'aaa0000', ...extra })
const base = { plugin: 'personal', plan: { name: 'plan-x', path: '/p/plan-x.md' }, canaryDone: true, approved: [], trailers: ['Assisted-by: Claude Code'] }
const kinds = calls => calls.map(c => c.label.split(' ')[0])
const tests = []
const test = (name, fn) => tests.push([name, fn])

test('plan errors are gate 0 and spawn nothing', async () => {
  const { result, calls } = await harness({ ...base, state: st(null, ['gate-0'], { errors: ['s3: [deep] step inside a [exec] wave'] }), groups: [G('/r/a', ['m1.s1'])] })
  assert.deepEqual(result.gates, ['gate-0'])
  assert.match(result.reason, /<= constraint|inside a \[exec\]/)
  assert.equal(calls.length, 0)
})

test('a gate the plan state reports and nobody approved spawns nothing', async () => {
  const { result, calls } = await harness({ ...base, state: st(unit(3, 'deep', ['m2.s1']), ['gate-4', 'gate-2']), groups: [G('/r/a', ['m2.s1'])] })
  assert.equal(result.stop, 'gate')
  assert.deepEqual(result.gates, ['gate-4', 'gate-2'])
  assert.equal(calls.length, 0)
})

test('an approval recorded for another wave does not count (H1)', async () => {
  const { result, calls } = await harness({ ...base, approval: 'yes', approved: [{ gate: 'gate-2', wave: 3 }], state: st(unit(6, 'deep', ['m2.s9']), ['gate-2']), groups: [G('/r/a', ['m2.s9'])] })
  assert.deepEqual(result.gates, ['gate-2'])
  assert.equal(calls.length, 0)
})

test('approvals without the human answer are gate 0', async () => {
  const { result } = await harness({ ...base, approved: [{ gate: 'gate-2', wave: 3 }], state: st(unit(3, 'deep', ['m2.s1']), ['gate-2']), groups: [G('/r/a', ['m2.s1'])] })
  assert.deepEqual(result.gates, ['gate-0'])
})

test('approved gates for this wave let it run, on Opus high', async () => {
  const { result, calls } = await harness({ ...base, approval: 'yes, start wave 3', approved: [{ gate: 'gate-4', wave: 3 }, { gate: 'gate-2', wave: 3 }], state: st(unit(3, 'deep', ['m2.s1']), ['gate-4', 'gate-2']), groups: [G('/r/a', ['m2.s1'])] })
  assert.equal(result.stop, 'done')
  assert.deepEqual(kinds(calls), ['Wave', 'Review'])
  assert.deepEqual([calls[0].agentType, calls[0].model, calls[0].effort], ['personal:plan-worker', 'opus', 'high'])
  assert.deepEqual([calls[1].agentType, calls[1].model, calls[1].effort], ['personal:plan-reviewer', 'opus', 'high'])
})

test('canary runs one group of the unit, then gate 5', async () => {
  const { result, calls } = await harness({ ...base, canaryDone: false, state: st(unit(1, 'exec', ['m1.s1', 'm1.s2'])), groups: [G('/r/a', ['m1.s1']), G('/r/b', ['m1.s2'])] })
  assert.deepEqual(result.gates, ['gate-5'])
  assert.deepEqual(kinds(calls), ['Wave', 'Review'])
  assert.equal(result.groups.length, 1)
})

test('canary stops even when the unit has one group', async () => {
  const { result } = await harness({ ...base, canaryDone: undefined, state: st(unit(1, 'fast', ['m1.s1'])), groups: [G('/r/a', ['m1.s1'])] })
  assert.deepEqual(result.gates, ['gate-5'])
})

test('two working directories run in parallel and each gets one review', async () => {
  const { result, calls } = await harness({ ...base, state: st(unit(2, 'exec', ['m1.s2', 'm1.s3'])), groups: [G('/r/repo-a', ['m1.s2']), G('/r/repo-b', ['m1.s3'])] })
  assert.equal(result.stop, 'done')
  assert.deepEqual(kinds(calls).sort(), ['Review', 'Review', 'Wave', 'Wave'])
  assert.deepEqual(result.groups.map(g => g.id), ['repo-a m1 s2', 'repo-b m1 s3'])
  const w = calls.find(c => c.label === 'Wave 2 of 4 [exec] repo-a m1 s2')
  assert.deepEqual([w.agentType, w.model, w.effort], ['personal:plan-worker', 'sonnet', 'high'])
  assert.match(w.prompt, /exactly these trailer lines[\s\S]*Assisted-by: Claude Code/)
  assert.match(w.prompt, /Never add `Co-authored-by`/)
  assert.match(w.prompt, /log --format=%s aaa0000\.\.HEAD/)
})

test('fast routes to Haiku with no effort', async () => {
  const { calls } = await harness({ ...base, state: st(unit(1, 'fast', ['m1.s1'])), groups: [G('/r/a', ['m1.s1'])] })
  assert.equal(calls[0].model, 'haiku')
  assert.equal(calls[0].effort, undefined)
  assert.match(calls[0].prompt, /Mechanical edits/)
})

test('an approved [xdeep] wave runs Opus max with no fan-out by default', async () => {
  const { result, calls } = await harness({ ...base, approval: 'go', approved: [{ gate: 'gate-7', wave: 4 }], state: st(unit(4, 'xdeep', ['m2.s4']), ['gate-7']), groups: [G('/r/a', ['m2.s4'])] })
  assert.equal(result.stop, 'done')
  assert.deepEqual(kinds(calls), ['Wave', 'Review'])
  assert.deepEqual(calls.map(c => [c.agentType, c.model, c.effort]), [['personal:plan-worker-max', 'opus', 'max'], ['personal:plan-reviewer-max', 'opus', 'max']])
})

test('xdeepDrafts 3 adds three drafts and a judge', async () => {
  const { calls } = await harness({ ...base, xdeepDrafts: 3, approval: 'go', approved: [{ gate: 'gate-7', wave: 4 }], state: st(unit(4, 'xdeep', ['m2.s4']), ['gate-7']), groups: [G('/r/a', ['m2.s4'])] })
  assert.deepEqual(kinds(calls), ['Draft', 'Draft', 'Draft', 'Judge', 'Wave', 'Review'])
  assert.match(calls[4].prompt, /Chosen design[\s\S]*syn/)
})

test('xdeepDrafts on an [exec] wave is gate 0', async () => {
  const { result } = await harness({ ...base, xdeepDrafts: 3, state: st(unit(2, 'exec', ['m1.s2'])), groups: [G('/r/a', ['m1.s2'])] })
  assert.deepEqual(result.gates, ['gate-0'])
})

test('a step-up needs gate 6 on top of the blocked gate 1', async () => {
  const s = st(unit(2, 'exec', ['m1.s2'], { start: false }), ['gate-1'], { blocked: 'gate-1' })
  const one = await harness({ ...base, stepUp: 'deep', approval: 'retry on opus', approved: [{ gate: 'gate-1', wave: 2 }], state: s, groups: [G('/r/a', ['m1.s2'])] })
  assert.deepEqual(one.result.gates, ['gate-6'])
  assert.equal(one.calls.length, 0)
  const two = await harness({ ...base, stepUp: 'deep', approval: 'retry on opus', approved: [{ gate: 'gate-1', wave: 2 }, { gate: 'gate-6', wave: 2 }], state: s, groups: [G('/r/a', ['m1.s2'])] })
  assert.equal(two.result.stop, 'done')
  assert.deepEqual([two.calls[0].model, two.calls[0].effort], ['opus', 'high'])
  assert.match(two.calls[0].label, /^Wave 2 of 4 \[deep\]/)
})

test('a Fable step-up needs gates 6 and 7 and runs on the max worker', async () => {
  const s = st(unit(4, 'xdeep', ['m2.s4'], { start: false }), ['gate-1'], { blocked: 'gate-1' })
  const one = await harness({ ...base, stepUp: 'fable', approval: 'try fable', approved: [{ gate: 'gate-1', wave: 4 }, { gate: 'gate-6', wave: 4 }], state: s, groups: [G('/r/a', ['m2.s4'])] })
  assert.deepEqual(one.result.gates, ['gate-7'])
  const two = await harness({ ...base, stepUp: 'fable', approval: 'try fable', approved: ['gate-1', 'gate-6', 'gate-7'].map(gate => ({ gate, wave: 4 })), state: s, groups: [G('/r/a', ['m2.s4'])] })
  assert.deepEqual([two.calls[0].agentType, two.calls[0].model, two.calls[0].effort], ['personal:plan-worker-max', 'fable', 'max'])
  assert.deepEqual([two.calls[1].agentType, two.calls[1].model], ['personal:plan-reviewer-max', 'opus'])
})

test('a step-up that is not above the wave tier is gate 0', async () => {
  const { result } = await harness({ ...base, stepUp: 'exec', state: st(unit(3, 'deep', ['m2.s1'])), groups: [G('/r/a', ['m2.s1'])] })
  assert.deepEqual(result.gates, ['gate-0'])
})

test('groups that miss a step of the unit are gate 0 (H2)', async () => {
  const { result, calls } = await harness({ ...base, state: st(unit(2, 'exec', ['m1.s2', 'm1.s3'])), groups: [G('/r/a', ['m1.s2'])] })
  assert.deepEqual(result.gates, ['gate-0'])
  assert.match(result.reason, /cover steps/)
  assert.equal(calls.length, 0)
})

test('two groups on one working directory are gate 0', async () => {
  const { result } = await harness({ ...base, state: st(unit(2, 'exec', ['m1.s2', 'm1.s3'])), groups: [G('/r/a', ['m1.s2']), G('/r/a', ['m1.s3'])] })
  assert.deepEqual(result.gates, ['gate-0'])
})

test('every group commits on its task branch: trailers, never Co-authored-by, and no shared-branch mode (v6)', async () => {
  const s = st(unit(1, 'fast', ['m1.s1']))
  assert.deepEqual((await harness({ ...base, trailers: [], state: s, groups: [G('/r/a', ['m1.s1'])] })).result.gates, ['gate-0'])
  assert.deepEqual((await harness({ ...base, trailers: ['Co-Authored-By: Claude <noreply@anthropic.com>'], state: s, groups: [G('/r/a', ['m1.s1'])] })).result.gates, ['gate-0'])
  for (const extra of [{ branch: undefined }, { git: 'shared' }, { git: 'task' }]) {
    const { result, calls } = await harness({ ...base, checkWave: '/k/scripts/check_wave.py', state: s, groups: [G('/r/a', ['m1.s1'], extra)] })
    assert.deepEqual(result.gates, ['gate-0'], JSON.stringify(extra))
    assert.equal(calls.length, 0)
  }
  const ok = await harness({ ...base, state: s, groups: [G('/r/a', ['m1.s1'], { from: 'bbb1111' })] })
  assert.match(ok.calls[0].prompt, /Commit each finished step on the current branch \(feature\/x\)/)
  assert.match(ok.calls[1].prompt, /git diff bbb1111/)
  assert.doesNotMatch(ok.calls[1].prompt, /check_wave\.py diff/)
  assert.equal(ok.result.groups[0].branch, 'feature/x')
})

const fixup = (k, extra = {}) => ({ kind: 'fixup', wave: 2, label: k === 1 ? '2-fix' : `2-fix${k}`, fix: k, tier: 'exec', milestone: 'm1', groups: ['repo-b m1 s3'], steps: [], start: false, ...extra })
const concern = (notes, source = 'review') => ({ wave: 2, group: 'repo-b m1 s3', count: notes.length, note: notes[notes.length - 1], notes, source, from: '846932b', to: '518e99f' })

test('a fix-up takes its groups, concern and range from the Review log', async () => {
  const s = st(fixup(1), [], { concerns: [concern(['gamma.txt lacks a newline'])] })
  const { result, calls } = await harness({ ...base, state: s, groups: [G('/r/repo-b', ['m1.s3'], { from: 'fffffff' })] })
  assert.equal(result.stop, 'done')
  assert.equal(calls[0].label, 'Wave 2-fix of 4 [exec] repo-b m1 s3')
  assert.match(calls[0].prompt, /## Fix-up 2-fix\n\nThe review of this group raised \(verbatim\):\n\n> gamma.txt lacks a newline/)
  assert.match(calls[0].prompt, /new commits whose subjects start with the step ID[\s\S]*Do not rewrite earlier commits/)
  assert.match(calls[1].prompt, /git diff 846932b/)
  assert.match(calls[1].prompt, /This is fix-up 2-fix[\s\S]*> gamma.txt lacks a newline/)
  assert.equal(result.groups[0].from, '846932b')
})

test('fix-up groups that do not match the CONCERNS groups are gate 0', async () => {
  const s = st({ kind: 'fixup', wave: 2, tier: 'exec', milestone: 'm1', groups: ['repo-b m1 s3'], steps: [], start: false }, [],
    { concerns: [{ wave: 2, group: 'repo-b m1 s3', count: 1, note: 'n', from: '846932b', to: '518e99f' }] })
  const { result } = await harness({ ...base, state: s, groups: [G('/r/repo-a', ['m1.s2'])] })
  assert.deepEqual(result.gates, ['gate-0'])
})

test('a worker that dies, or a review that dies, is gate 1', async () => {
  const s = st(unit(2, 'exec', ['m1.s2', 'm1.s3']))
  const g = [G('/r/a', ['m1.s2']), G('/r/b', ['m1.s3'])]
  assert.deepEqual((await harness({ ...base, state: s, groups: g }, { Wave: o => (o.label.endsWith('b m1 s3') ? null : DONE) })).result.gates, ['gate-1'])
  assert.deepEqual((await harness({ ...base, state: s, groups: g }, { Review: () => null })).result.gates, ['gate-1'])
})

test('low_quality is gate 1 and is not reviewed', async () => {
  const { result, calls } = await harness({ ...base, state: st(unit(1, 'fast', ['m1.s1'])), groups: [G('/r/a', ['m1.s1'])] }, { Wave: () => ({ ...DONE, status: 'low_quality' }) })
  assert.deepEqual(result.gates, ['gate-1'])
  assert.deepEqual(kinds(calls), ['Wave'])
})

test('CONCERNS is returned, not acted on: the parent logs it and plan_state schedules the fix-up', async () => {
  const { result } = await harness({ ...base, state: st(unit(2, 'exec', ['m1.s2'])), groups: [G('/r/a', ['m1.s2'])] }, { Review: () => ({ verdict: 'CONCERNS', note: 'bad', findings: [{ claim: 'c', evidence: 'e' }] }) })
  assert.equal(result.stop, 'done')
  assert.equal(result.groups[0].review.verdict, 'CONCERNS')
})

test('a finished plan ends without spawning', async () => {
  const { result, calls } = await harness({ ...base, state: st(null), groups: [] })
  assert.equal(result.stop, 'end')
  assert.equal(calls.length, 0)
})

test('the plugin name sets the agent namespace (Agerpoint port)', async () => {
  const { calls } = await harness({ ...base, plugin: 'agerpoint', state: st(unit(1, 'fast', ['m1.s1'])), groups: [G('/r/a', ['m1.s1'])] })
  assert.equal(calls[0].agentType, 'agerpoint:plan-worker')
})

// ---- v3: modes, checkpoints, automatic retries, questions ----

test('an unconfirmed mode spawns nothing, even with approvals', async () => {
  const s = st(unit(1, 'exec', ['m1.s1']), ['gate-mode'], { mode: null })
  const { result, calls } = await harness({ ...base, approval: 'yes', approved: [{ gate: 'gate-mode', wave: 1 }], state: s, groups: [G('/r/a', ['m1.s1'])] })
  assert.deepEqual(result.gates, ['gate-mode'])
  assert.equal(calls.length, 0)
})

test('unattended: checkpoint gates spawn without approvals and come back in the result', async () => {
  const { result, calls } = await harness({ ...base, state: un(unit(3, 'deep', ['m2.s1']), [], ['gate-4', 'gate-2']), groups: [G('/r/a', ['m2.s1'])] })
  assert.equal(result.stop, 'done')
  assert.equal(result.mode, 'unattended')
  assert.deepEqual(result.checkpoints, ['gate-4', 'gate-2'])
  assert.deepEqual(kinds(calls), ['Wave', 'Review'])
})

test('unattended: a stopping gate still needs its approval', async () => {
  const { result, calls } = await harness({ ...base, state: un(unit(4, 'xdeep', ['m2.s4']), ['gate-7']), groups: [G('/r/a', ['m2.s4'])] })
  assert.deepEqual(result.gates, ['gate-7'])
  assert.equal(calls.length, 0)
})

test('unattended: the canary runs one group and returns done with a gate-5 checkpoint', async () => {
  const { result, calls } = await harness({ ...base, canaryDone: false, state: un(unit(1, 'exec', ['m1.s1', 'm1.s2'])), groups: [G('/r/a', ['m1.s1']), G('/r/b', ['m1.s2'])] })
  assert.equal(result.stop, 'done')
  assert.deepEqual(result.checkpoints, ['gate-5'])
  assert.equal(result.groups.length, 1)
  assert.deepEqual(kinds(calls), ['Wave', 'Review'])
})

test('unattended: a worker that dies is retried once on the same tier', async () => {
  let n = 0
  const { result, calls } = await harness({ ...base, state: un(unit(2, 'exec', ['m1.s2'])), groups: [G('/r/a', ['m1.s2'])] }, { Wave: () => (n++ ? DONE : null) })
  assert.equal(result.stop, 'done')
  assert.deepEqual(kinds(calls), ['Wave', 'Wave', 'Review'])
  assert.equal(calls[1].label, 'Wave 2 of 4 [exec] a m1 s2 (retry)')
  assert.equal(calls[1].model, 'sonnet')
  assert.match(calls[1].prompt, /Earlier attempt[\s\S]*with no result/)
  assert.deepEqual(result.retries.map(r => [r.from, r.to]), [['exec', 'exec']])
  assert.deepEqual(result.checkpoints, [])
})

test('unattended: low_quality at [exec] steps up to Opus high once, logged as a gate-6 checkpoint', async () => {
  const { result, calls } = await harness({ ...base, state: un(unit(2, 'exec', ['m1.s2'])), groups: [G('/r/a', ['m1.s2'])] },
    { Wave: o => (o.model === 'sonnet' ? { ...DONE, status: 'low_quality', surprises: 'tests flaky' } : DONE) })
  assert.equal(result.stop, 'done')
  assert.deepEqual(calls.map(c => [c.label.split(' ')[0], c.model, c.effort]), [['Wave', 'sonnet', 'high'], ['Wave', 'opus', 'high'], ['Review', 'opus', 'high']])
  assert.match(calls[1].label, /^Wave 2 of 4 \[deep\] a m1 s2 \(retry\)$/)
  assert.deepEqual(result.checkpoints, ['gate-6'])
  assert.equal(result.groups[0].tier, 'deep')
})

test('unattended: a second failure stops at gate 1', async () => {
  const { result, calls } = await harness({ ...base, state: un(unit(1, 'fast', ['m1.s1'])), groups: [G('/r/a', ['m1.s1'])] }, { Wave: () => ({ ...DONE, status: 'failed' }) })
  assert.deepEqual(result.gates, ['gate-1'])
  assert.deepEqual(calls.map(c => c.model), ['haiku', 'sonnet'])
  assert.match(result.reason, /after one automatic retry/)
})

test('unattended: a failed [deep] wave never steps up into [xdeep] on its own', async () => {
  const { result, calls } = await harness({ ...base, state: un(unit(3, 'deep', ['m2.s1'])), groups: [G('/r/a', ['m2.s1'])] }, { Wave: () => ({ ...DONE, status: 'failed' }) })
  assert.deepEqual(result.gates, ['gate-1'])
  assert.equal(calls.length, 1)
})

test('unattended: an [xdeep] wave is never retried automatically, not even after a crash', async () => {
  const { result, calls } = await harness({ ...base, state: un(unit(4, 'xdeep', ['m2.s4']), [], ['gate-7']), groups: [G('/r/a', ['m2.s4'])] }, { Wave: () => null })
  assert.deepEqual(result.gates, ['gate-1'])
  assert.equal(calls.length, 1)
})

test('unattended: a review that dies reruns only the review', async () => {
  let n = 0
  const { result, calls } = await harness({ ...base, state: un(unit(2, 'exec', ['m1.s2'])), groups: [G('/r/a', ['m1.s2'])] }, { Review: () => (n++ ? { verdict: 'PASS', note: 'ok', findings: [] } : null) })
  assert.equal(result.stop, 'done')
  assert.deepEqual(kinds(calls), ['Wave', 'Review', 'Review'])
})

test('gated: no automatic retry; a failure is gate 1 as before', async () => {
  const { result, calls } = await harness({ ...base, state: st(unit(2, 'exec', ['m1.s2'])), groups: [G('/r/a', ['m1.s2'])] }, { Wave: () => null })
  assert.deepEqual(result.gates, ['gate-1'])
  assert.equal(calls.length, 1)
})

test('needs_info is a question at gate 1 in every mode, and is never retried', async () => {
  for (const s of [st(unit(2, 'exec', ['m1.s2'])), un(unit(2, 'exec', ['m1.s2']))]) {
    const { result, calls } = await harness({ ...base, state: s, groups: [G('/r/a', ['m1.s2'])] }, { Wave: () => ({ ...DONE, status: 'needs_info', question: 'Which registry token?' }) })
    assert.deepEqual(result.gates, ['gate-1'])
    assert.deepEqual(result.questions, [{ id: 'a m1 s2', question: 'Which registry token?' }])
    assert.equal(calls.length, 1)
    assert.match(calls[0].prompt, /return `needs_info` with one question/)
  }
})

test('the answer to a question rides into the worker prompt only as the verbatim approval', async () => {
  const s = st(unit(2, 'exec', ['m1.s2'], { start: false }), ['gate-1'], { blocked: 'gate-1' })
  const ans = { question: 'Which registry token?', answer: 'use NPM_TOKEN from the env' }
  const ok = await harness({ ...base, approval: 'use NPM_TOKEN  from the env', approved: [{ gate: 'gate-1', wave: 2 }], state: s, groups: [G('/r/a', ['m1.s2'], { answer: ans })] })
  assert.equal(ok.result.stop, 'done')
  assert.match(ok.calls[0].prompt, /Gary answered: use NPM_TOKEN from the env/)
  const forged = await harness({ ...base, approval: 'yes', approved: [{ gate: 'gate-1', wave: 2 }], state: s, groups: [G('/r/a', ['m1.s2'], { answer: ans })] })
  assert.deepEqual(forged.result.gates, ['gate-0'])
})

test('unattended: a human-approved step-up still needs gates 6 and 7, and gets no second automatic retry', async () => {
  const s = un(unit(4, 'xdeep', ['m2.s4'], { start: false }), ['gate-1'], [], { blocked: 'gate-1' })
  const one = await harness({ ...base, stepUp: 'fable', approval: 'try fable', approved: [{ gate: 'gate-1', wave: 4 }], state: s, groups: [G('/r/a', ['m2.s4'])] })
  assert.deepEqual(one.result.gates, ['gate-6', 'gate-7'])
  const s2 = un(unit(2, 'exec', ['m1.s2'], { start: false }), ['gate-1'], [], { blocked: 'gate-1' })
  const two = await harness({ ...base, stepUp: 'deep', approval: 'retry on opus', approved: ['gate-1', 'gate-6'].map(gate => ({ gate, wave: 2 })), state: s2, groups: [G('/r/a', ['m1.s2'])] }, { Wave: () => null })
  assert.deepEqual(two.result.gates, ['gate-1'])
  assert.equal(two.calls.length, 1)
})

test('unattended: draft fan-out needs a human gate-7 approval', async () => {
  const s = un(unit(4, 'xdeep', ['m2.s4']), [], ['gate-7'])
  const no = await harness({ ...base, xdeepDrafts: 3, state: s, groups: [G('/r/a', ['m2.s4'])] })
  assert.deepEqual(no.result.gates, ['gate-0'])
  const yes = await harness({ ...base, xdeepDrafts: 2, approval: 'yes, two drafts', approved: [{ gate: 'gate-7', wave: 4 }], state: s, groups: [G('/r/a', ['m2.s4'])] })
  assert.deepEqual(kinds(yes.calls), ['Draft', 'Draft', 'Judge', 'Wave', 'Review'])
})

// ---- v4: automatic fix-ups (unattended), fix-up numbering, outward actions ----

test('unattended: a check failure gets an automatic fix-up that quotes the check output', async () => {
  const note = 'check_wave.py: repo-b: 518e99f has a Co-authored-by line; repo-b: m1.s3 has no commit'
  const s = un(fixup(1), [], ['gate-1'], { concerns: [concern([note], 'check')] })
  const { result, calls } = await harness({ ...base, state: s, groups: [G('/r/repo-b', ['m1.s3'])] })
  assert.equal(result.stop, 'done')
  assert.deepEqual(result.checkpoints, ['gate-1'])
  assert.deepEqual(kinds(calls), ['Wave', 'Review'])
  assert.match(calls[0].prompt, /check_wave\.py\) failed on this group\. Their output \(verbatim\):\n\n> check_wave\.py: repo-b: 518e99f has a Co-authored-by line; repo-b: m1\.s3 has no commit/)
  assert.match(calls[0].prompt, /change only the messages of the commits the check names by SHA[\s\S]*every other commit in 846932b\.\.HEAD as it is, message included; some of them are the parent's plan and handoff commits/)
  assert.match(calls[0].prompt, /`git commit --amend` only when HEAD is one of the named commits[\s\S]*Do not push/)
  assert.doesNotMatch(calls[0].prompt, /review CONCERNS:/)
  assert.match(calls[1].prompt, /The last check_wave\.py run raised/)
  assert.match(calls[1].prompt, /that check failed, so check the failure quoted below yourself as well/)
  assert.doesNotMatch(calls[1].prompt, /leave those to it/)
})

test('a check failure logged with the review\'s CONCERNS gets both fixes: rewritten messages and new commits', async () => {
  const note = 'check_wave.py: repo-b: 518e99f lacks Assisted-by: Claude Code; review CONCERNS: gamma lacks a newline'
  const s = un(fixup(1), [], ['gate-1'], { concerns: [concern([note], 'check')] })
  const { calls } = await harness({ ...base, state: s, groups: [G('/r/repo-b', ['m1.s3'])] })
  assert.match(calls[0].prompt, /failed on this group, and its review raised CONCERNS/)
  assert.match(calls[0].prompt, /change only the messages of the commits the check names[\s\S]*The review's concern, after `review CONCERNS:` in that output, is fixed separately, as new commits whose subjects start with the step ID they fix; do not rewrite earlier commits for it/)
  assert.match(calls[1].prompt, /The last check_wave\.py run and review raised/)
})

test('a review fix-up still leaves the commit checks to the script', async () => {
  const s = st(fixup(1), [], { concerns: [concern(['gamma lacks a newline'])] })
  const { calls } = await harness({ ...base, state: s, groups: [G('/r/repo-b', ['m1.s3'])] })
  assert.match(calls[1].prompt, /paths after you; leave those to it/)
  assert.doesNotMatch(calls[0].prompt, /git commit --amend/)
})

test('unattended: a second CONCERNS gets fix-up 2, labeled N-fix2, with the streak quoted', async () => {
  const s = un(fixup(2), [], ['gate-1'], { concerns: [concern(['gamma lacks a newline', 'still no newline'])] })
  const { result, calls } = await harness({ ...base, state: s, groups: [G('/r/repo-b', ['m1.s3'])] })
  assert.equal(result.stop, 'done')
  assert.deepEqual(calls.map(c => c.label), ['Wave 2-fix2 of 4 [exec] repo-b m1 s3', 'Review Wave 2-fix2 of 4 [exec] repo-b m1 s3'])
  assert.match(calls[0].prompt, /## Fix-up 2-fix2\n\nThe review of this group raised \(verbatim\):\n\n> still no newline\n\nEarlier failures on this group, oldest first \(verbatim\):\n\n> gamma lacks a newline/)
  assert.match(calls[0].prompt, /\.scratch\/orchestrate-plan-x-2-fix2-repo-b-m1-s3\.md/)
})

test('a third failure is a stopping gate 1 that spawns nothing without an approval', async () => {
  const s = un(fixup(3), ['gate-1'], [], { concerns: [concern(['a', 'b', 'c'])] })
  const { result, calls } = await harness({ ...base, state: s, groups: [G('/r/repo-b', ['m1.s3'])] })
  assert.deepEqual(result.gates, ['gate-1'])
  assert.equal(calls.length, 0)
  const ok = await harness({ ...base, approval: 'try once more on opus', approved: [{ gate: 'gate-1', wave: 2 }], state: s, groups: [G('/r/repo-b', ['m1.s3'])] })
  assert.equal(ok.result.stop, 'done')
  assert.equal(ok.calls[0].label, 'Wave 2-fix3 of 4 [exec] repo-b m1 s3')
})

test('gated: a check failure or a second CONCERNS still stops at gate 1', async () => {
  for (const [k, src] of [[1, 'check'], [2, 'review']]) {
    const s = st(fixup(k), ['gate-1'], { concerns: [concern(k === 1 ? ['check_wave.py: m1.s3 has no commit'] : ['a', 'b'], src)] })
    const { result, calls } = await harness({ ...base, state: s, groups: [G('/r/repo-b', ['m1.s3'])] })
    assert.deepEqual(result.gates, ['gate-1'])
    assert.equal(calls.length, 0)
  }
})

test('an automatic fix-up still gets the in-run retry, and keeps its label', async () => {
  let n = 0
  const s = un(fixup(2), [], ['gate-1'], { concerns: [concern(['a', 'b'])] })
  const { result, calls } = await harness({ ...base, state: s, groups: [G('/r/repo-b', ['m1.s3'])] }, { Wave: () => (n++ ? DONE : null) })
  assert.equal(result.stop, 'done')
  assert.equal(calls[1].label, 'Wave 2-fix2 of 4 [exec] repo-b m1 s3 (retry)')
})

test('every prompt forbids outward actions, and a worker asks with needs_info instead', async () => {
  const { calls } = await harness({ ...base, xdeepDrafts: 2, approval: 'go', approved: [{ gate: 'gate-7', wave: 4 }], state: st(unit(4, 'xdeep', ['m2.s4']), ['gate-7']), groups: [G('/r/a', ['m2.s4'])] })
  for (const c of calls) assert.match(c.prompt, /open or merge a PR/, c.label)
  assert.match(calls.find(c => c.label.startsWith('Wave')).prompt, /If a step needs one, return `needs_info` naming it/)
})

let failed = 0
for (const [name, fn] of tests) {
  try { await fn(); console.log(`ok   ${name}`) } catch (e) { failed++; console.log(`FAIL ${name}\n     ${e.message}`) }
}
console.log(`${tests.length - failed}/${tests.length} passed`)
process.exit(failed ? 1 : 0)
