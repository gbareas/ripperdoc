"""Consistency checks on the eval cases themselves (stdlib only).

A clean case must be internally consistent, or a good reviewer is right to block it and the
benchmark counts that as a false block. These tests pin the two inconsistencies found by the
M0 baseline (case08 noise figure, case09 baseline varying by seed) and check the baseline file.
"""
import csv, json, os, re, statistics, unittest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
CASES = os.path.join(ROOT, "evals", "cases")


def findings(case):
    return open(os.path.join(CASES, case, "FINDINGS.md")).read()


class CleanCases(unittest.TestCase):
    def test_case08_noise_figure_matches_data(self):
        s = json.load(open(os.path.join(CASES, "case08", "psd_summary.json")))
        noise = s["time_domain_variance"] - 2.0 ** 2 / 2   # variance minus the power of the nominal 2.0 V line
        m = re.search(r"integrates to about ([0-9.]+) V²", findings("case08"))
        self.assertIsNotNone(m, "case08 write-up must state the broadband noise power")
        self.assertAlmostEqual(float(m.group(1)), noise, delta=0.15 * noise)
        self.assertLess(abs(noise - 0.3 ** 2) / 0.3 ** 2, 0.25, "noise should match the 0.3 V rms spec")

    def test_case09_numbers_match_results_and_baseline_is_per_seed(self):
        rows = list(csv.DictReader(open(os.path.join(CASES, "case09", "results.csv"))))
        model = [float(r["model_acc"]) for r in rows]
        base = [float(r["baseline_acc"]) for r in rows]
        text = findings("case09")
        self.assertIn(f"{statistics.mean(model):.3f}", text)
        self.assertIn(f"{statistics.mean(base):.3f}", text)
        diffs = [m - b for m, b in zip(model, base)]
        self.assertTrue(all(d > 0 for d in diffs))
        self.assertIn(f"+{100 * min(diffs):.1f} points", text)
        if len(set(base)) > 1:  # a single fixed production model would score the same on every seed
            self.assertRegex(text, r"retrained .*each of the same 5 seeds")


class Baselines(unittest.TestCase):
    def test_baselines_cover_every_case(self):
        answers = json.load(open(os.path.join(ROOT, "evals", "answers.json")))["cases"]
        folder = os.path.join(ROOT, "evals", "baselines")
        for name in sorted(os.listdir(folder)):
            b = json.load(open(os.path.join(folder, name)))
            self.assertEqual(sorted(b["cases"]), sorted(answers), name)
            for case, r in b["cases"].items():
                runs = r["runs"]
                self.assertEqual(len(runs), b["config"]["repeats"], f"{name} {case}")
                top = max(set(runs), key=runs.count)
                self.assertEqual(r["majority"], top, f"{name} {case}")
                self.assertGreaterEqual(runs.count(top), 2, f"{name} {case}")


if __name__ == "__main__":
    unittest.main()
