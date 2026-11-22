"""Domain packs: manifests and checklists in packs/, and the validator's rules for reviews that use them."""
import copy, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "bin"))
from test_validate import BASE, BLOCKING, validate  # noqa: E402
import validate as V  # noqa: E402

VAL = os.path.join(ROOT, "bin", "validate.py")
PACKS = V.load_packs()


def version(pid):
    return PACKS[pid]["manifest"]["version"]


def with_packs(*ids, **changes):
    r = copy.deepcopy(BASE)
    r["packs"] = [{"id": i, "version": version(i)} for i in ids]
    r.update(changes)
    return r


def blocking(item):
    return dict(BLOCKING, checklist_item=item)


def revise(r):
    r.update(verdict="revise", stop=False, stop_reason="continue")
    return r


class Repository(unittest.TestCase):
    def test_shipped_packs_are_valid(self):
        p = subprocess.run([sys.executable, VAL, "packs"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_expected_packs_and_items(self):
        self.assertTrue({"research-core", "physics", "ml"} <= set(PACKS))
        self.assertIn("physics.jacobian", PACKS["physics"]["items"])
        self.assertIn("ml.split-leakage", PACKS["ml"]["items"])
        self.assertIn("research-core.controls", PACKS["research-core"]["items"])

    def test_every_eval_case_is_covered_by_a_domain_pack(self):
        cases = set(json.load(open(os.path.join(ROOT, "evals", "answers.json")))["cases"])
        domain = {c for pid, p in PACKS.items() if pid != "research-core" for c in p["manifest"]["eval_cases"]}
        self.assertEqual(domain, cases)

    def test_experiment_design_moved_out_of_skill(self):
        skill = open(os.path.join(ROOT, "SKILL.md")).read()
        self.assertNotIn("### Experiment design", skill)
        self.assertIn("packs/research-core/checklist.md", skill)
        for label in ("Controls", "Baselines", "Confounds", "Statistical power", "Reproducibility", "Pre-specification"):
            self.assertIn(f"**{label}.**", open(os.path.join(ROOT, "packs", "research-core", "checklist.md")).read())


class BrokenPacks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dir = os.path.join(self.tmp, "packs")
        shutil.copytree(os.path.join(ROOT, "packs"), self.dir)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def errors(self):
        errs = []
        V.pack_rules(V.load_packs(self.dir), errs, case_ids=set(json.load(open(os.path.join(ROOT, "evals", "answers.json")))["cases"]))
        return errs

    def edit(self, pid, **changes):
        p = os.path.join(self.dir, pid, "pack.json")
        m = json.load(open(p)); m.update(changes); json.dump(m, open(p, "w"))

    def test_copy_is_valid(self):
        self.assertEqual(self.errors(), [])

    def test_id_must_match_folder(self):
        self.edit("physics", id="phys")
        self.assertTrue(any("folder name" in e for e in self.errors()))

    def test_unknown_extends(self):
        self.edit("ml", extends=["research-core", "stats"])
        self.assertTrue(any("unknown pack stats" in e for e in self.errors()))

    def test_unknown_eval_case(self):
        self.edit("ml", eval_cases=["case04", "case99"])
        self.assertTrue(any("case99" in e for e in self.errors()))

    def test_bad_version_and_extra_field(self):
        self.edit("physics", version="1.0", owner="x")
        errs = self.errors()
        self.assertTrue(any("version" in e for e in errs), errs)
        self.assertTrue(any("unknown field 'owner'" in e for e in errs), errs)

    def test_item_prefix_and_duplicates(self):
        p = os.path.join(self.dir, "ml", "checklist.md")
        open(p, "a").write("\n### physics.units\nx\n\n### ml.variance\ny\n")
        errs = self.errors()
        self.assertTrue(any("must start with 'ml.'" in e for e in errs), errs)
        self.assertTrue(any("duplicate checklist item" in e for e in errs), errs)


class Reviews(unittest.TestCase):
    def ok(self, r):
        code, out = validate(r)
        self.assertEqual(code, 0, out)

    def bad(self, r, text):
        code, out = validate(r)
        self.assertEqual(code, 1, "validator accepted it")
        self.assertIn(text, out)

    def test_review_without_packs_still_valid(self):
        self.ok(BASE)  # reviews made before packs existed

    def test_packs_with_tagged_issue(self):
        self.ok(revise(with_packs("research-core", "physics", issues=[blocking("physics.jacobian")])))

    def test_tagged_verification(self):
        r = with_packs("research-core", "ml")
        r["verifications"][0]["checklist_item"] = "ml.metric-definition"
        self.ok(r)

    def test_item_of_unlisted_pack(self):
        self.bad(revise(with_packs("research-core", issues=[blocking("physics.units")])), "not in packs")

    def test_item_without_any_packs(self):
        self.bad(revise(dict(copy.deepcopy(BASE), issues=[blocking("ml.variance")])), "not in packs")

    def test_unknown_item(self):
        self.bad(revise(with_packs("research-core", "physics", issues=[blocking("physics.vibes")])), "does not exist")

    def test_unknown_pack(self):
        r = with_packs("research-core")
        r["packs"].append({"id": "chemistry", "version": "1.0.0"})
        self.bad(r, "unknown pack chemistry")

    def test_version_mismatch(self):
        r = with_packs("research-core", "physics")
        r["packs"][1]["version"] = "0.9.0"
        self.bad(r, "does not match the installed")

    def test_extended_pack_must_be_listed(self):
        self.bad(with_packs("physics"), "extends research-core")

    def test_listed_twice(self):
        r = with_packs("research-core", "research-core")
        self.bad(r, "listed twice")

    def test_malformed_item_id(self):
        self.bad(revise(with_packs("research-core", issues=[blocking("Research Core: controls")])), "does not match")


if __name__ == "__main__":
    unittest.main()
