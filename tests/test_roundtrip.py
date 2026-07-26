import os
import glob, json, os, re, subprocess, sys, time, unittest
import urllib.request
from unittest import mock

from acl_mcp import core

os.environ["ACL_PLAN_PATH"] = "/nonexistent"  # hermetic: ignore the runner's real plan config
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FIXTURE = os.path.join(REPO, "fixtures", "vanilla_replay.jsonl")
SERVER_PY = os.path.join(REPO, "server", ".venv", "bin", "python")
PORT = 8797


@unittest.skipUnless(os.path.exists(FIXTURE) and os.path.exists(SERVER_PY),
                     "needs fixture + server venv")
class TestRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = subprocess.Popen(
            [SERVER_PY, os.path.join(HERE, "local_server.py"), str(PORT)],
            stdout=subprocess.PIPE, text=True)
        cls.key = None
        for line in cls.proc.stdout:
            if line.startswith("KEY "):
                cls.key = line.split(None, 1)[1].strip()
            if line.startswith("READY"):
                break
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/v1/health", timeout=2)
                return
            except OSError:
                time.sleep(0.3)
        raise RuntimeError("local 2C server never became healthy")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate(); cls.proc.wait(timeout=10)

    def test_mcp_analyze_matches_lens_push(self):
        env = {"LENS_SERVER_URL": f"http://127.0.0.1:{PORT}",
               "LENS_API_KEY": self.key}
        with mock.patch("acl_mcp.core.scrub.load_or_create_salt",
                        return_value=b"proof-salt-32-bytes-padded......"):
            out = core.run_analyze(apilog=FIXTURE, env=env)
        lens_env = dict(os.environ, LENS_API_KEY=self.key)
        r = subprocess.run([sys.executable, "lens.py", "--apilog", FIXTURE,
                            "--push", f"http://127.0.0.1:{PORT}"],
                           capture_output=True, text=True, cwd=REPO, env=lens_env)
        self.assertEqual(r.returncode, 0, r.stderr)
        # both paths went through the same server on the same fixture:
        # the server summary line must be identical (scrub tags differ per
        # salt, but dollars/percentages/counts are salt-independent).
        strip = lambda s: re.sub(r"\[[^\]]*\]", "[SRC]", s)
        self.assertEqual(strip(out.splitlines()[0]),
                         strip(r.stdout.strip().splitlines()[0]))

    def test_preview_greps_clean_on_real_transcripts(self):
        real_names = {os.path.basename(p) for p in
                      glob.glob(os.path.expanduser("~/.claude/projects/*"))}
        real_names = {n for n in real_names if len(n) > 3}
        if not real_names:
            self.skipTest("no real transcripts on this box")
        out = core.build_preview(limit=3)
        for name in real_names:
            self.assertNotIn(name, out)
        self.assertTrue(out.endswith("Nothing was sent."))
