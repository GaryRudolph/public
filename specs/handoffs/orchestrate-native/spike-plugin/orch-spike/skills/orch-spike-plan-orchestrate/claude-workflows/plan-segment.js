export const meta = {
  name: 'plan-segment',
  description: 'Run one dispatch unit of a tagged plan for orch-spike-plan-orchestrate: one wave, every working directory executed and then reviewed',
  whenToUse: 'Only when the orch-spike-plan-orchestrate skill launches it with plan_state.py output and the contracts for that unit',
}

// One run = one dispatch unit (a wave, or the part of a wave inside one
// milestone). plan_state.py computes the unit, the gates in front of it, and
// which of them stop in the plan's recorded mode; the PreToolUse hook re-runs
// it from disk, checks approval text against the human's prompt, and checks an
// unattended mode against the human turn that confirmed it. This script
// refuses to spawn anything unless every stopping gate is approved for this
// wave, then runs and reviews each working directory and returns. In
// unattended mode the other gates are checkpoints: logged in the result, not
// asked, and a broken group gets one automatic retry below [xdeep]. A fix-up
// unit (N-fix, N-fix2, ...) quotes the failed check or the review concern from
// the Review log into its worker prompt; plan_state.py decides whether its
// gate 1 stops. It never decides to continue: the parent records the result,
// runs check_wave.py, commits the plan and handoff, and launches the next run.

// Tier routing. Must match plan-execution.md's Claude Code picker row and the
// -xdeep agents' frontmatter (orchestrate_check.py checks both).
const ROUTE = {
  fast: { model: 'haiku' },
  exec: { model: 'sonnet', effort: 'high' },
  deep: { model: 'opus', effort: 'high' },
  xdeep: { model: 'opus', effort: 'xhigh' },
  fable: { model: 'fable', effort: 'xhigh' },
}
const CHAIN = ['fast', 'exec', 'deep', 'xdeep', 'fable']
const PREMIUM = { xdeep: true, fable: true }  // the tiers on the -xdeep agents
const ANGLES = [
  'the simplest design that fully satisfies the spec',
  'risk first: list the failure modes, then design to rule each one out',
  'adversarial: assume a hostile input or caller, then design so it cannot succeed',
  'reuse first: the closest existing pattern in the repo, the standards, or the dependencies',
]

const RESULT = { type: 'object', required: ['status', 'changed', 'decided', 'surprises', 'artifact', 'commits'], properties: {
  status: { type: 'string', enum: ['done', 'failed', 'low_quality', 'needs_info'] }, changed: { type: 'string' }, decided: { type: 'string' },
  surprises: { type: 'string' }, artifact: { type: 'string' }, commits: { type: 'array', items: { type: 'string' } },
  question: { type: 'string' } } }
const REVIEW = { type: 'object', required: ['verdict', 'note', 'findings'], properties: {
  verdict: { type: 'string', enum: ['PASS', 'CONCERNS'] }, note: { type: 'string' },
  findings: { type: 'array', items: { type: 'object', required: ['claim', 'evidence'], properties: { claim: { type: 'string' }, evidence: { type: 'string' } } } } } }
const DRAFT = { type: 'object', required: ['design', 'risks'], properties: { design: { type: 'string' }, risks: { type: 'string' } } }
const JUDGE = { type: 'object', required: ['pick', 'synthesis'], properties: { pick: { type: 'integer' }, synthesis: { type: 'string' } } }

const S = args && args.state
const U = S && S.next
const tier = (args && args.stepUp) || (U && U.tier)
const P = args && args.plugin
const unattended = !!(S && S.mode && S.mode.value === 'unattended')
const NEVER_APPROVED = ['gate-0', 'gate-mode']  // cleared only by fixing the plan or recording the kickoff answer
// The standard's one effort step-up, set per launch: max runs an [xdeep] or Fable worker at max (a task type with a
// measured gain). Reviews, drafts and judges keep the tier's effort. [exec] has none: it runs at high and never past
// it, so a stalled [exec] step re-tags to [deep] (stepUp, or the unattended retry below).
function route(t) { return PREMIUM[t] && args.max ? { ...ROUTE[t], effort: 'max' } : ROUTE[t] }
function worker(t = tier) { return { agentType: `${P}:plan-worker${PREMIUM[t] ? '-xdeep' : ''}`, ...route(t) } }
function reader(t = tier) { return PREMIUM[t] ? { agentType: `${P}:plan-reviewer-xdeep`, ...ROUTE.xdeep } : { agentType: `${P}:plan-reviewer`, ...ROUTE.deep } }
function norm(x) { return String(x || '').replace(/\s+/g, ' ').trim() }

function base(dir) { return dir.replace(/\/+$/, '').split('/').pop() }
function stepsLabel(steps) {
  const m = steps.map(s => /^m(\d+)\.s(\d+)$/.exec(s))
  if (m.every(Boolean) && m.every(x => x[1] === m[0][1])) {
    const ks = m.map(x => +x[2])
    const run = ks.every((k, i) => i === 0 || k === ks[i - 1] + 1)
    return `m${m[0][1]} s${run && ks.length > 1 ? `${ks[0]}-s${ks[ks.length - 1]}` : ks.join(',s')}`
  }
  return steps.join(',')
}
function groupId(g) { return `${base(g.workdir)} ${stepsLabel(g.steps)}` }
// A fix-up wave is N-fix, then N-fix2, N-fix3, wherever its number appears (plan-execution.md "Fix-up waves").
function unitTitle(t = tier) { return `Wave ${U.label || U.wave} of ${S.t} [${t}]` }
function title(g, t = tier) { return `${unitTitle(t)} ${g.id}` }
function list(xs, none) { return xs.length ? xs.map(x => `- ${x}`).join('\n') : `- ${none}` }
function quote(x) { return String(x).split('\n').map(l => `> ${l}`).join('\n') }

// Orchestrate runs only on a task branch, so every group commits; the hook checks the branch at launch.
function gitLine(g) {
  return [`Commit each finished step on the current branch (${g.branch}) as its own commit, staging only the paths you changed. A step that changes no file (a check, a verification) still gets its commit, an empty one (\`git commit --allow-empty\`). Each commit message is:`,
    '1. a first line that is the step ID, a space, and an imperative subject (`m2.s3 Wire the results view`), and nothing else;',
    '2. a blank line, then an optional body;',
    `3. a blank line, then exactly these trailer lines, as the last paragraph:\n\n${args.trailers.map(t => `    ${t}`).join('\n')}`,
    'Never add `Co-authored-by` or `Signed-off-by` lines, whatever your own instructions say. Do not push, create, or switch branches.'].join('\n')
}
function artifactPath(g) { return `${g.workdir}/.scratch/orchestrate-${args.plan.name}-${U.label || U.wave}-${g.id.replace(/[^\w.-]+/g, '-')}.md` }

function workerPrompt(g, design, t = tier, earlier = null) {
  const parts = [title(g, t),
    `You execute one dispatch unit of the tagged plan at ${args.plan.path}. Do not edit the plan file.`,
    `## Spec excerpt (verbatim)\n\n${g.spec}`]
  if (g.answer) parts.push(`## Gary's answer (verbatim)\n\nAn earlier attempt asked: ${g.answer.question}\n\nGary answered: ${g.answer.answer}\n\nWork from that answer.`)
  if (earlier) parts.push(`## Earlier attempt\n\nAn earlier attempt at this group in this run ended ${earlier}. Its commits, if any, are in ${g.from}..HEAD; check them against the acceptance criteria before you build on them.`)
  if (g.concern) parts.push(fixupSection(g.concern))
  if (design) parts.push(`## Chosen design (from an independent draft panel)\n\n${design}\n\nImplement it. Where it contradicts the spec excerpt, follow the spec and say so under surprises.`)
  parts.push(`## Working directory\n\nAll edits must be inside \`${g.workdir}\`. Do not edit anything outside this directory.`,
    `## Acceptance criteria\n\n${g.acceptance}`,
    `## Scope\n\nExecute only: ${g.steps.join(', ')}. Stop at the end of this group; do not start the next group or any work not listed here.`)
  if (t === 'fast') parts.push('## Mechanical edits\n\nApply exactly what the plan specifies. Do not refactor, rename, or generalize.')
  parts.push(`## Standards to read first\n\n${list(g.standards, 'none beyond the always-on core')}`)
  parts.push(`## Before you start\n\nRun \`git -C ${g.workdir} log --format=%s ${g.from}..HEAD\`. A step that already has a commit whose subject starts with its ID was done by an earlier attempt: check that commit against the acceptance criteria and skip the step if it holds. If a file you need to change already has uncommitted changes, do not touch it: return \`failed\` and name the file.`)
  parts.push('## When to ask\n\nIf the spec reads two ways that lead to materially different results, or you lack an access, credential or tool the step needs, stop: return `needs_info` with one question in `question`. Do not guess, and do not work around missing access.\n\nDo not open or merge a PR, push a tag, delete a remote branch, or deploy. If a step needs one, return `needs_info` naming it.',
    `## Output\n\nWrite your full output (diffs, decisions, surprises, follow-ups) to \`${artifactPath(g)}\`. Return the structured result: status, what changed, what was decided, any surprises, the artifact path, and the short SHA of every commit you made. Use \`failed\` or \`low_quality\` when you could not meet the acceptance criteria; never report partial work as \`done\`.`,
    `## Git\n\n${gitLine(g)}`)
  return parts.join('\n\n')
}
// The failure is quoted verbatim from the Review log. A failed check may need this group's own commit
// messages rewritten (a subject, a trailer); a review concern is fixed with new commits only. A check
// note that also carries the review's CONCERNS gets both instructions.
function withReview(c) { return c.source === 'check' && /; review CONCERNS:/.test(c.note || '') }
function fixupSection(c) {
  const what = c.source === 'check'
    ? `The commit and scope checks (check_wave.py) failed on this group${withReview(c) ? ', and its review raised CONCERNS' : ''}. Their output (verbatim):`
    : 'The review of this group raised (verbatim):'
  const before = (c.notes || []).slice(0, -1)
  const how = c.source === 'check'
    ? `Fix only that. A step with no commit gets its commit, an empty one (\`git commit --allow-empty\`) when the step changes no file. A new uncommitted path your group's work made is committed under its step, or deleted if it is a by-product (a build output, a temp file), the one case where you touch a path that already has uncommitted changes; leave any path you did not make alone and name it under surprises. A commit message the check rejects (its first line, a Co-authored-by or Signed-off-by line, a missing trailer) is rewritten: change only the messages of the commits the check names by SHA, keep each commit's content, and keep the message and content of every other commit in ${c.from}..HEAD; some of them are the parent's plan and handoff commits. Use \`git commit --amend\` only when HEAD is one of the named commits; otherwise reword just those commits with a \`git rebase\` onto ${c.from}, run non-interactively (set GIT_SEQUENCE_EDITOR and GIT_EDITOR to commands). The rebase replays the commits after them with new SHAs, the parent's included: that is expected, and the parent force-pushes with a lease. List the rewritten commits under surprises. Do not push.${withReview(c) ? `\n\nThe review's concern, after \`review CONCERNS:\` in that output, is fixed separately, as new commits whose subjects start with the step ID they fix; do not rewrite earlier commits for it.` : ''}`
    : 'Fix only that. Make the fix as new commits whose subjects start with the step ID they fix. Do not rewrite earlier commits.'
  return [`## Fix-up ${U.label}`, `${what}\n\n${quote(c.note)}`,
    before.length ? `Earlier failures on this group, oldest first (verbatim):\n\n${before.map(quote).join('\n\n')}` : '',
    how].filter(Boolean).join('\n\n')
}
function changes(g) { return `read \`git diff ${g.from}\`, \`git log ${g.from}..HEAD\` and \`git status\`` }
function reviewPrompt(g, r, t = tier) {
  return [`Review ${title(g, t)}. READ-ONLY: do not edit files, commit, push, open or merge a PR, tag, deploy, or start other work.`,
    `In \`${g.workdir}\`, ${changes(g)}, then the worker's artifact \`${r.artifact}\`. Check the change against the spec excerpt, the acceptance criteria and the standards below: does it do what they ask, no more and no less, correctly, with tests where the repo expects them?`,
    `${g.concern && g.concern.source === 'check' ? 'A script checks commit subjects, trailers, step coverage and paths after you. This fix-up exists because that check failed, so check the failure quoted below yourself as well.' : 'A script checks commit subjects, trailers, step coverage and paths after you; leave those to it.'} List only defects the change must fix before the plan builds on it, each with evidence (a file and line, a command and its output, or a quoted spec line). Checks that passed go in the note. Return PASS with no findings when you find nothing real.`,
    `## Spec excerpt (verbatim)\n\n${g.spec}`, `## Acceptance criteria\n\n${g.acceptance}`, `## Standards\n\n${list(g.standards, 'the always-on core')}`,
    g.concern ? `## This is fix-up ${U.label}\n\nThe last ${g.concern.source === 'check' ? (withReview(g.concern) ? 'check_wave.py run and review' : 'check_wave.py run') : 'review'} raised (verbatim):\n\n${quote(g.concern.note)}\n\nCheck that it is fixed, and review the whole range.` : '',
    `## Worker summary\n\nChanged: ${r.changed}\nDecided: ${r.decided}\nSurprises: ${r.surprises}\nCommits: ${r.commits.join(', ') || 'none'}`].filter(Boolean).join('\n\n')
}
function draftPrompt(g, angle) {
  return [`Draft for ${title(g)}. READ-ONLY: do not edit files, commit, push, open or merge a PR, tag, deploy, or run anything else that changes state.`,
    `Design how to carry out the steps below in \`${g.workdir}\`, from this angle: ${angle}. Read the code you need. Return a design an implementer can follow, and the risks it leaves open.`,
    `## Spec excerpt (verbatim)\n\n${g.spec}`, `## Acceptance criteria\n\n${g.acceptance}`, `## Steps\n\n${g.steps.join(', ')}`].join('\n\n')
}
function judgePrompt(g, drafts) {
  return [`Judge for ${title(g)}. READ-ONLY: do not edit files, commit, push, open or merge a PR, tag, or deploy.`,
    `Check each independent draft below against the spec and the code in \`${g.workdir}\`. Pick the strongest (1-based \`pick\`), then write a synthesis that keeps the winner, grafts in the best ideas from the others, and resolves or names every open risk.`,
    `## Spec excerpt (verbatim)\n\n${g.spec}`, `## Acceptance criteria\n\n${g.acceptance}`,
    drafts.map((d, i) => `### Draft ${i + 1}\n\n${d.design}\n\nRisks: ${d.risks}`).join('\n\n')].join('\n\n')
}

function gate(gates, reason, extra) { return { stop: 'gate', gates, reason, unit: U || null, tier: tier || null, mode: unattended ? 'unattended' : 'gated', checkpoints: [], groups: [], ...extra } }

function validate() {
  const e = []
  if (!args || typeof args !== 'object') return ['args missing']
  if (!/^[a-z][a-z0-9-]*$/.test(P || '')) e.push('args.plugin must be the plugin name')
  if (!args.plan || !args.plan.name || !/^\//.test(args.plan.path || '')) e.push('args.plan needs name and an absolute path')
  if (!S || S.version !== 3) e.push('args.state must be plan_state.py output (version 3)')
  if (S && S.errors && S.errors.length) e.push(...S.errors.map(x => `plan: ${x}`))
  if (e.length || !U) return e
  if (!ROUTE[U.tier]) e.push(`unknown tier ${U.tier}`)
  if (args.stepUp && !(CHAIN.indexOf(args.stepUp) > CHAIN.indexOf(U.tier))) e.push(`stepUp ${args.stepUp} is not above [${U.tier}]`)
  if (args.max && !PREMIUM[tier]) e.push(`max is only for an [xdeep] or Fable dispatch, on a task type with a measured gain, not [${tier}]`)
  const d = args.xdeepDrafts || 0
  if (d && (!PREMIUM[tier] || d < 2 || d > ANGLES.length)) e.push(`xdeepDrafts ${d}: only 2..${ANGLES.length}, and only on an [xdeep] or Fable dispatch`)
  const gate7 = (args.approved || []).some(a => a && a.gate === 'gate-7' && a.wave === U.wave)
  if (d && unattended && !gate7) e.push('xdeepDrafts in unattended mode needs a human gate-7 approval for this wave')
  if (args.max && unattended && !gate7) e.push('max in unattended mode needs a human gate-7 approval for this wave')
  const ap = args.approved || []
  if (!Array.isArray(ap) || ap.some(a => !a || typeof a.gate !== 'string' || typeof a.wave !== 'number')) e.push('approved must be [{gate, wave}]')
  else if (ap.length && !(args.approval || '').trim()) e.push('approved is set but approval (the human answer, verbatim) is empty')
  const gs = args.groups
  if (!Array.isArray(gs) || !gs.length) return e.concat('args.groups is empty')
  const dirs = new Set()
  for (const g of gs) {
    const at = g.workdir || '?'
    for (const k of ['workdir', 'spec', 'acceptance', 'from']) if (!g[k] || typeof g[k] !== 'string') e.push(`${at}: missing ${k}`)
    if (!Array.isArray(g.steps) || !g.steps.length) e.push(`${at}: no steps`)
    if (!Array.isArray(g.standards)) e.push(`${at}: standards must be a list`)
    if (g.workdir && (!g.workdir.startsWith('/') || g.workdir.split('/').includes('..'))) e.push(`${at}: workdir must be absolute`)
    if (g.from && !/^[0-9a-f]{7,40}$/.test(g.from)) e.push(`${at}: from must be a commit SHA`)
    if (!g.branch || typeof g.branch !== 'string') e.push(`${at}: missing branch, the task branch the group commits on`)
    if ('git' in g) e.push(`${at}: there is no git mode; every group commits on its task branch`)
    if (dirs.has(g.workdir)) e.push(`two groups share ${g.workdir}; one subagent per working directory`)
    if (g.answer && (!g.answer.question || norm(g.answer.answer) !== norm(args.approval))) e.push(`${at}: answer must quote the question and carry the human answer verbatim, as approval does`)
    dirs.add(g.workdir)
  }
  const t = args.trailers
  if (!Array.isArray(t) || !t.length || t.some(x => typeof x !== 'string' || /^(co-authored-by|signed-off-by):/i.test(x) || !/^[\w-]+: \S/.test(x))) {
    e.push('trailers must list the harness trailer lines, such as "Assisted-by: Claude Code", and never Co-authored-by or Signed-off-by')
  }
  if (e.length) return e
  if (U.kind === 'fixup') {
    const want = [...U.groups].sort().join(' | ')
    const got = gs.map(groupId).sort().join(' | ')
    if (want !== got) e.push(`fix-up groups ${got} do not match the Review log's CONCERNS groups ${want}`)
  } else {
    const all = gs.flatMap(g => g.steps)
    const want = [...U.steps].sort().join(',')
    if (new Set(all).size !== all.length || [...all].sort().join(',') !== want) e.push(`groups cover steps ${all.join(',')}; this unit is ${U.steps.join(',')}`)
  }
  return e
}

// ---- run ----
const errors = validate()
if (errors.length) return gate(['gate-0'], errors.join('; '))
if (!U) return { stop: 'end', gates: [], reason: 'plan complete', unit: null, tier: null, mode: unattended ? 'unattended' : 'gated', checkpoints: [], groups: [] }

const hard = S.stops.filter(g => NEVER_APPROVED.includes(g))
if (hard.length) return gate(hard, hard.includes('gate-mode') ? 'the kickoff question has no recorded answer' : 'the plan has errors')
// Every gate derives from the plan; the mode only says which ones stop.
const required = [...S.stops]
const checkpoints = [...S.checkpoints]
if (args.stepUp) required.push('gate-6')  // a step-up across runs always follows a human answer
if (args.stepUp && PREMIUM[args.stepUp]) required.push('gate-7')
const approved = (args.approved || []).filter(a => a.wave === U.wave).map(a => a.gate)
const stale = (args.approved || []).filter(a => a.wave !== U.wave)
if (stale.length) log(`Ignoring approvals for other waves: ${stale.map(a => `${a.gate}@${a.wave}`).join(', ')}`)
const missing = [...new Set(required)].filter(g => !approved.includes(g))
if (missing.length) return gate(missing, `wave ${U.label || U.wave} [${tier}] needs ${missing.join(', ')} approved`)
if (checkpoints.length) log(`Unattended checkpoints: ${checkpoints.join(', ')}`)

const concernOf = id => (S.concerns.find(c => c.wave === U.wave && c.group === id) || {})
let groups = args.groups.map(g => {
  const id = groupId(g)
  const c = U.kind === 'fixup' ? concernOf(id) : {}
  return { ...g, id, concern: c.note ? c : null, from: c.from || g.from }
})
const canary = !args.canaryDone
if (canary && groups.length > 1) {
  log(`Canary: running ${groups[0].id} only; ${groups.length - 1} group(s) wait for the gate-5 answer`)
  groups = groups.slice(0, 1)
}

const ph = unitTitle()
phase(ph)
async function execute(g) {
  const drafts = args.xdeepDrafts || 0
  let design = null
  if (drafts) {
    const ds = (await parallel(ANGLES.slice(0, drafts).map((a, i) => () =>
      agent(draftPrompt(g, a), { label: `Draft ${i + 1} ${title(g)}`, phase: ph, schema: DRAFT, ...reader() })))).filter(Boolean)
    if (ds.length < 2) return null
    const j = await agent(judgePrompt(g, ds), { label: `Judge ${title(g)}`, phase: ph, schema: JUDGE, ...reader() })
    if (!j) return null
    design = j.synthesis
  }
  return agent(workerPrompt(g, design), { label: title(g), phase: ph, schema: RESULT, ...worker() })
}
function review(g, work, t = tier) {
  return agent(reviewPrompt(g, work, t), { label: `Review ${title(g, t)}`, phase: ph, schema: REVIEW, ...reader(t) })
}
const runs = await pipeline(groups,
  g => execute(g),
  (work, g) => (work && work.status === 'done' ? review(g, work).then(r => ({ work, review: r })) : { work, review: null }))

let out = groups.map((g, i) => ({ id: g.id, workdir: g.workdir, steps: g.steps, from: g.from, branch: g.branch, tier,
  work: (runs[i] && runs[i].work) || null, review: (runs[i] && runs[i].review) || null }))
const isBroken = x => !x.work || x.work.status !== 'done' || !x.review

// Unattended only: one automatic retry per broken group, never at [xdeep] or Fable, never on a launch that is
// already a human-approved step-up, never for needs_info. A crash or a missing review retries on the same tier;
// failed or low_quality steps up one tier, into [exec] or [deep] only (gate 6 becomes a checkpoint), so a stalled
// [exec] group re-tags to [deep].
function retryTier(x) {
  if (!unattended || args.stepUp || PREMIUM[tier]) return null
  if (x.work && x.work.status === 'needs_info') return null
  if (!x.work || x.work.status === 'done') return tier
  const up = CHAIN[CHAIN.indexOf(tier) + 1]
  return up === 'exec' || up === 'deep' ? up : null
}
const retries = []
const again = out.filter(isBroken).map(x => ({ x, t: retryTier(x) })).filter(r => r.t)
if (again.length) {
  const redo = await parallel(again.map(({ x, t }) => async () => {
    const g = groups.find(y => y.id === x.id)
    const why = !x.work ? 'with no result' : x.work.status === 'done' ? 'with its review missing' : `as ${x.work.status}: ${x.work.surprises}`
    retries.push({ id: x.id, from: tier, to: t, effort: route(t).effort || null, reason: why })
    const work = x.work && x.work.status === 'done' ? x.work
      : await agent(workerPrompt(g, null, t, why), { label: `${title(g, t)} (retry)`, phase: ph, schema: RESULT, ...worker(t) })
    const r = work && work.status === 'done' ? await review(g, work, t) : null
    return { ...x, tier: t, work: work || null, review: r || null }
  }))
  out = out.map(x => (redo.find(y => y && y.id === x.id) || x))
  if (again.some(r => r.t !== tier)) checkpoints.push('gate-6')
}

const broken = out.filter(isBroken)
const questions = out.filter(x => x.work && x.work.status === 'needs_info').map(x => ({ id: x.id, question: x.work.question || x.work.surprises }))
const extra = { groups: out, canary, checkpoints, retries, questions }
if (broken.length) {
  const why = `${broken.map(x => x.id).join(', ')}: ${questions.length ? 'needs an answer, or ' : ''}failed, low quality, or unreviewed${retries.length ? ' after one automatic retry' : ''}`
  return gate(canary && !unattended ? ['gate-1', 'gate-5'] : ['gate-1'], why, extra)
}
if (canary && !unattended) return gate(['gate-5'], 'first-subagent canary', extra)
if (canary) checkpoints.push('gate-5')  // unattended: the parent continues once check_wave.py passes too
return { stop: 'done', gates: [], reason: `wave ${U.label || U.wave} reviewed`, unit: U, tier, mode: unattended ? 'unattended' : 'gated', ...extra }
