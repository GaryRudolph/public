# GARY-TOOLS(1) — User Manual

## NAME

**gary-tools** — frameworks and decision-making tools

## SYNOPSIS

```
gary tools [--blanchard] [--pugh]
```

## OPTIONS

**--blanchard**
: Blanchard Situational Leadership — this a hammer and can be used everywhere. Maps development
  levels (D1–D4) to leadership styles (S1–S4). Self-assessment example: *"I'm a D2 at our
  domain but a D4 at my skill (Software Leadership)."* Pairs with software engineering levels
  to calibrate how to lead individuals.

**--pugh**
: [Pugh Matrix](sample-pugh.xlsx) with a QFD (Quality Function Deployment) scale — a
  decision-making framework that scores options against weighted criteria using the classic
  1-3-9 relationship scale from QFD / House of Quality, to force meaningful differentiation
  between options rather than treating everything as equally important. Rule: the matrix must
  use a roughly even number of 1s, 3s, and 9s for both the criteria *weights* and the
  per-option *scores* — this forces real differentiation instead of everyone defaulting to 9s.
  When weights and scores are compounded (weight × score, summed per option), the true
  standouts pop to the top. Great for software vendor evaluations or any decision matrix where
  you need to defend a choice.

## SEE ALSO

[gary(1)](../user-manual.md), [gary-leadership(1)](leadership.md), [gary-operating(1)](operating.md), [gary-communication(1)](communication.md), [sample-pugh.xlsx](sample-pugh.xlsx)