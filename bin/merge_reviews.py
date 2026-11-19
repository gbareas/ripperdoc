#!/usr/bin/env python3
"""Draft a merged review from independent ensemble members (stdlib only).

  merge_reviews.py <out.json> <member_a.md> <member_b.md> [...]

Mechanical floor for Ripperdoc's ensemble mode, so nothing is averaged away:
  - every blocking issue of every member is carried (ids renumbered, merged_from = <reviewer>:<id>),
  - nice-to-have issues raised by one member only are left out (the merge step may re-add them),
  - verdict = the most severe member verdict, confidence = the lowest,
  - verifications: contradicted ones first, then confirmed, then the rest (max 3),
  - reviewer_disagreements lists differing verdicts and every blocking issue only one member raised.
The draft is a starting point: the merge step dedupes issues (joining merged_from lists),
re-verifies disputed blocking issues, moves the ones that do not stand to `dismissed` with a
reason, and writes the final report. validate.py checks that every member blocking issue ends
up merged or dismissed.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from validate import SEVERITY, load_review  # noqa: E402

ORDER = {"contradicted": 0, "confirmed": 1, "could_not_verify": 2}


def main():
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(2)
    out, paths = sys.argv[1], sys.argv[2:]
    if "ripperdoc_reviews" not in os.path.realpath(out).split(os.sep):
        sys.exit("merge_reviews: the draft must be written inside a ripperdoc_reviews/ directory")
    members = [(p, load_review(p)) for p in paths]
    for p, m in members:
        if not m.get("reviewer"):
            sys.exit(f"merge_reviews: {p} has no reviewer id")
    first = members[0][1]
    rnd = first["round"]
    verdict = max((m["verdict"] for _, m in members), key=lambda v: SEVERITY[v])
    issues, n, disagreements = [], 0, []
    verdicts = {m["reviewer"]: m["verdict"] for _, m in members}
    if len(set(verdicts.values())) > 1:
        disagreements.append("verdicts differ: " + ", ".join(f"{k}={v}" for k, v in verdicts.items()))
    for _, m in members:
        for i in m.get("issues", []):
            if i.get("severity") != "blocking":
                continue
            n += 1
            j = {k: v for k, v in i.items() if k != "merged_from"}
            j["id"] = f"R{rnd}-{n:02d}"
            j["merged_from"] = [f"{m['reviewer']}:{i['id']}"]
            issues.append(j)
            disagreements.append(f"{m['reviewer']}:{i['id']} blocking, raised by {m['reviewer']} only (before dedupe): {i.get('what', '')[:120]}")
    vers = sorted(((m["reviewer"], v) for _, m in members for v in m.get("verifications", [])),
                  key=lambda x: ORDER.get(x[1].get("status"), 3))[:3]
    draft = {
        "round": rnd, "slug": first["slug"], "date": first["date"],
        "intake": first["intake"],
        "verifications": [dict(v, method=f"[{rid}] {v.get('method', '')}") for rid, v in vers],
        "verdict": verdict,
        "confidence": min(m["confidence"] for _, m in members),
        "confidence_reason": "draft: lowest member confidence; revise after re-verifying disputed points",
        "issues": issues,
        "actions": {k: sorted({a for _, m in members for a in m.get("actions", {}).get(k, [])}) for k in ("do", "revise", "discard")},
        "insights": [x for _, m in members for x in m.get("insights", [])][:3],
        "questions": sorted({q for _, m in members for q in m.get("questions", [])}),
        "previous_issues": first.get("previous_issues", []),
        "keep_or_revert": first.get("keep_or_revert", "n/a"),
        "stop": False, "stop_reason": "continue",
        "worklog": first.get("worklog", [])[:-1] + [f"r{rnd}: merged {len(members)} reviews ({', '.join(f'{k}={v}' for k, v in verdicts.items())})"],
        "ensemble_of": [os.path.relpath(os.path.realpath(p), os.path.dirname(os.path.realpath(out))) for p, _ in members],
        "dismissed": [],
        "reviewer_disagreements": disagreements,
    }
    if verdict == "accept":
        draft.update(stop=True, stop_reason="no_blocking_issues")
    json.dump(draft, open(out, "w"), indent=2)
    print(f"wrote {out}: verdict {verdict}, {len(issues)} blocking issue(s) carried, {len(disagreements)} disagreement(s)")


if __name__ == "__main__":
    main()
