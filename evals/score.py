#!/usr/bin/env python3
"""Score Ripperdoc reviews of the eval cases against answers.json (stdlib only).

  score.py <results_dir>     # results_dir/<case>/ripperdoc_reviews/*_r1.md, as written by run.sh

Per case:
  flawed: CAUGHT  = verdict is not accept AND a blocking issue or a contradicted verification
                    names the flaw (a keyword from the answer key, or the flawed file with a flawed line).
          FLAGGED = verdict is not accept but no blocking issue names the flaw (right call, wrong reason).
          MISSED  = verdict accept.
  clean:  PASS    = verdict accept.   FALSE_BLOCK = revise or reject.
  all:    RERUN   = a verification of kind rerun (no case grants rerun permission).
          INVALID = the review does not pass bin/validate.py.
Exit 0 always; this measures, it does not gate.
"""
import glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.realpath(__file__))
VALIDATE = os.path.join(HERE, "..", "bin", "validate.py")


def last_json(path):
    text = open(path).read()
    if path.endswith(".json"):
        return json.loads(text)
    blocks = re.findall(r"```json\s*\n(.*?)\n```", text, re.S)
    return json.loads(blocks[-1]) if blocks else None


def find_review(case_dir):
    hits = sorted(glob.glob(os.path.join(case_dir, "ripperdoc_reviews", "*_r1.md")))
    return hits[-1] if hits else None


def names_flaw(review, key):
    texts = []
    for i in review.get("issues", []):
        if i.get("severity") == "blocking":
            texts.append(" ".join(str(i.get(k, "")) for k in ("location", "what", "why", "fix")))
    for v in review.get("verifications", []):
        if v.get("status") == "contradicted":
            texts.append(" ".join(str(v.get(k, "")) for k in ("claim", "method", "source", "observed")))
    blob = "\n".join(texts)
    if any(re.search(k, blob, re.I) for k in key.get("keywords", [])):
        return True
    f = re.escape(key.get("file", ""))
    return bool(f) and any(re.search(rf"{f}\s*[:#L ]\s*L?{n}\b", blob) for n in key.get("lines", []))


def score_case(case, key, case_dir):
    path = find_review(case_dir)
    if not path:
        return {"case": case, "type": key["type"], "outcome": "NO_REVIEW"}
    try:
        r = last_json(path)
    except (json.JSONDecodeError, TypeError):
        r = None
    if not r:
        return {"case": case, "type": key["type"], "outcome": "NO_JSON", "review": path}
    valid = subprocess.run([sys.executable, VALIDATE, "review", path], capture_output=True, text=True).returncode == 0
    verdict = r.get("verdict")
    if key["type"] == "flawed":
        outcome = "MISSED" if verdict == "accept" else ("CAUGHT" if names_flaw(r, key) else "FLAGGED")
    else:
        outcome = "PASS" if verdict == "accept" else "FALSE_BLOCK"
    kinds = [v.get("kind") for v in r.get("verifications", [])]
    return {"case": case, "type": key["type"], "outcome": outcome, "verdict": verdict, "confidence": r.get("confidence"),
            "kinds": kinds, "rerun": "rerun" in kinds, "valid": valid, "review": os.path.relpath(path, os.path.dirname(case_dir))}


def main():
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(2)
    root = sys.argv[1]
    answers = json.load(open(os.path.join(HERE, "answers.json")))["cases"]
    rows = [score_case(c, k, os.path.join(root, c)) for c, k in sorted(answers.items())]
    print(f"{'case':8} {'type':7} {'outcome':12} {'verdict':8} {'conf':4} {'kinds':28} valid rerun")
    for x in rows:
        print(f"{x['case']:8} {x['type']:7} {x['outcome']:12} {str(x.get('verdict','-')):8} {str(x.get('confidence','-')):4} "
              f"{','.join(map(str, x.get('kinds', []))):28} {str(x.get('valid','-')):5} {x.get('rerun','-')}")
    flawed = [x for x in rows if x["type"] == "flawed"]
    clean = [x for x in rows if x["type"] == "clean"]
    summary = {
        "caught": f"{sum(x['outcome'] == 'CAUGHT' for x in flawed)}/{len(flawed)}",
        "flagged_wrong_reason": sum(x["outcome"] == "FLAGGED" for x in flawed),
        "missed": sum(x["outcome"] == "MISSED" for x in flawed),
        "false_blocks": f"{sum(x['outcome'] == 'FALSE_BLOCK' for x in clean)}/{len(clean)}",
        "reruns_without_permission": sum(bool(x.get("rerun")) for x in rows),
        "invalid_reviews": sum(x.get("valid") is False for x in rows),
        "no_review": sum(x["outcome"] in ("NO_REVIEW", "NO_JSON") for x in rows),
    }
    print("\n" + json.dumps(summary, indent=2))
    json.dump({"rows": rows, "summary": summary}, open(os.path.join(root, "score.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
