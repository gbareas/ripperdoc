"""Tests for evals/score.py on hand-written reviews. Run: python3 -m unittest discover -s tests"""
import copy, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
from test_validate import BASE, BLOCKING  # noqa: E402

SCORE = os.path.join(ROOT, "evals", "score.py")


def review(verdict="accept", issues=(), kind="trace", conf=4):
    r = copy.deepcopy(BASE)
    r.update(verdict=verdict, issues=list(issues), confidence=conf)
    r["verifications"][0]["kind"] = kind
    if verdict != "accept":
        r.update(stop=False, stop_reason="continue")
    return r


def write(root, case, r):
    d = os.path.join(root, case, "ripperdoc_reviews")
    os.makedirs(d)
    with open(os.path.join(d, "2026-11-20_eval_r1.md"), "w") as f:
        f.write("## Reasoning\n\nx\n\n```json\n" + json.dumps(r) + "\n```\n")


class Score(unittest.TestCase):
    def test_outcomes(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "case01", review("reject", [dict(BLOCKING, what="PSD lacks the 1/(fs*N) normalisation")]))
            write(root, "case02", review("revise", [dict(BLOCKING, what="grid too coarse")]))
            write(root, "case03", review("accept"))
            write(root, "case07", review("reject", [dict(BLOCKING, location="line_flux.py:9", what="wrong array")]))
            write(root, "case08", review("accept"))
            write(root, "case09", review("revise", [BLOCKING]))
            write(root, "case10", review("accept", kind="rerun"))
            subprocess.run([sys.executable, SCORE, root], capture_output=True, text=True, check=True)
            rows = {x["case"]: x for x in json.load(open(os.path.join(root, "score.json")))["rows"]}
            self.assertEqual(rows["case01"]["outcome"], "CAUGHT")
            self.assertEqual(rows["case02"]["outcome"], "FLAGGED")
            self.assertEqual(rows["case03"]["outcome"], "MISSED")
            self.assertEqual(rows["case07"]["outcome"], "CAUGHT")
            self.assertEqual(rows["case08"]["outcome"], "PASS")
            self.assertEqual(rows["case09"]["outcome"], "FALSE_BLOCK")
            self.assertTrue(rows["case10"]["rerun"])
            self.assertFalse(rows["case10"]["valid"])  # rerun without rerun_budget fails the validator
            self.assertEqual(rows["case04"]["outcome"], "NO_REVIEW")


class Cases(unittest.TestCase):
    def test_every_case_has_findings_and_an_answer(self):
        answers = json.load(open(os.path.join(ROOT, "evals", "answers.json")))["cases"]
        cases = sorted(os.listdir(os.path.join(ROOT, "evals", "cases")))
        self.assertEqual(cases, sorted(answers))
        for c in cases:
            self.assertTrue(os.path.exists(os.path.join(ROOT, "evals", "cases", c, "FINDINGS.md")), c)
            key = answers[c]
            if key["type"] == "flawed":
                self.assertTrue(os.path.exists(os.path.join(ROOT, "evals", "cases", c, key["file"])), c)

    def test_no_answer_key_inside_cases(self):
        for dirpath, _, files in os.walk(os.path.join(ROOT, "evals", "cases")):
            self.assertNotIn("answers.json", files)


if __name__ == "__main__":
    unittest.main()
