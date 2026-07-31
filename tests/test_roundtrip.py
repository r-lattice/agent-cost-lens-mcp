import os
import glob, gzip, json, os, re, subprocess, sys, time, unittest
import urllib.request
from unittest import mock

from acl_mcp import core, parse_apilog, push

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

    def test_live_gzip_negotiation_answers_identically_to_a_plain_push(self):
        """Gzip negotiation probe leg 1, over real HTTP against the real app — not mocks.

        The existing round-trip already sends a compressed body now that the
        client negotiates, but SILENTLY: if the handshake regressed to always-
        False it would quietly send plain and still pass. This pins both ends —
        the advertisement is really read over the wire, and the compressed push
        returns exactly what the same payload returns uncompressed."""
        url = f"http://127.0.0.1:{PORT}"
        self.assertTrue(push.server_accepts(url, "gzip"),
                        "live server did not advertise gzip on /v1/health")
        events, _skipped = parse_apilog.sweep_apilog(FIXTURE)
        payload = push.build_payload(events, salt=b"proof-salt-32-bytes-padded......")

        with mock.patch("acl_mcp.push.server_accepts", return_value=False):
            plain_status, plain_body = push.send(payload, url, self.key)
        self.assertEqual(plain_status, 200)

        # Hand-built gzip POST rather than another send() call: this asserts the
        # LIVE uvicorn/Starlette stack hands the compressed bytes through
        # un-mangled and the server inflates them. Going through send() again
        # would pass even if it silently ignored the negotiation and sent plain.
        raw = gzip.compress(json.dumps(payload).encode(), mtime=0)
        req = urllib.request.Request(
            url + "/v1/analyze", data=raw, method="POST",
            headers={"Content-Type": "application/json",
                     "Content-Encoding": "gzip",
                     "Authorization": f"Bearer {self.key}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            self.assertEqual(resp.status, 200)
            gz_body = json.loads(resp.read().decode())

        self.assertLess(len(raw), len(json.dumps(payload).encode()))
        self.assertEqual(gz_body, plain_body,
                         "compressed and plain bodies produced different answers")

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
