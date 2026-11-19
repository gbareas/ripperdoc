"""bin/sandbox-run argument construction (dry run; the sandboxes themselves need bwrap or macOS)."""
import os, subprocess, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SR = os.path.join(ROOT, "bin", "sandbox-run")


def dry(os_name, *cmd, **env):
    with tempfile.TemporaryDirectory() as tmp:
        e = dict(os.environ, RIPPERDOC_SANDBOX_DRYRUN="1", RIPPERDOC_SANDBOX_OS=os_name, RIPPERDOC_SCRATCH=tmp, **env)
        p = subprocess.run([SR, *cmd], capture_output=True, text=True, env=e)
        return p.returncode, p.stdout, p.stderr


class Linux(unittest.TestCase):
    def test_flags(self):
        code, out, _ = dry("Linux", "python", "x.py")
        self.assertEqual(code, 0)
        for flag in ("--ro-bind / /", "--dev /dev", "--unshare-net", "--new-session", "--unshare-pid", "--die-with-parent",
                     "timeout 300 python x.py", "RIPPERDOC_OUT", "PYTHONPYCACHEPREFIX"):
            self.assertIn(flag, out)
        self.assertNotIn("--dev-bind /dev /dev", out)

    def test_timeout_env(self):
        self.assertIn("timeout 1200 ", dry("Linux", "true", RIPPERDOC_TIMEOUT="1200")[1])
        self.assertEqual(dry("Linux", "true", RIPPERDOC_TIMEOUT="10; rm -rf x")[0], 2)


class MacOS(unittest.TestCase):
    def test_profile(self):
        code, out, _ = dry("Darwin", "python", "x.py")
        self.assertEqual(code, 0)
        self.assertIn("sandbox-exec -p", out)
        self.assertIn("(deny network*)", out)
        self.assertIn("(deny file-write*)", out)
        self.assertIn("run-", out)
        self.assertIn("300 python x.py", out)


class Other(unittest.TestCase):
    def test_unknown_platform_refuses(self):
        self.assertEqual(dry("Plan9", "true")[0], 97)

    def test_no_bwrap_refuses_without_dry_run(self):
        e = dict(os.environ, RIPPERDOC_SANDBOX_OS="Linux", PATH="/usr/bin:/bin")
        if subprocess.run(["sh", "-c", "command -v bwrap"], env=e, capture_output=True).returncode == 0:
            self.skipTest("bwrap is installed")
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run([SR, "true"], capture_output=True, text=True, env=dict(e, RIPPERDOC_SCRATCH=tmp))
        self.assertEqual(p.returncode, 97)


if __name__ == "__main__":
    unittest.main()
