---
name: experiment-review
description: Close out a finished experiment or analysis run before its results are trusted: run /code-review on the code that produced the results, then the ripperdoc subagent with those findings, and report one combined verdict. Use proactively whenever an experiment, analysis, evaluation or simulation run has finished and before its numbers go into a findings document, figure or paper; also when the user says "review this experiment" or "close out <experiment>".
---

# Experiment review: code review, then Ripperdoc

Two reviewers with different jobs, run in this order:
1. **`/code-review`** looks for bugs in the code that produced the results.
2. **Ripperdoc** (subagent) decides whether the result can be trusted. It takes the code-review findings as input and checks which of them actually change the claimed numbers.

Code review alone cannot say whether a bug matters for the conclusion. Ripperdoc alone is not a bug hunter. Running code review first gives Ripperdoc the bugs to check.

Ripperdoc's procedure lives in `__RIPPERDOC_HOME__/SKILL.md`; you do not need to read it to run this.

## Steps

### 1. Pin down the experiment
Collect, from the conversation, the project's findings/log documents and the run's outputs:
- **slug**: short kebab-case name, the same one Ripperdoc uses across rounds (check `ripperdoc_reviews/NOTES.md` for an existing one).
- **claim**: what the experiment is said to show, with the key numbers.
- **code**: the files that produced those numbers (training/eval/analysis scripts, the modules they import that changed for this experiment, the run/queue script).
- **outputs and log**: result files, the experiment log or findings entry.
- **protocol**: the frozen spec and hash, if the experiment was pre-registered.
- **review directory**: `ripperdoc_reviews/` at the root of the project folder (e.g. the publication folder).

If the claim is not written down anywhere yet, state it in one or two sentences and say that you inferred it.

### 2. Code review
Invoke the `code-review` skill on the experiment's code:
- **Target**: if the experiment's code is committed, the range from the commit before the experiment's changes (or the protocol freeze commit) to the commit that ran it. If it is uncommitted, pass the code paths from step 1.
- **Level**: `medium` by default; `high` when the results are headed for a paper or a frozen criterion decides the outcome. Never `max` or `ultra` unless the user asks for it.
- **Never `--fix`.** Fixing the code after the results exist would leave results that no code reproduces. Fixes come after the review, as a decision for the user.

Write the findings, exactly as reported (file, line, summary, failure scenario, verdict if any), to `<review dir>/<YYYY-MM-DD>_<slug>_code-review.md`, numbered `CR-01`, `CR-02`, ... Write the file even when there are no findings, and say what was reviewed (commit range or paths, level).

### 3. Ripperdoc
Spawn the `ripperdoc` agent (foreground, since you need its verdict) with:
- goal, claim, acceptance criteria (or the frozen protocol), slug and review directory,
- paths to code, outputs, log/findings entry,
- rerun permission only if the user gave it, quoted with its time budget (e.g. "rerun eval.py allowed, max 20 min"). Otherwise say nothing: Ripperdoc then traces and recomputes from saved outputs, and never reruns training or simulations on its own,
- the code-review file from step 2, with this instruction: "For each CR finding, decide whether it affects the computation behind the claimed numbers. Verify the most consequential one if it could change the conclusion, by tracing whether the buggy line feeds the claimed number."

Do not add your own opinion of the result to the prompt. Ripperdoc should judge the artifacts, not your summary.

### 4. Report to the user
Give one short combined answer:
- Ripperdoc's verdict and confidence, and the report path.
- The **Actions** lists (do next / revise / discard).
- Code-review findings Ripperdoc judged `affects_result: yes` or `unknown`, and how many it judged irrelevant to the result.
- What should happen next, as a recommendation. Do not start fixing anything or rerunning anything until the user says so.

### 5. Document
Follow the project's documentation rules: add one line to the experiment's entry in the findings/log document pointing to the Ripperdoc report and verdict. If the verdict is `reject` or a result is listed under Discard, say so in that entry rather than leaving the result looking valid.

## Loop
After the user or producer fixes things and reruns, run this skill again with the same slug. Code review covers the new changes since the last review; Ripperdoc picks up its earlier report and runs in loop mode (round cap 3).
