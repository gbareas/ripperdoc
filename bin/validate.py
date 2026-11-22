#!/usr/bin/env python3
"""Validate ripperdoc output against its schema (stdlib only).

  validate.py review  <report.md | review.json>   # uses the last ```json block of a .md
  validate.py dossier <dossier.json>
  validate.py packs   [<packs dir>]                 # every packs/<id>/pack.json + checklist.md

Exit 0 = valid. Otherwise prints one error per line and exits 1.
"""
import json, os, re, sys

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "schema")
PACKS_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "packs")
ITEM_RE = re.compile(r"^### ([a-z][a-z0-9-]*\.[a-z0-9-]+)\s*$", re.M)
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


SEVERITY = {"accept": 0, "revise": 1, "reject": 2}


def load_review(path):
    text = open(path).read()
    if path.endswith(".md"):
        blocks = re.findall(r"```json\s*\n(.*?)\n```", text, re.S)
        if not blocks:
            raise ValueError(f"{path}: no ```json block found")
        text = blocks[-1]
    return json.loads(text)


def ensemble_rules(r, path, errs):
    """A merged review must account for every member's blocking issues and contradicted verifications."""
    if r.get("reviewer"):
        errs.append("a review cannot be both an ensemble member (reviewer) and a merge (ensemble_of)")
    base = os.path.dirname(os.path.realpath(path))
    members = {}
    for rel in r["ensemble_of"]:
        try:
            m = load_review(os.path.join(base, rel))
        except (OSError, ValueError) as e:
            errs.append(f"ensemble_of {rel}: cannot read ({e})"); continue
        rid = m.get("reviewer")
        if not rid:
            errs.append(f"ensemble_of {rel}: member has no reviewer id"); continue
        if rid in members:
            errs.append(f"ensemble_of {rel}: duplicate reviewer id {rid}")
        if m.get("slug") != r.get("slug") or m.get("round") != r.get("round"):
            errs.append(f"ensemble_of {rel}: slug/round differ from the merged review")
        members[rid] = m
    carried = {ref for i in r.get("issues", []) for ref in i.get("merged_from", [])}
    dismissed = {d.get("ref") for d in r.get("dismissed", [])}
    known = set()
    for rid, m in members.items():
        for i in m.get("issues", []):
            ref = f"{rid}:{i.get('id')}"
            known.add(ref)
            if i.get("severity") == "blocking" and ref not in carried and ref not in dismissed:
                errs.append(f"blocking issue {ref} is neither merged (merged_from) nor dismissed with a reason")
        for n, v in enumerate(m.get("verifications", []), 1):
            ref = f"{rid}:V{n}"
            known.add(ref)
            if v.get("status") == "contradicted" and ref not in dismissed and r.get("verdict") == "accept":
                errs.append(f"verification {ref} is contradicted and not dismissed, so the merged verdict cannot be accept")
    for ref in carried | dismissed:
        if members and ref not in known:
            errs.append(f"{ref}: no such issue or verification in the member reviews")
    if members and r.get("confidence", 0) > max(m.get("confidence", 0) for m in members.values()):
        errs.append("merged confidence is higher than every member's")
    if members and not r.get("dismissed") and SEVERITY.get(r.get("verdict"), 0) < max(SEVERITY.get(m.get("verdict"), 0) for m in members.values()):
        errs.append("merged verdict is milder than a member's, but nothing was dismissed to justify it")


def load_packs(packs_dir=PACKS_DIR):
    """{id: {"manifest": dict, "items": [item ids in checklist.md order]}} for every pack folder."""
    packs = {}
    if not os.path.isdir(packs_dir):
        return packs
    for name in sorted(os.listdir(packs_dir)):
        d = os.path.join(packs_dir, name)
        if not os.path.isdir(d):
            continue
        entry = {"manifest": None, "items": [], "error": None}
        try:
            entry["manifest"] = json.load(open(os.path.join(d, "pack.json")))
            entry["items"] = ITEM_RE.findall(open(os.path.join(d, "checklist.md")).read())
        except (OSError, ValueError) as e:
            entry["error"] = str(e)
        packs[name] = entry
    return packs


def pack_rules(packs, errs, case_ids=None):
    schema = json.load(open(os.path.join(SCHEMA_DIR, "pack.schema.json")))
    for name, p in packs.items():
        if p["error"]:
            errs.append(f"pack {name}: {p['error']}"); continue
        m = p["manifest"]
        check(m, schema, f"pack {name}", errs)
        if m.get("id") != name:
            errs.append(f"pack {name}: id {m.get('id')!r} must equal the folder name")
        if not p["items"]:
            errs.append(f"pack {name}: checklist.md has no '### {name}.<item>' headings")
        if len(p["items"]) != len(set(p["items"])):
            errs.append(f"pack {name}: duplicate checklist item ids")
        for item in p["items"]:
            if not item.startswith(name + "."):
                errs.append(f"pack {name}: checklist item {item} must start with '{name}.'")
        for ext in m.get("extends", []):
            if ext not in packs: errs.append(f"pack {name}: extends unknown pack {ext}")
            if ext == name: errs.append(f"pack {name}: extends itself")
        if case_ids is not None:
            for c in m.get("eval_cases", []):
                if c not in case_ids: errs.append(f"pack {name}: eval case {c} is not in evals/answers.json")


def packs_used_rules(r, errs, packs):
    """A review that lists packs must name installed packs, include what they extend, and tag
    issues/verifications only with items of listed packs. Item ids are checked against the installed
    checklist when the review's pack version has the installed major version; a review made with
    another major version stays valid and its item ids are not checked (items may have been renamed)."""
    listed, other_major = {}, set()
    for p in r.get("packs", []):
        pid, ver = p.get("id"), p.get("version")
        if pid in listed: errs.append(f"packs: {pid} listed twice")
        listed[pid] = ver
        inst = packs.get(pid)
        if not inst or not inst["manifest"]:
            errs.append(f"packs: unknown pack {pid}"); continue
        installed = inst["manifest"].get("version", "")
        if str(ver).split(".")[0] != installed.split(".")[0]:
            other_major.add(pid)  # made with another major version: its item ids may have changed, so skip them
        for ext in inst["manifest"].get("extends", []):
            if ext not in [x.get("id") for x in r.get("packs", [])]:
                errs.append(f"packs: {pid} extends {ext}, which must be listed too")
    tagged = [(f"issues {i.get('id')}", i.get("checklist_item")) for i in r.get("issues", [])]
    tagged += [(f"verifications[{n}]", v.get("checklist_item")) for n, v in enumerate(r.get("verifications", []))]
    for where, item in tagged:
        if not item:
            continue
        pid = item.split(".", 1)[0]
        if pid not in listed:
            errs.append(f"{where}: checklist_item {item} belongs to pack {pid}, which is not in packs")
        elif pid in packs and pid not in other_major and item not in packs[pid]["items"]:
            errs.append(f"{where}: checklist_item {item} does not exist in packs/{pid}/checklist.md")


def review_rules(r, errs, path=""):
    issues = r.get("issues", [])
    ids = [i.get("id") for i in issues]
    if len(ids) != len(set(ids)): errs.append("issues: duplicate ids")
    blocking = [i for i in issues if i.get("severity") == "blocking"]
    if r.get("verdict") == "accept" and blocking: errs.append("verdict accept with blocking issues")
    vers = r.get("verifications", [])
    if r.get("verdict") in ("revise", "reject") and not blocking and not any(v.get("status") == "contradicted" for v in vers):
        errs.append(f"verdict {r.get('verdict')} needs a blocking issue or a contradicted verification")
    if r.get("verdict") == "accept" and any(v.get("status") == "contradicted" for v in vers):
        errs.append("verdict accept but a verification is contradicted: use revise (fixable reporting error) or reject")
    if vers and all(v.get("status") == "could_not_verify" for v in vers) and r.get("confidence", 0) > 2:
        errs.append("confidence above 2 but no verification succeeded (all could_not_verify)")
    for n, v in enumerate(vers):
        if v.get("kind") == "trace" and not v.get("source"):
            errs.append(f"verifications[{n}]: a trace must name its source (file:line and equation or reference)")
        if v.get("kind") == "rerun":
            if not r.get("intake", {}).get("rerun_budget"):
                errs.append(f"verifications[{n}]: rerun without intake.rerun_budget; reruns need the caller's explicit permission")
            if not v.get("rerun_dir"):
                errs.append(f"verifications[{n}]: rerun must record rerun_dir")
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
    intake = r.get("intake", {})
    if intake.get("criteria_source") in ("protocol", "dossier") and not intake.get("criteria_ref"):
        errs.append(f"criteria_source {intake.get('criteria_source')} needs criteria_ref (protocol file and hash, or dossier entry)")
    if r.get("ensemble_of"):
        ensemble_rules(r, path, errs)
    elif r.get("dismissed") or any(i.get("merged_from") for i in issues):
        errs.append("dismissed / merged_from are only for a merged review (set ensemble_of)")
    if r.get("packs") or any(x.get("checklist_item") for x in issues + vers):
        packs_used_rules(r, errs, load_packs())
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
    if any(l.get("found_via") == "ripperdoc_search" for l in d.get("literature", [])) and not d.get("literature_search"):
        errs.append("literature found by ripperdoc_search but no literature_search record (searches run only when the caller asks)")


def main():
    if len(sys.argv) in (2, 3) and sys.argv[1] == "packs":
        d = sys.argv[2] if len(sys.argv) == 3 else PACKS_DIR
        answers = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "evals", "answers.json")
        cases = set(json.load(open(answers))["cases"]) if os.path.exists(answers) else None
        packs, errs = load_packs(d), []
        if not packs: errs.append(f"no packs in {d}")
        pack_rules(packs, errs, cases)
        if errs:
            print("\n".join(errs)); sys.exit(1)
        print(f"valid packs: {', '.join(packs)}"); return
    if len(sys.argv) != 3 or sys.argv[1] not in ("review", "dossier"):
        print(__doc__); sys.exit(2)
    kind, path = sys.argv[1:]
    try:
        data = load_review(path)
    except ValueError as e:
        print(e if not isinstance(e, json.JSONDecodeError) else f"invalid JSON: {e}"); sys.exit(1)
    errs = []
    check(data, json.load(open(os.path.join(SCHEMA_DIR, f"{kind}.schema.json"))), "$", errs)
    review_rules(data, errs, path) if kind == "review" else dossier_rules(data, errs)
    if errs:
        print("\n".join(errs)); sys.exit(1)
    print(f"valid {kind}: {path}")


if __name__ == "__main__":
    main()
