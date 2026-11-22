# The Ripperdoc gate

Milestone M2 of `harness-architecture.md`. The gate turns Ripperdoc from a reviewer you call into a
condition on "done": an agent's result counts only when Ripperdoc has passed exactly that version of it.

## Pieces

| File | Who writes it | What it is |
|---|---|---|
| `.ripperdoc/policy.json` | you | Pass bar, ensemble, models, round cap, the only rerun permissions (`schema/policy.schema.json`). |
| `.ripperdoc/claims/<slug>.json` | the producer agent | What it claims and which files back it (`schema/claim.schema.json`). |
| `ripperdoc_reviews/*.md` | Ripperdoc | The reviews, as before. |
| `ripperdoc_reviews/.gate/<report>.json` | the gate | sha256 of the report and of every artifact at review time. |
| `.ripperdoc/state/` | the Stop hook | Last block per claim, for loop protection. |

## Decisions

`bin/ripperdoc-gate check <claim>` decides from existing reviews and never calls a model.
`bin/ripperdoc-gate review <claim>` runs the reviewer(s) first when there is no usable review.
Both take `--all` for every claim. Exit codes: 0 pass, 2 block, 3 escalate, 1 error.

- **pass**: the newest report for the slug was recorded by the gate, is unchanged, still matches every
  artifact byte for byte, validates, has a verdict in `pass_verdicts` and confidence ≥ `min_confidence`,
  and is an ensemble merge when `ensemble` is on.
- **block**: anything else. If a file changed, a new review runs (next round). If nothing changed and
  the verdict is below the bar, the same actions come back without spending a new review.
- **escalate**: round `max_rounds` ended without a pass, the reviewer reported no progress, or the merge
  dismissed one reviewer's blocking issue. A human decides; the gate stops reviewing.
- **error**: invalid policy or claim, an artifact outside the project, a reviewer that wrote nothing,
  or artifacts that changed while the review ran.

Reviewer sessions run as `claude -p ... --agent ripperdoc` in the project root (override the binary
with `RIPPERDOC_CLAUDE`), with web tools off unless `literature_search` is true, and with
`RIPPERDOC_GATE_ACTIVE=1` so the project's own hooks leave them alone. Rerun permission reaches the
reviewer only from `policy.reruns.allowed`; anything the producer writes in the claim's `notes` is
passed on as a claim to check, never as permission.

## Wiring it into Claude Code

```bash
cd my-project && /path/to/ripperdoc/bin/ripperdoc-gate init
```

`init` writes the default policy (accept, confidence ≥ 3, ensemble on, 3 rounds, no reruns) and prints
the hook block for `.claude/settings.json`:

- **PreToolUse → `hooks/producer_guard.py`**: the producer cannot write reviews, gate records, the
  policy, gate state or the Ripperdoc installation. It may write claims, and run
  `ripperdoc-gate check|review <claim>` as a plain command. Bash is checked by text, which is
  best-effort; the gate's own record is what makes a forged or edited report fail.
- **Stop → `hooks/stop_gate.py`** (timeout 3600 s, since a review can take several minutes): runs
  the gate for every claim. A block keeps the session going with Ripperdoc's actions as the reason.
  An escalation or an error lets the session stop with a message for you. If the session was already
  continuing because of this hook (`stop_hook_active`) and a blocked claim is in exactly the same
  state as at the last block, it stops and escalates instead of looping. Use the same script for
  `SubagentStop` to gate a producer subagent.

Set `"stop_hook": "check"` in the policy to make the hook decide only from existing reviews (no model
calls at stop time); then run `ripperdoc-gate review` yourself.

`init` also copies the claim format to `.ripperdoc/claim.schema.json`, so the producer can read it
without access to the Ripperdoc folder, and prints a `CLAUDE.md` paragraph that tells the producer to
write a claim when a result is ready and not to review it itself first. In headless runs (`claude -p`)
the producer also needs its tools allowed, e.g. `--allowedTools "Bash(python3:*)" Read Write Edit Glob Grep`;
`--permission-mode acceptEdits` alone does not allow Bash.

The producer guard lets one plain read-only command through (`cat`, `ls`, `head`, `tail`, `wc`,
`stat`, `grep`, without pipes, redirection or separators), so the producer can read reports and the
policy from Bash as well as with the Read tool.

## Real-session trial (2026-11-22)

Linux, Claude Code 2.1.326, case03 (wrong-sign damping) as the producer's project, policy with one
reviewer and 2 rounds:

1. The producer wrote the claim and tried to finish. The Stop hook ran the reviewer inside the hook
   (nested `claude -p` works): **reject**, confidence 5, blocking issue "accel() uses +γv, the model
   needs −γv". The block reason with Ripperdoc's actions reached the producer.
2. The producer flipped the sign, added a γ = 0 control and a half-step run, regenerated the outputs,
   rewrote FINDINGS.md and finished again. The artifacts had changed, so round 2 ran: **accept**,
   confidence 5, every round-1 issue verified resolved.
3. `ripperdoc-gate check --all` → pass, exit 0. Whole producer session 6 min, both reviews included.

The reviewer sessions were never blocked by the producer guard, so `RIPPERDOC_GATE_ACTIVE` reaches
hook processes. Asked to write a fake approval and lower `min_confidence`, the producer was refused
and nothing changed on disk.

## Open points

- A producer that wants to stop without a claim can simply not write one. The gate enforces that a
  declared claim is reviewed; asking for a claim at the right moment belongs in the project's
  `CLAUDE.md` (see `init`).
