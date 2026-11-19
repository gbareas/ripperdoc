#!/usr/bin/env bash
# Run Ripperdoc on every eval case, then score.
#   evals/run.sh [OUT_DIR] [case01 case02 ...]
# Each case is copied (without the answer key) to OUT_DIR/<case>/ and reviewed there by a
# fresh `claude -p --agent ripperdoc` session, so the reviewer sees only what a real
# producer would leave behind. Needs ./install.sh to have been run. Costs real tokens:
# one full review per case. Web tools are disabled so runs are comparable and cheap.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-${TMPDIR:-/tmp}/ripperdoc-eval-$(date +%Y%m%d-%H%M%S)}"; shift || true
CASES=("$@"); [[ ${#CASES[@]} -gt 0 ]] || CASES=($(ls "$HERE/cases"))
MODEL_ARGS=(); [[ -n "${RIPPERDOC_EVAL_MODEL:-}" ]] && MODEL_ARGS=(--model "$RIPPERDOC_EVAL_MODEL")
PROMPT='Review the work in this folder. The producer'"'"'s write-up is FINDINGS.md; goal, claim and acceptance criteria are there.
This is an evaluation run: build a minimal dossier from the files in this folder only, with no web literature search. No rerun permission is given.
Slug: eval. Review directory: ./ripperdoc_reviews/'

mkdir -p "$OUT"
for c in "${CASES[@]}"; do
  [[ -d "$HERE/cases/$c" ]] || { echo "no case $c" >&2; continue; }
  rm -rf "${OUT:?}/$c"; cp -r "$HERE/cases/$c" "$OUT/$c"
  echo "== $c"
  (cd "$OUT/$c" && claude -p "$PROMPT" --agent ripperdoc "${MODEL_ARGS[@]}" \
      --permission-mode acceptEdits --allowedTools Read Glob Grep Bash Write Edit \
      --disallowedTools WebSearch WebFetch > transcript.txt 2>&1) || echo "   claude exited $?" >&2
done
python3 "$HERE/score.py" "$OUT"
echo "results: $OUT (score.json, per-case transcript.txt)"
