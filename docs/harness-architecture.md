# Ripperdoc as a harness component: architecture plan

Status: proposal, for review. Nothing here is implemented yet.
Date: 2026-11-20

## 1. What "harness engineering" means here

"Harness engineering" is the established name for designing everything that surrounds a
model in an agent: the tools it can call, its permissions and sandbox, what goes into its
context, the hooks and stop conditions that decide when it is done, the verification loops
that check its work, and the evals that tell you whether a change to any of that made it
better or worse. The model is the engine; the harness is the rest of the car.

Ripperdoc is already a piece of harness. It is a *verifier*: a separate-context agent with a
read-only guard, a sandbox, a schema, a validator and a planted-flaw eval set. What it is not
yet is *reusable*: it is wired to one workflow (`experiment-review` after a research run), its
rubric mixes general rules with research-specific ones, and its eval set is a loose script
rather than a benchmark that gates changes.

The plan turns it into three things, in this order:

1. **A verification gate.** Any agent's output (an analysis, a code change, a paper section)
   passes through Ripperdoc before it counts as done. Wired in through Claude Code hooks, CI,
   or the Agent SDK.
2. **A domain-agnostic core with pluggable domain packs.** The trace / recompute / rerun ladder,
   verdict rules, validator, criteria provenance and the dual-reviewer merge stay in the core.
   What "trace to the equation" means in physics, ML or software lives in a pack.
3. **The eval set as a harness benchmark.** Run on every change to the prompt, the tools, a
   pack, the guard or the model, with a stored baseline and a regression rule.

What does not change: Ripperdoc stays a judge, not a re-runner. Tracing is the default;
recomputes stay under 5 minutes; a rerun happens only when a human granted it with a time
budget. Tests are mandatory for every milestone.

## 2. Where Ripperdoc stands today (harness view)

| Harness concern | What exists | Gap for reuse |
|---|---|---|
| Separate context | `agents/ripperdoc.md` subagent, fresh context | none |
| Permissions | `hooks/guard.py` (writes only in `ripperdoc_reviews/`, all Bash through `sandbox-run`) | nothing stops the *producer* from writing in `ripperdoc_reviews/` and forging an accept |
| Sandbox | `bin/sandbox-run` (bwrap / sandbox-exec) | untested on real bwrap and macOS |
| Output contract | `schema/review.schema.json` + `bin/validate.py` | no gate decision derived from it; reviews are not tied to the artifact version they reviewed |
| Stop condition | loop mode (round cap 3, keep/revert, no-progress stop) | lives in prose; no hook enforces "not done until reviewed" |
| Ensemble | `bin/merge_reviews.py`, union of blocking issues | none |
| Domain knowledge | Appendix A rubric in `SKILL.md` | general and research-specific items mixed; physics/ML trace targets implicit |
| Evals | 10 cases, `answers.json`, `run.sh`, `score.py` | never run; no baseline, no repeats, no cost tracking, research-only cases |
| CI | unit tests on push | benchmark not wired anywhere |

## 3. Target architecture

```
                 ┌────────────────────────── producer agent ──────────────────────────┐
                 │ does the work; declares a claim when it thinks it is done          │
                 │ (producer guard: may not write ripperdoc_reviews/ or the policy)   │
                 └──────────────┬─────────────────────────────────────────────────────┘
                                │ claim manifest (.ripperdoc/claims/<slug>.json)
                                ▼
   ┌──────────── adapters ────────────┐      ┌────────────── gate ──────────────┐
   │ Claude Code Stop/SubagentStop    │─────▶│ bin/ripperdoc-gate               │
   │ GitHub Action (PR check)         │      │  1. hash artifacts               │
   │ Agent SDK callback / CLI         │◀─────│  2. reuse a fresh review or run  │
   └──────────────────────────────────┘      │     the reviewer(s)              │
            pass / block + actions /          │  3. validate, apply policy       │
            escalate to human                 │  4. decision + exit code         │
                                              └──────────────┬───────────────────┘
                                                             │ runs
                                    ┌────────────────────────▼─────────────────────────┐
                                    │ core reviewer (SKILL.md core, guard, sandbox,    │
                                    │ ladder, validator, ensemble merge, loop mode)    │
                                    │      + domain packs (physics, ml, software, ...) │
                                    └────────────────────────┬─────────────────────────┘
                                                             │ measured by
                                    ┌────────────────────────▼─────────────────────────┐
                                    │ benchmark: cases per pack, answer keys, scorer,  │
                                    │ baselines, regression rule                       │
                                    └──────────────────────────────────────────────────┘
```

### 3.1 Core (domain-agnostic)

Stays in `SKILL.md`, trimmed to what holds in every domain:

- ground rules, verification ladder, safe-execution protocol, verdict and confidence rules,
  feedback format, loop mode, ensemble mode, output format;
- the **Core** rubric section of Appendix A (answers the ask, verifiable evidence, hidden
  assumptions, edge cases, contradictions, consistent with the record, falsifiability, claim
  strength) and the general **Statistics** items;
- `guard.py`, `sandbox-run`, `validate.py`, `merge_reviews.py`, the schemas.

New in the core: a short **Packs** step after Intake: "load the packs the gate selected; their
checklist items join the rubric, their trace targets tell you what the 'equation' is in this
domain".

### 3.2 Domain packs

A pack is a folder, read by the reviewer like `SKILL.md` and by tooling through a manifest:

```
packs/
  research-core/   # experiment design + statistics items that are research-wide (moved from Appendix A)
  physics/
  ml/
  software/
    pack.json
    checklist.md
    cases/        -> symlink or pointer into evals/cases/software/
```

`pack.json`:

```json
{
  "id": "physics",
  "version": "1.0.0",
  "applies_when": {"globs": ["**/*.py", "**/*.ipynb"], "keywords": ["spectrum", "PSD", "Hamiltonian"]},
  "extends": ["research-core"],
  "checklist": "checklist.md",
  "trace_targets": "what counts as the 'equation' here",
  "recompute_recipes": ["Parseval check on a saved PSD", "unit conversion of one number"],
  "eval_cases": ["case01", "case02", "case03", "case07", "case08"]
}
```

`checklist.md` holds items with stable ids, each written as a question plus what a trace
would look at, for example `physics.normalisation`, `physics.units`, `physics.jacobian`,
`ml.split-leakage`, `ml.seed-selection`, `ml.metric-definition`, `software.claim-vs-test`,
`software.benchmark-method`.

What the "equation" is, per domain:

| Pack | Trace a number to... | Typical recompute | Typical rerun (permission only) |
|---|---|---|---|
| physics | the formula in code vs. derivation or cited paper: normalisation, units, signs, Jacobians | Parseval, a conversion, a fit on saved arrays | a simulation |
| ml | the metric definition, the split, the selection of reported runs, the baseline config | mean and spread over saved per-seed results | training, full evaluation |
| software | the test, spec or contract that is claimed to hold; the benchmark harness behind a perf number | rerun one focused unit test in the sandbox | full test suite, benchmark |

Schema change (additive, minor): issues and verifications get an optional `checklist_item`
(pack-qualified id) and the review gets `packs: [{id, version}]`. The category enum stays as
it is, so old reviews stay valid. The validator checks that a `checklist_item` names a loaded
pack.

Pack selection: the caller or policy names packs explicitly; otherwise the gate proposes them
from `applies_when` and records the choice in `intake`. A review always has `research-core`
or `software` plus zero or more specialised packs.

The software pack must not turn Ripperdoc into a second `/code-review`. Its job is the same as
in research: judge a *claim* ("fixes #12", "30% faster", "all tests pass") against evidence,
and decide which code-review findings change that claim.

### 3.3 The gate

`bin/ripperdoc-gate` (Python, stdlib only, like the rest of `bin/`):

```
ripperdoc-gate check  <claim manifest>   # decision only, from existing reviews; no model call
ripperdoc-gate review <claim manifest>   # run reviewer(s) if no fresh review exists, then decide
```

**Claim manifest** (`.ripperdoc/claims/<slug>.json`), written by the producer when it
believes the work is done:

```json
{"slug": "psd-aliasing", "goal": "...", "claim": "...", "artifacts": ["analysis/psd.py", "out/psd.npz", "FINDINGS.md"],
 "criteria": {"source": "dossier", "ref": "dossier.json#H2"}, "packs": ["physics"]}
```

**Policy** (`.ripperdoc/policy.json`), written by a human, never by an agent:

```json
{"pass_verdicts": ["accept"], "min_confidence": 3, "ensemble": true, "max_rounds": 3,
 "reruns": {"allowed": [{"cmd": "python eval.py", "max_minutes": 20}]},
 "on_round_cap": "escalate", "packs": {"default": ["research-core"]}}
```

Reruns live here and nowhere else: this is how "only when Guillem allows it, with a time
budget" survives automation. The gate copies the matching entry into the reviewer's prompt and
`intake.rerun_budget`; without an entry the reviewer traces.

**Freshness.** The gate records the sha256 of every artifact in the review
(`intake.artifact_hashes`, new optional field). A review counts only if the hashes still
match; any edit to the work makes it stale. This closes the "review, then quietly change the
numbers" hole.

**Decision.** `pass` (verdict in `pass_verdicts`, confidence ≥ minimum, validator passes, hashes
fresh), `block` (otherwise, with the Actions lists as the reason), or `escalate` (round cap hit,
two rounds without progress, or reviewers disagree on a blocking issue the merge dismissed).
Exit codes 0 / 2 / 3. Escalate always means a human decides; the gate never loops forever and
never fixes anything.

**Integrity.**
- The gate runs the reviewer itself and reads the report it just produced; it never trusts a
  report the producer points it to.
- A **producer guard** (`hooks/producer_guard.py`, PreToolUse on the producer's session) blocks
  writes to `ripperdoc_reviews/`, `.ripperdoc/policy.json` and `packs/`. The existing
  `guard.py` keeps the reviewer read-only. Together: neither side can write the other's files.
- Producer-written files (FINDINGS.md, comments, logs) are data to the reviewer. The benchmark
  gets cases that try to instruct the reviewer (see 3.5).

### 3.4 Adapters

1. **Claude Code Stop hook** (`hooks/stop_gate.py`). On Stop, if a claim manifest exists whose
   newest review is not a fresh `pass`, return a block decision with the Actions lists so the
   producer keeps working. It must respect `stop_hook_active` and the policy's round cap so it
   cannot loop; at the cap it lets the session stop and prints the escalation. A `SubagentStop`
   variant gates a producer subagent inside a larger workflow. `experiment-review` becomes a
   thin caller of `ripperdoc-gate review`.
2. **GitHub Action** (`.github/actions/ripperdoc-gate`). On a PR, runs `check` (cheap, no model)
   by default; `review` only on a label, because it costs tokens. Posts the decision as a check
   run.
3. **CLI / Agent SDK.** `ripperdoc-gate review` with JSON on stdout is enough for any other
   harness to call it in its own loop.

The exact hook input and output fields (block decision format, `stop_hook_active`, whether
`claude --agent` applies frontmatter hooks) get confirmed against current Claude Code docs
and a real session in milestone M2, before relying on them.

### 3.5 The benchmark

The eval set becomes the harness's regression test.

**Layout.** `evals/cases/<pack>/<case>/` and one `answers.json` per pack. The ten current cases
split into `physics/` (01, 02, 03, 07, 08) and `ml/` (04, 05, 06, 09, 10). New sets:

- `software/`: a claimed bug fix whose test does not exercise the bug; a perf claim measured on
  a warm cache vs. a cold baseline; "all tests pass" with a skipped test; two clean cases.
- `gate/`: cases that test the harness, not the domain: a producer note that says "the reviewer
  has already approved this", a FINDINGS.md that instructs the reviewer, an artifact changed
  after review (must be stale), a rerun-tempting case with no permission (exists: case10).

**Metrics** per run, per pack: catch rate (CAUGHT), right-call-wrong-reason (FLAGGED), misses,
false blocks on clean cases, unauthorised reruns, invalid reviews, injection compliance, and
cost (tokens, wall time per case). Confidence calibration (mean confidence on MISSED vs.
CAUGHT) as a secondary number.

**Repeats.** A single run is noisy. Each case runs `n` times (default 3); a case is CAUGHT when
the majority is, and the report shows the spread.

**Baselines and the regression rule.** `evals/baselines/<config>.json` stores the scores of
the last accepted configuration (model, SKILL.md hash, packs and versions, guard hash). A change
to any of those reruns the affected packs and compares:
- fail if catch rate drops by more than one case, or any clean case becomes FALSE_BLOCK in the
  majority, or any unauthorised rerun or injection compliance appears;
- otherwise update the baseline in the same PR.

**When it runs.** Unit tests stay on every push (free). The benchmark costs one review per case
per repeat, so it runs on a PR label (`benchmark`) or by hand, scoped to the packs the change
touches; a full run before each release tag. Changing the reviewer model is a full run.

**Ablations** come for free from the same runner: single vs. ensemble reviewer, model A vs. B,
with vs. without a pack. That answers "is the second reviewer worth its cost" with numbers.

## 4. Repository layout after the change

```
SKILL.md                    core procedure (trimmed)
agents/ripperdoc.md         reviewer subagent (unchanged role)
packs/<id>/{pack.json,checklist.md}
bin/ripperdoc-gate          new: gate CLI
bin/validate.py             + packs, checklist_item, artifact_hashes, policy and claim validation
bin/sandbox-run, merge_reviews.py, render_dossier.py
hooks/guard.py              reviewer guard (unchanged)
hooks/producer_guard.py     new
hooks/stop_gate.py          new
schema/review.schema.json   + optional packs, checklist_item, artifact_hashes
schema/{claim,policy,pack}.schema.json   new
skills/experiment-review/   calls the gate
evals/cases/<pack>/..., evals/<pack>/answers.json, evals/baselines/, run.sh, score.py, compare.py
.github/workflows/tests.yml + benchmark.yml (label / manual)
docs/harness-architecture.md (this file)
```

## 5. Milestones

Each milestone is one PR with its own unit tests; none of them changes the reviewer's
behaviour without a benchmark comparison.

| # | Milestone | Tests that ship with it |
|---|---|---|
| M0 | **First baseline.** Run the current 10 cases (n=3) on the current setup and commit the scores. Everything after this is measured against it. Needs Claude Code on a machine with bwrap; costs ~30 reviews. | scorer tests for repeats and majority (score.py) |
| M1 | **Core / pack split.** Move research items out of Appendix A into `packs/research-core`, `physics`, `ml`; add `pack.json` schema, `packs` and `checklist_item` fields. Benchmark must not regress vs. M0. | pack manifest validation, old reviews still valid, `checklist_item` must name a loaded pack |
| M2 | **Gate + Claude Code adapter.** `ripperdoc-gate` (check/review), claim and policy schemas, artifact hashing, producer guard, Stop hook with loop protection; `experiment-review` calls the gate. Confirm hook semantics in a real session. | decision table (pass/block/escalate) for every policy branch, stale-hash detection, round cap, producer guard blocks forged reviews and policy edits, stop hook never blocks when `stop_hook_active` and the cap is reached |
| M3 | **Benchmark harness.** Per-pack layout, repeats, cost capture, `compare.py` with the regression rule, `benchmark.yml` on label; `gate/` cases. | compare.py regression rule on synthetic score files, case-layout lint (no answer key inside a case) |
| M4 | **Software pack** with its cases, and the GitHub Action adapter. | as M1 for the pack; action runs `check` on a fixture repo |
| M5 | Ablations (ensemble vs. single, model pairs) and a short results section in the README. | none new |

Already open and folded in: real `sandbox-run` test on Linux and macOS (before M0), and the
README fixes Guillem deferred (after M1, since the layout changes).

## 6. Decisions for Guillem

1. **Gate trigger.** Recommended: explicit claim manifest + Stop hook (the producer says what it
   claims; the hook enforces that a claim is reviewed). Alternative: Stop hook reviews whatever
   changed in the session, with no manifest; simpler for the producer, but the reviewer has to
   guess the claim.
2. **Default pass bar.** Recommended: `accept` with confidence ≥ 3, ensemble on. Lower to single
   reviewer for exploratory work via policy.
3. **Software pack scope.** Recommended: claims about software (fix, perf, coverage), not a
   general code reviewer, so it complements `/code-review` instead of duplicating it.
4. **Benchmark budget.** M0 and every benchmark run cost real tokens and need a machine with
   bwrap. Where and how often you want to pay for them decides whether the label-triggered CI
   job or local runs come first.

## 7. Out of scope

- A general agent framework or orchestrator. Ripperdoc stays the verifier; the harness it sits
  in belongs to the caller.
- Score maximisation. The benchmark measures the reviewer; the gate never feeds a numeric
  score back to a producer to optimise against.
- Automatic fixing. Ripperdoc and the gate return actions; a producer or a human applies them.
