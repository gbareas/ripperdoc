"""Tests for bin/validate.py review rules. Run: python3 -m unittest discover -s tests"""
import copy, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
VAL = os.path.join(ROOT, "bin", "validate.py")

BASE = {
    "round": 1, "slug": "psd-peak", "date": "2026-11-20",
    "intake": {"goal": "g", "claim": "c", "acceptance_criteria": ["a"], "criteria_source": "caller", "artifacts_missing": []},
    "verifications": [{"kind": "trace", "claim": "peak PSD = 2.0", "method": "followed fig2 -> psd.npy -> analysis.py",
                       "source": "analysis.py:41, one-sided periodogram, Parseval normalisation",
                       "reported": "2.0", "observed": "formula correct", "status": "confirmed"}],
    "verdict": "accept", "confidence": 4, "confidence_reason": "traced the key number to a correct equation",
    "issues": [], "actions": {"do": [], "revise": [], "discard": []},
    "insights": [], "questions": [], "previous_issues": [], "keep_or_revert": "n/a",
    "stop": True, "stop_reason": "no_blocking_issues", "worklog": ["r1: traced psd peak, accept"],
}
BLOCKING = {"id": "R1-01", "severity": "blocking", "category": "evidence", "what": "w", "why": "y", "fix": "f", "question": "q"}


def validate(review):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(review, f)
    try:
        p = subprocess.run([sys.executable, VAL, "review", f.name], capture_output=True, text=True)
        return p.returncode, p.stdout
    finally:
        os.unlink(f.name)


def make(**changes):
    r = copy.deepcopy(BASE)
    for k, v in changes.items():
        r[k] = v
    return r


def ver(**changes):
    v = copy.deepcopy(BASE["verifications"][0])
    v.update(changes)
    return [v]


class Review(unittest.TestCase):
    def ok(self, r):
        code, out = validate(r)
        self.assertEqual(code, 0, out)

    def bad(self, r, msg=""):
        code, out = validate(r)
        self.assertEqual(code, 1, f"validator accepted it {msg}")
        return out

    def test_base_is_valid(self):
        self.ok(BASE)

    # verdict vs verification outcome
    def test_accept_with_contradicted_verification_fails(self):
        self.bad(make(verifications=ver(kind="recompute", status="contradicted", reported="0.9", observed="0.6")))

    def test_revise_with_contradicted_verification_passes(self):
        self.ok(make(verdict="revise", confidence=3, stop=False, stop_reason="continue",
                     verifications=ver(kind="recompute", status="contradicted", reported="0.9", observed="0.6")))

    def test_accept_with_blocking_issue_fails(self):
        self.bad(make(issues=[BLOCKING]))

    def test_revise_without_blocking_or_contradiction_fails(self):
        self.bad(make(verdict="revise", stop=False, stop_reason="continue"))

    # confidence vs what was actually verified
    def test_high_confidence_with_nothing_verified_fails(self):
        self.bad(make(verifications=ver(status="could_not_verify")))

    def test_low_confidence_with_nothing_verified_passes(self):
        self.ok(make(confidence=2, verifications=ver(status="could_not_verify")))

    # verification kinds
    def test_kind_required(self):
        v = ver(); del v[0]["kind"]
        self.bad(make(verifications=v))

    def test_unknown_kind_fails(self):
        self.bad(make(verifications=ver(kind="vibes")))

    def test_trace_needs_source(self):
        v = ver(); del v[0]["source"]
        self.bad(make(verifications=v))

    def test_rerun_without_budget_fails(self):
        self.bad(make(verifications=ver(kind="rerun", rerun_dir="/tmp/ripperdoc/run-1")))

    def test_rerun_with_budget_passes(self):
        r = make(verifications=ver(kind="rerun", rerun_dir="/tmp/ripperdoc/run-1"))
        r["intake"]["rerun_budget"] = "caller: rerun eval.py allowed, max 20 min"
        self.ok(r)

    def test_rerun_needs_rerun_dir(self):
        r = make(verifications=ver(kind="rerun"))
        r["intake"]["rerun_budget"] = "max 20 min"
        self.bad(r)

    # existing rules still hold
    def test_round_two_needs_previous_issues(self):
        self.bad(make(round=2, keep_or_revert="keep", worklog=["r1", "r2"]))

    def test_stop_and_reason_must_agree(self):
        self.bad(make(stop=False))

    def test_duplicate_issue_ids_fail(self):
        nb = dict(BLOCKING, severity="nice_to_have")
        self.bad(make(issues=[nb, nb]))

    def test_markdown_report_uses_last_json_block(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("## Reasoning\n\n```json\n{}\n```\n\n## Review\n\n```json\n" + json.dumps(BASE) + "\n```\n")
        try:
            p = subprocess.run([sys.executable, VAL, "review", f.name], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
