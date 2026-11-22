#!/usr/bin/env python3
"""Stand-in for `claude -p ... --agent ripperdoc` in gate tests. Writes a review the way Ripperdoc would.

Reads the prompt (argv after -p), appends it to $FAKE_PROMPTS, and writes:
  member a/b -> <date>_<slug>_r<n>_<id>.md, merge -> <date>_<slug>_r<n>.md with ensemble_of, single -> <date>_<slug>_r<n>.md
Verdict and confidence come from $FAKE_VERDICT (accept|revise) and $FAKE_CONFIDENCE. $FAKE_NOWRITE=1 writes nothing.
$FAKE_TOUCH=<file> appends to that file (simulates the artifacts changing during the review).
"""
import copy, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from test_validate import BASE, BLOCKING  # noqa: E402

text = sys.argv[sys.argv.index("-p") + 1]
if os.environ.get("FAKE_PROMPTS"):
    with open(os.environ["FAKE_PROMPTS"], "a") as f:
        f.write(json.dumps({"prompt": text, "argv": sys.argv[1:], "gate_env": os.environ.get("RIPPERDOC_GATE_ACTIVE")}) + "\n")
if os.environ.get("FAKE_TOUCH"):
    open(os.environ["FAKE_TOUCH"], "a").write("changed\n")
if os.environ.get("FAKE_NOWRITE"):
    sys.exit(0)
slug = re.search(r"[Ss]lug:? `?([a-z0-9-]+)`?", text).group(1)
rnd = int(re.search(r"[Rr]ound:? (\d+)", text).group(1))
rdir = re.search(r"[Rr]eview directory:? \./([^\s]+?)/", text).group(1)
os.makedirs(rdir, exist_ok=True)
verdict = os.environ.get("FAKE_VERDICT", "accept")
conf = int(os.environ.get("FAKE_CONFIDENCE", "4"))


def review(verdict=verdict, **extra):
    r = copy.deepcopy(BASE)
    r.update(slug=slug, round=rnd, verdict=verdict, confidence=conf,
             worklog=[f"r{i}: x" for i in range(1, rnd + 1)])
    if rnd > 1:
        r.update(previous_issues=[{"id": "R1-01", "status": "resolved"}], keep_or_revert="keep")
    if verdict != "accept":
        r.update(issues=[dict(BLOCKING, id=f"R{rnd}-01")], stop=False, stop_reason="continue",
                 actions={"do": ["add the control run"], "revise": [], "discard": []})
    r.update(extra)
    return r


def write(name, r):
    open(os.path.join(rdir, name), "w").write("## Reasoning\nfake\n\n## Actions\nnone\n\n```json\n" + json.dumps(r, indent=1) + "\n```\n")


m = re.search(r"ensemble member `([ab])`", text)
if m:
    v = "revise" if os.environ.get("FAKE_DISMISS") and m.group(1) == "b" else verdict
    write(f"2026-11-22_{slug}_r{rnd}_{m.group(1)}.md", review(v, reviewer=m.group(1)))
elif text.startswith("Ensemble merge"):
    members = re.search(r"Member reports: (.*?)\. Follow", text).group(1).split(", ")
    r = review(ensemble_of=[os.path.relpath(p, rdir) for p in members])
    if verdict != "accept":
        r["issues"][0]["merged_from"] = ["a:" + r["issues"][0]["id"], "b:" + r["issues"][0]["id"]]
    if os.environ.get("FAKE_DISMISS"):
        r.update(dismissed=[{"ref": "b:R%d-01" % rnd, "reason": "checked: not a real problem"}])
    write(f"2026-11-22_{slug}_r{rnd}.md", r)
else:
    write(f"2026-11-22_{slug}_r{rnd}.md", review())
