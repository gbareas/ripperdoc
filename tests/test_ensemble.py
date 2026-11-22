"""Ensemble merge: bin/merge_reviews.py and the validator's merged-review rules."""
import copy, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
from test_validate import BASE, BLOCKING  # noqa: E402

MERGE = os.path.join(ROOT, "bin", "merge_reviews.py")
VAL = os.path.join(ROOT, "bin", "validate.py")


def member(rid, verdict, issues=(), conf=4, contradicted=False):
    r = copy.deepcopy(BASE)
    r.update(reviewer=rid, verdict=verdict, confidence=conf, issues=list(issues))
    if contradicted:
        r["verifications"][0].update(status="contradicted", observed="0.6")
    if verdict != "accept":
        r.update(stop=False, stop_reason="continue")
    return r


class Ensemble(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "ripperdoc_reviews")
        os.makedirs(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, r):
        p = os.path.join(self.dir, name)
        json.dump(r, open(p, "w"))
        return p

    def validate(self, p):
        return subprocess.run([sys.executable, VAL, "review", p], capture_output=True, text=True)

    def merge(self, *members):
        paths = [self.write(f"m_{m['reviewer']}.json", m) for m in members]
        out = os.path.join(self.dir, "merged.json")
        subprocess.run([sys.executable, MERGE, out, *paths], check=True, capture_output=True, text=True)
        return out, json.load(open(out))

    def test_members_validate(self):
        a = member("a", "revise", [BLOCKING])
        self.assertEqual(self.validate(self.write("a.json", a)).returncode, 0)

    def test_draft_keeps_lone_blocking_issue_and_most_severe_verdict(self):
        out, d = self.merge(member("a", "accept", conf=5), member("b", "revise", [BLOCKING], conf=3))
        self.assertEqual(d["verdict"], "revise")
        self.assertEqual(d["confidence"], 3)
        self.assertEqual(d["issues"][0]["merged_from"], ["b:R1-01"])
        self.assertTrue(any("verdicts differ" in x for x in d["reviewer_disagreements"]))
        p = self.validate(out)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_draft_carries_packs_and_checklist_items(self):
        a = member("a", "revise", [dict(BLOCKING, checklist_item="physics.units")])
        a["packs"] = [{"id": "research-core", "version": "1.0.0"}, {"id": "physics", "version": "1.0.0"}]
        b = member("b", "accept")
        b["packs"] = [{"id": "research-core", "version": "1.0.0"}]
        out, d = self.merge(a, b)
        self.assertEqual(sorted(p["id"] for p in d["packs"]), ["physics", "research-core"])
        self.assertEqual(d["issues"][0]["checklist_item"], "physics.units")
        p = self.validate(out)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_dropping_a_blocking_issue_silently_fails(self):
        out, d = self.merge(member("a", "accept"), member("b", "revise", [BLOCKING]))
        d.update(issues=[], verdict="accept", stop=True, stop_reason="no_blocking_issues")
        json.dump(d, open(out, "w"))
        p = self.validate(out)
        self.assertEqual(p.returncode, 1)
        self.assertIn("b:R1-01", p.stdout)

    def test_dismissing_with_reason_passes(self):
        out, d = self.merge(member("a", "accept"), member("b", "revise", [BLOCKING]))
        d.update(issues=[], verdict="accept", stop=True, stop_reason="no_blocking_issues",
                 dismissed=[{"ref": "b:R1-01", "reason": "traced psd.py:12; normalisation is applied on line 13"}])
        json.dump(d, open(out, "w"))
        p = self.validate(out)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_undismissed_contradiction_blocks_accept(self):
        out, d = self.merge(member("a", "accept"), member("b", "reject", [BLOCKING], contradicted=True))
        d.update(issues=[], verdict="accept", stop=True, stop_reason="no_blocking_issues", verifications=[BASE["verifications"][0]],
                 dismissed=[{"ref": "b:R1-01", "reason": "duplicate of nothing"}])
        json.dump(d, open(out, "w"))
        p = self.validate(out)
        self.assertEqual(p.returncode, 1)
        self.assertIn("b:V1", p.stdout)

    def test_merged_confidence_cannot_exceed_members(self):
        out, d = self.merge(member("a", "revise", [BLOCKING], conf=3), member("b", "revise", [BLOCKING], conf=2))
        d["confidence"] = 5
        json.dump(d, open(out, "w"))
        self.assertEqual(self.validate(out).returncode, 1)

    def test_unknown_reference_fails(self):
        out, d = self.merge(member("a", "revise", [BLOCKING]), member("b", "revise", [BLOCKING]))
        d["issues"][0]["merged_from"].append("c:R1-09")
        json.dump(d, open(out, "w"))
        self.assertIn("c:R1-09", self.validate(out).stdout)

    def test_merged_from_outside_a_merge_fails(self):
        r = member("a", "revise", [dict(BLOCKING, merged_from=["a:R1-01"])])
        self.assertEqual(self.validate(self.write("x.json", r)).returncode, 1)

    def test_draft_must_go_to_review_dir(self):
        a = self.write("a.json", member("a", "accept"))
        p = subprocess.run([sys.executable, MERGE, os.path.join(self.tmp.name, "out.json"), a, a], capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)


class Criteria(unittest.TestCase):
    def test_protocol_criteria_need_a_ref(self):
        r = copy.deepcopy(BASE)
        r["intake"]["criteria_source"] = "protocol"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(r, f)
        try:
            self.assertEqual(subprocess.run([sys.executable, VAL, "review", f.name], capture_output=True).returncode, 1)
            r["intake"]["criteria_ref"] = "protocols/psd_v1.yaml sha256:ab12"
            json.dump(r, open(f.name, "w"))
            self.assertEqual(subprocess.run([sys.executable, VAL, "review", f.name], capture_output=True).returncode, 0)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
