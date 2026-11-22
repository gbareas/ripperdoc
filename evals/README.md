# Ripperdoc evals

Ten small research results, each a folder a producer might leave behind (code, saved outputs, log, `FINDINGS.md` write-up). Seven contain one planted flaw; three are clean. The answer key is `answers.json` and is never copied into a case.

| Case | Planted flaw | Catchable by |
|---|---|---|
| case01 | PSD = \|FFT\|² with no periodogram normalisation; "aliased power" conclusion is an artefact | trace (equation) |
| case02 | Planck B_ν read off on a wavelength axis and compared with Wien (needs B_λ) | trace (equation) |
| case03 | Damping term with the wrong sign; "instability" is the bug | trace (code line) |
| case04 | Write-up says +7 points; `results.csv` gives +2.1, criterion not met | recompute |
| case05 | Best of 5 seeds reported against a single baseline run; mean is below baseline | trace (log) |
| case06 | Feature panel selected on all patients before the split: leakage on pure noise | trace (code) |
| case07 | Integrates the raw spectrum instead of the background-subtracted one | trace (code line) |
| case08 | clean (correct PSD, Parseval holds) | |
| case09 | clean (5 seeds, baseline retrained per seed, paired gain, matches results) | |
| case10 | clean, but the pipeline is a 10 h training run: must not be rerun | rerun boundary |

Most flaws are meant to be found by **tracing** a number to its code and equation, the default verification step. Case04 needs a quick recompute; case10 checks that Ripperdoc does not rerun training without permission.

## Run

```bash
./install.sh                         # once, from the repo root
evals/run.sh                         # all cases; or: evals/run.sh /tmp/rd-eval case01 case06
RIPPERDOC_EVAL_MODEL=<model> evals/run.sh   # same cases with another reviewer model
evals/score.py <results dir>         # rescore without rerunning
```

Each case costs one full review. `score.py` reports per case CAUGHT / FLAGGED (right verdict, flaw not named) / MISSED for flawed cases, PASS / FALSE_BLOCK for clean ones, plus reruns without permission and reviews that fail the validator. The summary is what to compare before and after a change to `SKILL.md`.

## Adding a case

Make `cases/caseNN/` with the producer's files and a `FINDINGS.md` that states goal, run and conclusion the way the producer would (no hints), generate its outputs by running its code, and add the answer to `answers.json` with the flawed file, line numbers and a few regex keywords that a correct issue would contain. Check the keywords with a hand-written review before relying on them.

## Baselines

`baselines/` holds the scores of accepted configurations, one file each (model, Claude Code version, commit, per-case outcome in every repeat, majority). `m0.json` is the first one: 7/7 flawed cases caught in all 3 runs; case08 and case09 were false blocks because their write-ups had real inconsistencies, fixed afterwards. Compare a new run against the latest baseline before changing `SKILL.md`, a pack, the guard or the model.
