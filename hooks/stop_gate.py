#!/usr/bin/env python3
"""Claude Code Stop / SubagentStop hook for the producer's session: work is not done until its claims pass.

For every claim manifest in .ripperdoc/claims/, run the gate (`review` by default; `check` when the
policy sets stop_hook: check). Then:
  - any block    -> {"decision": "block", "reason": ...}: the session keeps going with Ripperdoc's actions
  - escalate     -> the session may stop; a systemMessage tells the human what to decide
  - all pass     -> the session may stop
Loop protection: when stop_hook_active is set (the session is already continuing because of this hook)
and a blocked claim is in exactly the same state as at the last block (same report, same artifacts),
the producer made no progress, so the hook lets the session stop and escalates instead of blocking
again. The policy's max_rounds caps the number of reviews per claim.
Reviewer sessions started by the gate carry RIPPERDOC_GATE_ACTIVE=1 and are ignored.
"""
import hashlib, importlib.util, json, os, sys

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin")
spec = importlib.util.spec_from_file_location("gate", os.path.join(BIN, "gate.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def emit(obj):
    print(json.dumps(obj))
    sys.exit(0)


def state_key(root, claim, res):
    fp = gate.fingerprint(root, claim["artifacts"])
    return hashlib.sha256(json.dumps([res.get("review"), fp], sort_keys=True).encode()).hexdigest()


def main():
    if os.environ.get(gate.GATE_ENV):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    root = gate.project_root(data.get("cwd") or os.getcwd())
    paths = gate.claims_from(root, "--all")
    if not paths:
        sys.exit(0)
    try:
        policy = gate.load_policy(root)
    except gate.GateError as e:
        emit({"systemMessage": f"Ripperdoc gate: policy is invalid ({e}); claims were not checked."})
    run = gate.review if policy.get("stop_hook", "review") == "review" else gate.decide
    state_dir = os.path.join(root, ".ripperdoc", "state")
    os.makedirs(state_dir, exist_ok=True)
    blocks, escalations, errors, stuck = [], [], [], []
    for p in paths:
        try:
            claim = gate.load_claim(p)
            res = run(root, claim, policy)
        except gate.GateError as e:
            errors.append(f"{os.path.basename(p)}: {e}")
            continue
        slug = claim["slug"]
        if res["decision"] == "block":
            key = state_key(root, claim, res)
            sp = os.path.join(state_dir, f"{slug}.json")
            last = json.load(open(sp)).get("key") if os.path.exists(sp) else None
            if data.get("stop_hook_active") and last == key:
                stuck.append(f"{slug}: {res['reason']}")
                continue
            json.dump({"key": key, "review": res.get("review")}, open(sp, "w"))
            blocks.append(f"Claim `{slug}` is not done: {res['reason']}" + (f"\n{res['actions']}" if res.get("actions") else ""))
        elif res["decision"] == "escalate":
            escalations.append(f"{slug}: {res['reason']}")
    msgs = []
    if escalations:
        msgs.append("Ripperdoc gate needs a human decision: " + " | ".join(escalations))
    if stuck:
        msgs.append("Ripperdoc gate: no progress since the last block, stopping so a human can decide: " + " | ".join(stuck))
    if errors:
        msgs.append("Ripperdoc gate errors: " + " | ".join(errors))
    if blocks:
        out = {"decision": "block", "reason": "\n\n".join(blocks) +
               "\n\nFix the work (not the review), update the claim manifest if the claim changed, then finish again."}
        if msgs:
            out["systemMessage"] = " ".join(msgs)
        emit(out)
    if msgs:
        emit({"systemMessage": " ".join(msgs)})
    sys.exit(0)


if __name__ == "__main__":
    main()
