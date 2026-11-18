#!/usr/bin/env python3
"""Validate ripperdoc output against its schema (stdlib only).

  validate.py review  <report.md | review.json>   # uses the last ```json block of a .md
  validate.py dossier <dossier.json>

Exit 0 = valid. Otherwise prints one error per line and exits 1.
"""
import json, os, re, sys

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "schema")
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "number": (int, float)}


def check(v, s, path, errs):
    if "const" in s and v != s["const"]:
        errs.append(f"{path}: must be {s['const']!r}")
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: {v!r} not in {s['enum']}")
        return
    t = s.get("type")
    if t == "integer":
        if not isinstance(v, int) or isinstance(v, bool):
            errs.append(f"{path}: expected integer"); return
    elif t:
        if not isinstance(v, TYPES[t]) or (t != "boolean" and isinstance(v, bool)):
            errs.append(f"{path}: expected {t}"); return
    if isinstance(v, str):
        if len(v) < s.get("minLength", 0): errs.append(f"{path}: empty string")
        if "pattern" in s and not re.search(s["pattern"], v): errs.append(f"{path}: does not match {s['pattern']}")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in s and v < s["minimum"]: errs.append(f"{path}: below {s['minimum']}")
        if "maximum" in s and v > s["maximum"]: errs.append(f"{path}: above {s['maximum']}")
    if isinstance(v, list):
        if len(v) < s.get("minItems", 0): errs.append(f"{path}: needs at least {s['minItems']} item(s)")
        if "maxItems" in s and len(v) > s["maxItems"]: errs.append(f"{path}: at most {s['maxItems']} item(s)")
        for i, x in enumerate(v):
            check(x, s.get("items", {}), f"{path}[{i}]", errs)
    if isinstance(v, dict):
        props = s.get("properties", {})
        for k in s.get("required", []):
            if k not in v: errs.append(f"{path}: missing '{k}'")
        for k, x in v.items():
            if k in props: check(x, props[k], f"{path}.{k}", errs)
            elif s.get("additionalProperties") is False: errs.append(f"{path}: unknown field '{k}'")


def review_rules(r, errs):
    issues = r.get("issues", [])
    ids = [i.get("id") for i in issues]
    if len(ids) != len(set(ids)): errs.append("issues: duplicate ids")
    blocking = [i for i in issues if i.get("severity") == "blocking"]
    if r.get("verdict") == "accept" and blocking: errs.append("verdict accept with blocking issues")
    if r.get("verdict") in ("revise", "reject") and not blocking and not any(v.get("status") == "contradicted" for v in r.get("verifications", [])):
        errs.append(f"verdict {r.get('verdict')} needs a blocking issue or a contradicted verification")
    if r.get("round") == 1:
        if r.get("previous_issues"): errs.append("round 1: previous_issues must be empty")
        if r.get("keep_or_revert") != "n/a": errs.append("round 1: keep_or_revert must be n/a")
    elif r.get("round", 1) > 1:
        if r.get("keep_or_revert") == "n/a": errs.append("round > 1: keep_or_revert must be keep or revert")
        if not r.get("previous_issues"): errs.append("round > 1: previous_issues must list the earlier issues")
    if r.get("stop") != (r.get("stop_reason") != "continue"): errs.append("stop and stop_reason disagree")
    if r.get("stop_reason") == "no_blocking_issues" and blocking: errs.append("stop_reason no_blocking_issues but blocking issues remain")
    if len(r.get("worklog", [])) < r.get("round", 1): errs.append("worklog needs one line per round")
    if r.get("intake", {}).get("code_review_file") and "code_findings" not in r:
        errs.append("intake.code_review_file is set but code_findings is missing")
    by_id = {i.get("id"): i for i in issues}
    for f in r.get("code_findings", []):
        if f.get("affects_result") in ("yes", "unknown"):
            iss = by_id.get(f.get("issue_id"))
            if not iss: errs.append(f"code_findings {f.get('ref')}: affects_result {f.get('affects_result')} needs an issue_id present in issues")
            elif iss.get("category") != "code_defect": errs.append(f"code_findings {f.get('ref')}: linked issue must have category code_defect")


def dossier_rules(d, errs):
    for key in ("hypotheses", "work_done", "literature"):
        ids = [x.get("id", x.get("key")) for x in d.get(key, [])]
        if len(ids) != len(set(ids)): errs.append(f"{key}: duplicate ids")
    hyp = {h.get("id") for h in d.get("hypotheses", [])}
    for w in d.get("work_done", []):
        for h in w.get("tests_hypotheses", []):
            if h not in hyp: errs.append(f"work_done {w.get('id')}: unknown hypothesis {h}")
        if w.get("review") != "not_reviewed" and not w.get("review_file"): errs.append(f"work_done {w.get('id')}: review_file missing")
    for h in d.get("hypotheses", []):
        if h.get("pre_registered") and not h.get("frozen_ref"): errs.append(f"hypothesis {h.get('id')}: pre_registered but no frozen_ref")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("review", "dossier"):
        print(__doc__); sys.exit(2)
    kind, path = sys.argv[1:]
    text = open(path).read()
    if path.endswith(".md"):
        blocks = re.findall(r"```json\s*\n(.*?)\n```", text, re.S)
        if not blocks: print(f"{path}: no ```json block found"); sys.exit(1)
        text = blocks[-1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"invalid JSON: {e}"); sys.exit(1)
    errs = []
    check(data, json.load(open(os.path.join(SCHEMA_DIR, f"{kind}.schema.json"))), "$", errs)
    (review_rules if kind == "review" else dossier_rules)(data, errs)
    if errs:
        print("\n".join(errs)); sys.exit(1)
    print(f"valid {kind}: {path}")


if __name__ == "__main__":
    main()
