"""Dossier validation and rendering."""
import copy, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
VAL = os.path.join(ROOT, "bin", "validate.py")
RENDER = os.path.join(ROOT, "bin", "render_dossier.py")
SCHEMA_VERSION = json.load(open(os.path.join(ROOT, "schema", "dossier.schema.json")))["properties"]["schema_version"].get("const", 1)

LIT = {"key": "welch1967", "citation": "Welch 1967", "claim": "averaged periodograms", "relevance": "PSD method",
       "found_via": "producer_bib", "read_by_ripperdoc": "citation_only"}
BASE = {
    "schema_version": SCHEMA_VERSION, "updated": "2026-11-20",
    "project": {"name": "bench", "root": "/work/bench", "goal": "calibrate the sensor", "research_questions": ["is the line clean?"]},
    "sources_read": [{"path": "README.md", "kind": "readme", "mtime": "2026-11-19T10:00:00"}],
    "hypotheses": [{"id": "H1", "statement": "no power outside 50 Hz", "origin": "stated", "status": "open", "pre_registered": False, "source": "README.md:3"}],
    "work_done": [{"id": "W1", "what": "PSD", "status": "complete", "source": "FINDINGS.md", "review": "not_reviewed", "tests_hypotheses": ["H1"]}],
    "literature": [LIT], "conventions": [], "locations": [], "risks": [], "gaps": [],
}


class Dossier(unittest.TestCase):
    def run_on(self, d, render=False):
        with tempfile.TemporaryDirectory() as tmp:
            rd = os.path.join(tmp, "ripperdoc_reviews"); os.makedirs(rd)
            p = os.path.join(rd, "dossier.json"); json.dump(d, open(p, "w"))
            v = subprocess.run([sys.executable, VAL, "dossier", p], capture_output=True, text=True)
            md = None
            if render and v.returncode == 0:
                subprocess.run([sys.executable, RENDER, p], check=True, capture_output=True)
                md = open(os.path.join(rd, "DOSSIER.md")).read()
            return v, md

    def test_base_valid_and_renders(self):
        v, md = self.run_on(BASE, render=True)
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertIn("No web literature search", md)

    def test_search_results_need_a_search_record(self):
        d = copy.deepcopy(BASE)
        d["literature"].append(dict(LIT, key="x2024", found_via="ripperdoc_search"))
        self.assertEqual(self.run_on(d)[0].returncode, 1)
        d["literature_search"] = {"date": "2026-11-20", "queries": ["periodogram normalisation one-sided"]}
        v, md = self.run_on(d, render=True)
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertIn("periodogram normalisation", md)

    def test_unknown_hypothesis_fails(self):
        d = copy.deepcopy(BASE)
        d["work_done"][0]["tests_hypotheses"] = ["H9"]
        self.assertEqual(self.run_on(d)[0].returncode, 1)


if __name__ == "__main__":
    unittest.main()
