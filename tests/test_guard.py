"""Tests for hooks/guard.py. Run: python3 -m unittest discover -s tests"""
import json, os, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
GUARD = os.path.join(ROOT, "hooks", "guard.py")
SR = os.path.join(ROOT, "bin", "sandbox-run")
VAL = os.path.join(ROOT, "bin", "validate.py")
CWD = "/work/proj"


def run(tool, tool_input, cwd=CWD):
    p = subprocess.run([sys.executable, GUARD], input=json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": cwd}),
                       capture_output=True, text=True)
    return p.returncode, p.stderr


def bash(cmd):
    return run("Bash", {"command": cmd})[0]


# Commands that write files or run code outside the sandbox. All must be blocked.
ESCAPES = [
    "python train.py",
    "python3 -c 'open(\"results.csv\",\"w\")'",
    "bash run.sh",
    'git -c core.fsmonitor="touch pwn" status',
    "git -c diff.external=./evil.sh diff",
    "git checkout -- results.csv",
    "rg --pre ./evil.sh foo .",
    "sed -n '1e touch pwn' README.md",
    "sed 's/a/b/w results.csv' README.md",
    "sed -ni 's/a/b/' results.csv",
    "sed -i 's/a/b/' results.csv",
    "sort -o results.csv results.csv",
    "uniq a.txt results.csv",
    "xxd -r dump.hex model.pt",
    "pdftotext paper.pdf notes.txt",
    'find . -name "*.csv" -fprint0 list',
    "find . -delete",
    "tree -o out.txt",
    "nvidia-smi -r",
    "cat a.txt > results.csv",
    "cat a.txt | tee results.csv",
    "rm -rf outputs",
    "mv a b",
    "awk 'BEGIN{system(\"touch pwn\")}'",
    # unsandboxed execution smuggled around a sandboxed command
    f"{SR} cat x; python train.py",
    f"{SR} cat x && rm results.csv",
    f'{SR} bash -c "$(cat evil.sh)"',
    f"echo `touch pwn`",
    f"{SR} cat x > results.csv",
    # environment that changes how sandbox-run itself (a host-side bash script) runs
    f"BASH_ENV=./evil.sh {SR} true",
    f"LD_PRELOAD=./evil.so {SR} true",
    f"PATH=.:$PATH {SR} true",
    # a sandbox-run that is not ripperdoc's own
    "./sandbox-run python train.py",
    "/tmp/x/bin/sandbox-run python train.py",
    f"python3 {ROOT}/bin/../hooks/guard.py",
]

ALLOWED = [
    f"{SR} python train.py --out \"$RIPPERDOC_OUT\"",
    f"{SR} bash -c 'cd src && python x.py; echo $(date)'",
    f"{SR} cat results.csv | {SR} grep loss",
    f"cd /work/proj && {SR} git log --oneline -5",
    f"RIPPERDOC_TIMEOUT=600 {SR} python eval.py",
    f"{SR} python x.py > /work/proj/ripperdoc_reviews/run.txt 2>&1",
    f"{SR} python x.py 2>/dev/null",
    f"python3 {VAL} review /work/proj/ripperdoc_reviews/r.md",
    f"{VAL} dossier ripperdoc_reviews/dossier.json",
    f"python3 {ROOT}/bin/render_dossier.py ripperdoc_reviews/dossier.json",
    f"python3 {ROOT}/bin/merge_reviews.py ripperdoc_reviews/m.json ripperdoc_reviews/a.md ripperdoc_reviews/b.md",
]


class GuardBash(unittest.TestCase):
    def test_escapes_blocked(self):
        for cmd in ESCAPES:
            with self.subTest(cmd=cmd):
                self.assertEqual(bash(cmd), 2, f"guard allowed: {cmd}")

    def test_sandboxed_and_own_tools_allowed(self):
        for cmd in ALLOWED:
            with self.subTest(cmd=cmd):
                code, err = run("Bash", {"command": cmd})
                self.assertEqual(code, 0, f"guard blocked: {cmd}\n{err}")

    def test_block_message_points_to_sandbox(self):
        _, err = run("Bash", {"command": "python train.py"})
        self.assertIn("sandbox-run", err)


class GuardWrite(unittest.TestCase):
    def test_write_outside_review_dir_blocked(self):
        for p in ["/work/proj/results.csv", "/work/proj/ripperdoc_reviews/../train.py", "src/model.py"]:
            with self.subTest(path=p):
                self.assertEqual(run("Write", {"file_path": p, "content": "x"})[0], 2)
                self.assertEqual(run("Edit", {"file_path": p, "old_string": "a", "new_string": "b"})[0], 2)

    def test_write_inside_review_dir_allowed(self):
        for p in ["/work/proj/ripperdoc_reviews/NOTES.md", "ripperdoc_reviews/2026-01-01_x_r1.md"]:
            with self.subTest(path=p):
                self.assertEqual(run("Write", {"file_path": p, "content": "x"})[0], 0)

    def test_other_tools_pass(self):
        self.assertEqual(run("Read", {"file_path": "/work/proj/results.csv"})[0], 0)


if __name__ == "__main__":
    unittest.main()
