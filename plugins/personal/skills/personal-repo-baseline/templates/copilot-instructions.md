# Code review

When reviewing a pull request:

- Start every comment with one label: `blocking:` (must change before
  merge), `suggestion:` (better, not required), `nit:` (style, naming,
  wording) or `question:`.
- A `blocking:` comment names the trigger, the inputs or state that happen
  in real use of this code today, and what breaks. A scenario no caller
  reaches yet ("if a future change sets it") is a `suggestion:` at most.
- Skip findings that need a hostile caller of an internal tool, a malformed
  file the code itself writes, or concurrency a single-user tool doesn't
  have, unless they're security issues.
- Security issues are always `blocking:`.
- The PR description's review guide tags each area `[study]`, `[check]`,
  `[skim]` or `[skip]`. Spend your attention in that order, and flag an
  area whose code doesn't match its tag.
