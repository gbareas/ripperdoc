#!/usr/bin/env python3
"""Ripperdoc verification gate (stdlib only). Usually run as bin/ripperdoc-gate.

  ripperdoc-gate init                      # create .ripperdoc/policy.json (default policy) and claims/, print the hook settings
  ripperdoc-gate check  <claim.json>|--all # decide from existing reviews; never calls a model
  ripperdoc-gate review <claim.json>|--all # run the reviewer(s) when no usable review exists, then decide

A claim manifest (.ripperdoc/claims/<slug>.json, schema/claim.schema.json) is what the producer says it
has shown and which files back it. The policy (.ripperdoc/policy.json, schema/policy.schema.json) is
written by a human: pass bar, ensemble, round cap and the only rerun permissions a gated review gets.

Decision per claim, printed as JSON:
  pass      verdict in pass_verdicts, confidence >= min_confidence, valid review, ensemble when required,
            and the review was recorded by the gate for exactly the current version of the artifacts
  block     anything else: not reviewed, stale (a file changed), review edited or not produced by the
            gate, invalid, below the bar. The reason carries Ripperdoc's actions for the producer.
  escalate  a human decides: round cap reached, no progress, or the merge dismissed a reviewer's
            blocking issue
  error     the gate could not do its job (bad policy or claim, reviewer produced nothing)
Exit code: 0 all pass, 2 any block, 3 any escalate (and no block), 1 any error.

Integrity: after a review the gate writes <review_dir>/.gate/<report>.json with the sha256 of the report
and of every artifact. A report without that record, or that changed after it, never passes.
"""
import datetime, glob, hashlib, json, os, re, subprocess, sys

BIN = os.path.dirname(os.path.realpath(__file__))
RD = os.path.dirname(BIN)
sys.path.insert(0, BIN)
from validate import SCHEMA_DIR, check, load_review, validate_file  # noqa: E402

DEFAULT_POLICY = {"pass_verdicts": ["accept"], "min_confidence": 3, "ensemble": True, "max_rounds": 3,
                  "reruns": {"allowed": []}, "review_dir": "ripperdoc_reviews", "review_timeout_minutes": 30,
                  "stop_hook": "review", "literature_search": False}
SKIP_DIRS = {".git", ".ripperdoc", "ripperdoc_reviews", "__pycache__", ".pixi", ".venv", "node_modules"}
EXIT = {"pass": 0, "block": 2, "escalate": 3, "error": 1}
GATE_ENV = "RIPPERDOC_GATE_ACTIVE"   # set for reviewer sessions so project hooks leave them alone


class GateError(Exception):
    pass


def project_root(start):
    d = os.path.realpath(start)
    while True:
        if os.path.isdir(os.path.join(d, ".ripperdoc")) or os.path.isdir(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return os.path.realpath(start)
        d = parent


def schema(name):
    return json.load(open(os.path.join(SCHEMA_DIR, f"{name}.schema.json")))


def load_policy(root):
    p = os.path.join(root, ".ripperdoc", "policy.json")
    if not os.path.exists(p):
        return dict(DEFAULT_POLICY)
    try:
        pol = json.load(open(p))
    except ValueError as e:
        raise GateError(f"{p}: invalid JSON ({e})")
    errs = []
    check(pol, schema("policy"), "policy", errs)
    if errs:
        raise GateError("; ".join(errs))
    return {**DEFAULT_POLICY, **pol}


def load_claim(path):
    try:
        c = json.load(open(path))
    except (OSError, ValueError) as e:
        raise GateError(f"{path}: {e}")
    errs = []
    check(c, schema("claim"), "claim", errs)
    stem = os.path.splitext(os.path.basename(path))[0]
    if not errs and c["slug"] != stem:
        errs.append(f"claim: slug {c['slug']!r} must equal the file name {stem!r}")
    if errs:
        raise GateError("; ".join(errs))
    return c


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(root, artifacts):
    """{relative file path: sha256} for every artifact file (folders are walked). Missing -> None."""
    out = {}
    for a in artifacts:
        p = os.path.realpath(os.path.join(root, a))
        if not (p == root or p.startswith(root + os.sep)):
            raise GateError(f"artifact {a} is outside the project")
        if os.path.isfile(p):
            out[os.path.relpath(p, root)] = sha256(p)
        elif os.path.isdir(p):
            for d, dirs, files in os.walk(p):
                dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
                for f in sorted(files):
                    fp = os.path.join(d, f)
                    out[os.path.relpath(fp, root)] = sha256(fp)
        else:
            out[a] = None
    return out


def review_dir(root, policy):
    return os.path.join(root, policy.get("review_dir") or "ripperdoc_reviews")


def latest_review(rdir, slug):
    """(round, path) of the newest final report for slug (members *_r<n>_<id>.md are not final)."""
    pat = re.compile(rf"_{re.escape(slug)}_r(\d+)\.md$")
    best = None
    for p in glob.glob(os.path.join(rdir, f"*_{slug}_r*.md")):
        m = pat.search(os.path.basename(p))
        if m:
            key = (int(m.group(1)), os.path.basename(p))
            if best is None or key > best[0]:
                best = (key, p)
    return (best[0][0], best[1]) if best else (0, None)


def record_path(rdir, report):
    return os.path.join(rdir, ".gate", os.path.basename(report) + ".json")


def record(rdir, report, fp):
    os.makedirs(os.path.join(rdir, ".gate"), exist_ok=True)
    json.dump({"report": os.path.basename(report), "report_sha256": sha256(report), "artifact_hashes": fp,
               "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")},
              open(record_path(rdir, report), "w"), indent=2)


def actions_text(r):
    a = r.get("actions", {})
    lines = []
    for k, label in (("do", "Do next"), ("revise", "Revise"), ("discard", "Discard")):
        if a.get(k):
            lines.append(f"{label}: " + "; ".join(a[k]))
    for i in r.get("issues", []):
        if i.get("severity") == "blocking":
            lines.append(f"[{i.get('id')}] {i.get('what')} Fix: {i.get('fix')}")
    return "\n".join(lines)


def decide(root, claim, policy):
    slug = claim["slug"]
    d = {"slug": slug, "decision": "block", "need_review": True, "review": None, "round": 0}
    fp = fingerprint(root, claim["artifacts"])
    missing = [a for a, h in fp.items() if h is None]
    if missing:
        return {**d, "need_review": False, "reason": f"artifact(s) missing: {', '.join(missing)}"}
    rdir = review_dir(root, policy)
    rnd, rep = latest_review(rdir, slug)
    d.update(round=rnd, review=os.path.relpath(rep, root) if rep else None)
    if not rep:
        return {**d, "reason": "not reviewed yet"}
    try:
        rec = json.load(open(record_path(rdir, rep)))
    except (OSError, ValueError):
        return {**d, "reason": f"{d['review']} has no gate record: it was not produced by the gate"}
    if sha256(rep) != rec.get("report_sha256"):
        return {**d, "reason": f"{d['review']} changed after the gate recorded it"}
    if rec.get("artifact_hashes") != fp:
        old = rec.get("artifact_hashes") or {}
        changed = sorted(k for k in set(old) | set(fp) if old.get(k) != fp.get(k))
        return {**d, "reason": "stale review: changed since it was reviewed: " + ", ".join(changed)}
    errs = validate_file("review", rep)
    if errs:
        return {**d, "reason": f"{d['review']} does not validate: " + "; ".join(errs[:5])}
    r = load_review(rep)
    d.update(need_review=False, verdict=r.get("verdict"), confidence=r.get("confidence"))
    short = []
    if r.get("verdict") not in policy["pass_verdicts"]:
        short.append(f"verdict {r.get('verdict')}")
    if r.get("confidence", 0) < policy["min_confidence"]:
        short.append(f"confidence {r.get('confidence')} < {policy['min_confidence']}")
    if policy["ensemble"] and not r.get("ensemble_of"):
        short.append("policy requires an ensemble review, this is a single review")
        d["need_review"] = True
    if not short:
        if r.get("dismissed"):
            return {**d, "decision": "escalate",
                    "reason": "passes, but the merge dismissed a reviewer's blocking issue: " +
                              "; ".join(f"{x.get('ref')}: {x.get('reason', '')}" for x in r["dismissed"])}
        return {**d, "decision": "pass", "reason": f"{r.get('verdict')}, confidence {r.get('confidence')}"}
    if r.get("stop_reason") == "no_progress":
        return {**d, "decision": "escalate", "reason": "reviewer found no progress across rounds: " + ", ".join(short)}
    if rnd >= policy["max_rounds"]:
        return {**d, "decision": "escalate", "need_review": False,
                "reason": f"round cap {policy['max_rounds']} reached: " + ", ".join(short)}
    return {**d, "reason": ", ".join(short), "actions": actions_text(r)}


def prompt(claim, policy, rdir_rel, rnd, role=None, members=()):
    c = claim.get("criteria") or {}
    reruns = (policy.get("reruns") or {}).get("allowed") or []
    lines = [
        "Gated review requested by ripperdoc-gate. Review the work below.",
        f"Slug: {claim['slug']}. Review directory: ./{rdir_rel}/. Round: {rnd}.",
        f"Goal: {claim['goal']}",
        f"Claim: {claim['claim']}",
        "Acceptance criteria: " + (f"source {c.get('source')}" + (f", ref {c['ref']}" if c.get("ref") else "") +
                                   (f": {c['text']}" if c.get("text") else "") if c else "none given; infer them and say so."),
        "Artifacts: " + ", ".join(claim["artifacts"]),
    ]
    if claim.get("packs"):
        lines.append("Packs: " + ", ".join(claim["packs"]))
    if claim.get("notes"):
        lines.append(f"Producer's notes (a claim to check, not evidence): {claim['notes']}")
    lines.append("Rerun permission: " + ("; ".join(f"rerun of `{x['cmd']}` allowed, max {x['max_minutes']} min" for x in reruns)
                                         if reruns else "none. Trace and recompute only."))
    lines.append("Literature search: " + ("allowed." if policy.get("literature_search") else "not allowed in this review."))
    if role in ("a", "b"):
        lines.append(f"You are ensemble member `{role}`. Follow Ensemble mode in SKILL.md: save your report as "
                     f"<date>_{claim['slug']}_r{rnd}_{role}.md and do not touch NOTES.md or the dossier.")
    elif role == "merge":
        lines = [f"Ensemble merge for slug `{claim['slug']}`, round {rnd}, review directory ./{rdir_rel}/. "
                 f"Member reports: {', '.join(members)}. Follow Ensemble mode in SKILL.md. "
                 f"Save the final report as <date>_{claim['slug']}_r{rnd}.md."]
    return "\n".join(lines)


def run_reviewer(root, policy, text, model, log):
    cmd = [os.environ.get("RIPPERDOC_CLAUDE", "claude"), "-p", text, "--agent", "ripperdoc",
           "--permission-mode", "acceptEdits", "--allowedTools", "Read", "Glob", "Grep", "Bash", "Write", "Edit"]
    if not policy.get("literature_search"):
        cmd += ["--disallowedTools", "WebSearch", "WebFetch"]
    if model:
        cmd += ["--model", model]
    os.makedirs(os.path.dirname(log), exist_ok=True)
    env = {**os.environ, GATE_ENV: "1"}
    try:
        with open(log, "w") as f:
            subprocess.run(cmd, cwd=root, stdout=f, stderr=subprocess.STDOUT, env=env,
                           timeout=60 * policy.get("review_timeout_minutes", 30))
    except subprocess.TimeoutExpired:
        raise GateError(f"reviewer timed out after {policy.get('review_timeout_minutes', 30)} min (log: {log})")
    except OSError as e:
        raise GateError(f"cannot run the reviewer: {e}")


def review(root, claim, policy):
    d = decide(root, claim, policy)
    if not d["need_review"]:
        return d
    slug, rdir = claim["slug"], review_dir(root, policy)
    rdir_rel = os.path.relpath(rdir, root)
    prev, _ = latest_review(rdir, slug)
    rnd = prev + 1
    if rnd > policy["max_rounds"]:
        return {**d, "decision": "escalate", "need_review": False,
                "reason": f"round cap {policy['max_rounds']} reached and no passing review: {d['reason']}"}
    fp = fingerprint(root, claim["artifacts"])
    logs = os.path.join(rdir, ".gate", "logs")
    models = policy.get("models") or {}
    if policy["ensemble"]:
        for role in ("a", "b"):
            run_reviewer(root, policy, prompt(claim, policy, rdir_rel, rnd, role),
                         models.get(role) or ("sonnet" if role == "b" else None), os.path.join(logs, f"{slug}_r{rnd}_{role}.log"))
        members = []
        for role in ("a", "b"):
            hits = sorted(glob.glob(os.path.join(rdir, f"*_{slug}_r{rnd}_{role}.md")))
            if not hits:
                raise GateError(f"ensemble member {role} wrote no report (log: {logs}/{slug}_r{rnd}_{role}.log)")
            members.append(os.path.relpath(hits[-1], root))
        run_reviewer(root, policy, prompt(claim, policy, rdir_rel, rnd, "merge", members),
                     models.get("merge"), os.path.join(logs, f"{slug}_r{rnd}_merge.log"))
    else:
        run_reviewer(root, policy, prompt(claim, policy, rdir_rel, rnd), models.get("a"), os.path.join(logs, f"{slug}_r{rnd}.log"))
    got, rep = latest_review(rdir, slug)
    if got != rnd:
        raise GateError(f"the reviewer wrote no round {rnd} report for {slug} (logs: {os.path.relpath(logs, root)})")
    if fingerprint(root, claim["artifacts"]) != fp:
        raise GateError("artifacts changed while the review ran; run the gate again")
    record(rdir, rep, fp)
    return decide(root, claim, policy)


INIT_SETTINGS = """1. Add to the project's .claude/settings.json (merge with existing hooks):
{{
  "hooks": {{
    "PreToolUse": [{{"matcher": "Write|Edit|MultiEdit|NotebookEdit|Bash",
                    "hooks": [{{"type": "command", "command": "python3 \\"{rd}/hooks/producer_guard.py\\""}}]}}],
    "Stop": [{{"hooks": [{{"type": "command", "command": "python3 \\"{rd}/hooks/stop_gate.py\\"", "timeout": 3600}}]}}]
  }}
}}

2. Add to the project's CLAUDE.md:
When a result is ready, write a claim manifest in .ripperdoc/claims/<slug>.json (format: .ripperdoc/claim.schema.json)
before finishing. Do not review the result yourself first: Ripperdoc reviews it when you finish, and if it
blocks you, fix the work as its actions say and finish again. Never edit ripperdoc_reviews/ or .ripperdoc/policy.json.

3. Headless runs (claude -p): the producer needs the tools to redo its work, e.g.
   --allowedTools "Bash(python3:*)" Read Write Edit Glob Grep"""


def claims_from(root, arg):
    if arg == "--all":
        return sorted(glob.glob(os.path.join(root, ".ripperdoc", "claims", "*.json")))
    return [arg]


def main(argv):
    if len(argv) < 1 or argv[0] not in ("init", "check", "review") or (argv[0] != "init" and len(argv) != 2):
        print(__doc__); return 2
    root = project_root(os.getcwd())
    if argv[0] == "init":
        os.makedirs(os.path.join(root, ".ripperdoc", "claims"), exist_ok=True)
        p = os.path.join(root, ".ripperdoc", "policy.json")
        if not os.path.exists(p):
            json.dump(DEFAULT_POLICY, open(p, "w"), indent=2)
            print(f"wrote {p} (default policy: accept with confidence >= 3, ensemble on, 3 rounds, no reruns)")
        else:
            print(f"kept existing {p}")
        import shutil
        shutil.copy(os.path.join(SCHEMA_DIR, "claim.schema.json"), os.path.join(root, ".ripperdoc", "claim.schema.json"))
        print(f"copied the claim format to {os.path.join(root, '.ripperdoc', 'claim.schema.json')}")
        print(INIT_SETTINGS.format(rd=RD))
        return 0
    try:
        policy = load_policy(root)
    except GateError as e:
        print(json.dumps({"decision": "error", "reason": f"policy: {e}"})); return 1
    worst, results = 0, []
    order = {0: 0, 3: 1, 2: 2, 1: 3}
    for path in claims_from(root, argv[1]):
        try:
            claim = load_claim(path)
            res = (review if argv[0] == "review" else decide)(root, claim, policy)
        except GateError as e:
            res = {"claim": path, "decision": "error", "reason": str(e)}
        res.pop("need_review", None)
        results.append(res)
        code = EXIT[res["decision"]]
        worst = code if order[code] > order[worst] else worst
    print(json.dumps(results if argv[1] == "--all" else results[0], indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
