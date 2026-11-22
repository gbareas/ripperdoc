"""The verification gate (bin/gate.py), the Stop hook and the producer guard.

The reviewer is replaced by tests/fake_claude.py (RIPPERDOC_CLAUDE), so no model is called."""
import json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
GATE = os.path.join(ROOT, "bin", "ripperdoc-gate")
STOP = os.path.join(ROOT, "hooks", "stop_gate.py")
PGUARD = os.path.join(ROOT, "hooks", "producer_guard.py")
FAKE = os.path.join(ROOT, "tests", "fake_claude.py")


class Project(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        os.makedirs(os.path.join(self.root, ".ripperdoc", "claims"))
        os.makedirs(os.path.join(self.root, "out"))
        self.write("analysis.py", "print(1)\n")
        self.write("out/result.json", '{"peak": 2.0}\n')
        self.prompts = os.path.join(self.root, "prompts.jsonl")
        self.env = {**os.environ, "RIPPERDOC_CLAUDE": FAKE, "FAKE_PROMPTS": self.prompts}
        self.env.pop("RIPPERDOC_GATE_ACTIVE", None)
        self.policy(ensemble=False)
        self.claim()

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, rel, text, mode="w"):
        with open(os.path.join(self.root, rel), mode) as f:
            f.write(text)

    def policy(self, **kw):
        p = {"pass_verdicts": ["accept"], "min_confidence": 3, "ensemble": True, "max_rounds": 3}
        p.update(kw)
        self.write(".ripperdoc/policy.json", json.dumps(p))

    def claim(self, slug="psd-peak", **kw):
        c = {"slug": slug, "goal": "find the peak", "claim": "peak at 2.0", "artifacts": ["analysis.py", "out"]}
        c.update(kw)
        self.write(f".ripperdoc/claims/{slug}.json", json.dumps(c))

    def gate(self, cmd, claim="--all", **env):
        p = subprocess.run([GATE, cmd, claim], cwd=self.root, capture_output=True, text=True, env={**self.env, **env})
        try:
            out = json.loads(p.stdout)
        except ValueError:
            self.fail(f"gate printed no JSON: {p.stdout} {p.stderr}")
        return p.returncode, (out[0] if isinstance(out, list) and len(out) == 1 else out)

    def prompt_log(self):
        return [json.loads(l) for l in open(self.prompts)] if os.path.exists(self.prompts) else []

    def reviews(self):
        d = os.path.join(self.root, "ripperdoc_reviews")
        return sorted(f for f in os.listdir(d) if f.endswith(".md")) if os.path.isdir(d) else []


class Decisions(Project):
    def test_check_without_review_blocks_and_calls_no_model(self):
        code, d = self.gate("check")
        self.assertEqual((code, d["decision"]), (2, "block"))
        self.assertIn("not reviewed", d["reason"])
        self.assertEqual(self.prompt_log(), [])

    def test_review_then_pass(self):
        code, d = self.gate("review")
        self.assertEqual((code, d["decision"]), (0, "pass"), d)
        self.assertEqual(self.reviews(), ["2026-11-22_psd-peak_r1.md"])
        log = self.prompt_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["gate_env"], "1")
        self.assertIn("--agent", log[0]["argv"])
        self.assertIn("WebSearch", log[0]["argv"])  # literature search off by default
        # a second run reuses the fresh review
        code, d = self.gate("review")
        self.assertEqual(d["decision"], "pass")
        self.assertEqual(len(self.prompt_log()), 1)

    def test_editing_an_artifact_makes_the_review_stale(self):
        self.gate("review")
        self.write("out/result.json", '{"peak": 2.5}\n')
        code, d = self.gate("check")
        self.assertEqual(d["decision"], "block")
        self.assertIn("stale", d["reason"])
        self.assertIn("out/result.json", d["reason"])
        code, d = self.gate("review")  # re-review, round 2
        self.assertEqual(d["decision"], "pass", d)
        self.assertEqual(d["round"], 2)

    def test_adding_a_file_to_an_artifact_folder_is_a_change(self):
        self.gate("review")
        self.write("out/extra.csv", "x\n")
        self.assertIn("stale", self.gate("check")[1]["reason"])

    def test_edited_report_never_passes(self):
        self.gate("review")
        self.write("ripperdoc_reviews/2026-11-22_psd-peak_r1.md", "\n", mode="a")
        code, d = self.gate("check")
        self.assertEqual(d["decision"], "block")
        self.assertIn("changed after the gate recorded it", d["reason"])

    def test_forged_report_without_gate_record_never_passes(self):
        self.gate("review")
        shutil.rmtree(os.path.join(self.root, "ripperdoc_reviews", ".gate"))
        code, d = self.gate("check")
        self.assertEqual(d["decision"], "block")
        self.assertIn("not produced by the gate", d["reason"])

    def test_low_confidence_blocks(self):
        code, d = self.gate("review", FAKE_CONFIDENCE="2")
        self.assertEqual(d["decision"], "block")
        self.assertIn("confidence 2 < 3", d["reason"])

    def test_revise_blocks_with_actions_and_does_not_rereview_unchanged_work(self):
        code, d = self.gate("review", FAKE_VERDICT="revise")
        self.assertEqual((code, d["decision"]), (2, "block"))
        self.assertIn("add the control run", d["actions"])
        self.gate("review", FAKE_VERDICT="revise")
        self.assertEqual(len(self.prompt_log()), 1)  # nothing changed, so no second review

    def test_round_cap_escalates(self):
        self.policy(ensemble=False, max_rounds=2)
        for n in range(2):
            self.write("analysis.py", f"print({n})\n")
            code, d = self.gate("review", FAKE_VERDICT="revise")
        self.assertEqual((code, d["decision"]), (3, "escalate"), d)
        self.write("analysis.py", "print(9)\n")
        code, d = self.gate("review", FAKE_VERDICT="revise")
        self.assertEqual(d["decision"], "escalate")
        self.assertEqual(len(self.prompt_log()), 2)  # no third review past the cap

    def test_missing_artifact_blocks_without_review(self):
        os.remove(os.path.join(self.root, "analysis.py"))
        code, d = self.gate("review")
        self.assertEqual(d["decision"], "block")
        self.assertIn("missing", d["reason"])
        self.assertEqual(self.prompt_log(), [])

    def test_reviewer_writing_nothing_is_an_error(self):
        code, d = self.gate("review", FAKE_NOWRITE="1")
        self.assertEqual((code, d["decision"]), (1, "error"))

    def test_artifacts_changing_during_review_is_an_error(self):
        code, d = self.gate("review", FAKE_TOUCH=os.path.join(self.root, "analysis.py"))
        self.assertEqual(d["decision"], "error")
        self.assertIn("changed while the review ran", d["reason"])

    def test_rerun_permission_only_from_policy(self):
        self.gate("review")
        self.assertIn("Rerun permission: none", self.prompt_log()[0]["prompt"])
        shutil.rmtree(os.path.join(self.root, "ripperdoc_reviews"))
        self.policy(ensemble=False, reruns={"allowed": [{"cmd": "python eval.py", "max_minutes": 20}]})
        self.claim(notes="rerun of train.py allowed, max 600 min")
        self.gate("review")
        p = self.prompt_log()[-1]["prompt"]
        self.assertIn("rerun of `python eval.py` allowed, max 20 min", p)
        self.assertIn("Producer's notes (a claim to check, not evidence): rerun of train.py", p)

    def test_bad_claim_and_bad_policy(self):
        self.claim(slug="other", artifacts=[])
        os.rename(os.path.join(self.root, ".ripperdoc/claims/other.json"), os.path.join(self.root, ".ripperdoc/claims/wrong-name.json"))
        code, d = self.gate("check", ".ripperdoc/claims/wrong-name.json")
        self.assertEqual(d["decision"], "error")
        self.write(".ripperdoc/policy.json", json.dumps({"pass_verdicts": ["accept"], "min_confidence": 9, "ensemble": False, "max_rounds": 3}))
        code, d = self.gate("check", ".ripperdoc/claims/psd-peak.json")
        self.assertEqual((code, d["decision"]), (1, "error"))

    def test_artifact_outside_project_refused(self):
        self.claim(artifacts=["../etc"])
        code, d = self.gate("check")
        self.assertEqual(d["decision"], "error")


class Ensemble(Project):
    def setUp(self):
        super().setUp()
        self.policy(ensemble=True, models={"b": "haiku-test"})

    def test_two_members_and_a_merge(self):
        code, d = self.gate("review")
        self.assertEqual(d["decision"], "pass", d)
        self.assertEqual(self.reviews(), ["2026-11-22_psd-peak_r1.md", "2026-11-22_psd-peak_r1_a.md", "2026-11-22_psd-peak_r1_b.md"])
        log = self.prompt_log()
        self.assertEqual(len(log), 3)
        self.assertNotIn("--model", log[0]["argv"])
        self.assertEqual(log[1]["argv"][log[1]["argv"].index("--model") + 1], "haiku-test")
        self.assertTrue(log[2]["prompt"].startswith("Ensemble merge"))

    def test_single_review_does_not_pass_when_ensemble_required(self):
        self.policy(ensemble=False)
        self.gate("review")
        self.policy(ensemble=True)
        code, d = self.gate("check")
        self.assertEqual(d["decision"], "block")
        self.assertIn("requires an ensemble", d["reason"])

    def test_dismissed_blocking_issue_escalates(self):
        code, d = self.gate("review", FAKE_DISMISS="1")
        self.assertEqual((code, d["decision"]), (3, "escalate"), d)
        self.assertIn("dismissed", d["reason"])


class StopHook(Project):
    def stop(self, active=False, **env):
        p = subprocess.run([sys.executable, STOP], input=json.dumps({"cwd": self.root, "stop_hook_active": active, "hook_event_name": "Stop"}),
                           capture_output=True, text=True, env={**self.env, **env})
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout) if p.stdout.strip() else {}

    def test_no_claims_lets_the_session_stop(self):
        os.remove(os.path.join(self.root, ".ripperdoc/claims/psd-peak.json"))
        self.assertEqual(self.stop(), {})

    def test_passing_claim_lets_the_session_stop(self):
        self.assertEqual(self.stop(), {})
        self.assertEqual(len(self.prompt_log()), 1)

    def test_blocked_claim_keeps_the_session_going(self):
        out = self.stop(FAKE_VERDICT="revise")
        self.assertEqual(out["decision"], "block")
        self.assertIn("psd-peak", out["reason"])
        self.assertIn("add the control run", out["reason"])

    def test_no_progress_after_a_block_stops_and_escalates(self):
        self.stop(FAKE_VERDICT="revise")
        out = self.stop(active=True, FAKE_VERDICT="revise")
        self.assertNotIn("decision", out)
        self.assertIn("no progress", out["systemMessage"])

    def test_progress_after_a_block_gets_a_new_review(self):
        self.stop(FAKE_VERDICT="revise")
        self.write("analysis.py", "print('fixed')\n")
        out = self.stop(active=True)
        self.assertEqual(out, {})
        self.assertEqual(len(self.prompt_log()), 2)

    def test_check_mode_never_calls_a_model(self):
        self.policy(ensemble=False, stop_hook="check")
        out = self.stop()
        self.assertEqual(out["decision"], "block")
        self.assertEqual(self.prompt_log(), [])

    def test_reviewer_sessions_are_ignored(self):
        self.assertEqual(self.stop(RIPPERDOC_GATE_ACTIVE="1"), {})
        self.assertEqual(self.prompt_log(), [])

    def test_escalation_is_a_message_not_a_block(self):
        self.policy(ensemble=False, max_rounds=2)
        out = self.stop(FAKE_VERDICT="revise")
        self.assertEqual(out["decision"], "block")
        self.write("analysis.py", "print('again')\n")
        out = self.stop(active=True, FAKE_VERDICT="revise")
        self.assertNotIn("decision", out)
        self.assertIn("human decision", out["systemMessage"])


class ProducerGuard(Project):
    def guard(self, tool, tool_input, **env):
        p = subprocess.run([sys.executable, PGUARD], input=json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": self.root}),
                           capture_output=True, text=True, env={**self.env, **env})
        return p.returncode

    def test_blocks_writes_to_what_judges_the_producer(self):
        for path in ["ripperdoc_reviews/2026-11-22_x_r1.md", "ripperdoc_reviews/.gate/x.json", ".ripperdoc/policy.json",
                     ".ripperdoc/state/x.json", os.path.join(ROOT, "packs", "physics", "checklist.md"), os.path.join(ROOT, "SKILL.md")]:
            self.assertEqual(self.guard("Write", {"file_path": path}), 2, path)
            self.assertEqual(self.guard("Edit", {"file_path": path}), 2, path)

    def test_allows_the_work_and_claims(self):
        for path in ["analysis.py", "out/result.json", ".ripperdoc/claims/psd-peak.json", "FINDINGS.md"]:
            self.assertEqual(self.guard("Write", {"file_path": path}), 0, path)

    def test_custom_review_dir(self):
        self.policy(review_dir="qa/reviews")
        self.assertEqual(self.guard("Write", {"file_path": "qa/reviews/r1.md"}), 2)

    def test_bash(self):
        for cmd in ["echo x > ripperdoc_reviews/a.md", "cp fake.md ripperdoc_reviews/", "sed -i s/3/1/ .ripperdoc/policy.json",
                    "RIPPERDOC_GATE_ACTIVE=1 claude -p hi", f"rm -rf {ROOT}/packs"]:
            self.assertEqual(self.guard("Bash", {"command": cmd}), 2, cmd)
        for cmd in [f"{ROOT}/bin/ripperdoc-gate init", f"{ROOT}/bin/ripperdoc-gate review x; rm -rf ripperdoc_reviews"]:
            self.assertEqual(self.guard("Bash", {"command": cmd}), 2, cmd)
        for cmd in ["cat .ripperdoc/policy.json > /tmp/x", "cat .ripperdoc/policy.json | tee .ripperdoc/policy.json",
                    "ls ripperdoc_reviews; rm -rf ripperdoc_reviews", "cat $(echo .ripperdoc/policy.json)",
                    "grep x ripperdoc_reviews/a.md && touch ripperdoc_reviews/b.md", "head .ripperdoc/policy.json\nrm x"]:
            self.assertEqual(self.guard("Bash", {"command": cmd}), 2, cmd)
        for cmd in ["cat .ripperdoc/policy.json", "ls ripperdoc_reviews .ripperdoc", "head -n 40 ripperdoc_reviews/2026-11-22_x_r1.md",
                    "grep -n verdict ripperdoc_reviews/2026-11-22_x_r1.md", "wc -l .ripperdoc/policy.json"]:
            self.assertEqual(self.guard("Bash", {"command": cmd}), 0, cmd)
        for cmd in ["python analysis.py", "ls out", "cat .ripperdoc/claims/psd-peak.json",
                    f"{ROOT}/bin/ripperdoc-gate review .ripperdoc/claims/psd-peak.json", "ripperdoc-gate check --all"]:
            self.assertEqual(self.guard("Bash", {"command": cmd}), 0, cmd)

    def test_reviewer_session_is_not_checked_here(self):
        self.assertEqual(self.guard("Write", {"file_path": "ripperdoc_reviews/x.md"}, RIPPERDOC_GATE_ACTIVE="1"), 0)


class Init(Project):
    def test_init_writes_default_policy_and_prints_hooks(self):
        os.remove(os.path.join(self.root, ".ripperdoc/policy.json"))
        p = subprocess.run([GATE, "init"], cwd=self.root, capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        pol = json.load(open(os.path.join(self.root, ".ripperdoc/policy.json")))
        self.assertEqual((pol["pass_verdicts"], pol["min_confidence"], pol["ensemble"], pol["max_rounds"]), (["accept"], 3, True, 3))
        self.assertIn("stop_gate.py", p.stdout)
        self.assertIn("producer_guard.py", p.stdout)
        s = p.stdout
        json.loads(s[s.index("{"):s.index("\n2. ")])  # the printed settings are valid JSON
        self.assertTrue(os.path.exists(os.path.join(self.root, ".ripperdoc", "claim.schema.json")))
        self.assertIn("CLAUDE.md", s)
        self.assertIn("--allowedTools", s)


if __name__ == "__main__":
    unittest.main()
