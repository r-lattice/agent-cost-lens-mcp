# mcp-client/tests/test_core.py
import os
import json, os, tempfile, unittest
from unittest import mock

from acl_mcp import core
import push  # flat vendored module (importable after acl_mcp __init__ shim)

os.environ["ACL_PLAN_PATH"] = "/nonexistent"  # hermetic: ignore the runner's real plan config
REC = {"ts": "2026-07-10T00:00:00Z", "source": "secret-app", "session": "sess-9",
       "response": {"id": "m1", "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 100, "output_tokens": 5,
                              "cache_read_input_tokens": 0,
                              "cache_creation_input_tokens": 0}}}

def apilog_file(dirpath, n=3):
    p = os.path.join(dirpath, "log.jsonl")
    with open(p, "w") as f:
        for i in range(n):
            r = json.loads(json.dumps(REC)); r["response"]["id"] = f"m{i}"
            f.write(json.dumps(r) + "\n")
    return p

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.log = apilog_file(self.tmp.name)
        salt = mock.patch("acl_mcp.core.scrub.load_or_create_salt",
                          return_value=b"a" * 32)
        salt.start(); self.addCleanup(salt.stop)

class TestPreview(Base):
    def test_preview_scrubs_sends_nothing_and_says_so(self):
        with mock.patch.object(core.push, "send",
                               side_effect=AssertionError("must not send")):
            out = core.build_preview(apilog=self.log, limit=2)
        self.assertNotIn("secret-app", out)
        self.assertNotIn("sess-9", out)
        self.assertTrue(out.endswith("Nothing was sent."))
        self.assertIn("3 scrubbed records", out)

    def test_preview_empty_range(self):
        out = core.build_preview(apilog=self.log, since="2027-01-01")
        self.assertIn("Nothing found", out)
        self.assertTrue(out.endswith("Nothing was sent."))

class TestAnalyze(Base):
    def test_missing_env_returns_setup_msg(self):
        self.assertEqual(core.run_analyze(apilog=self.log, env={}), core.SETUP_MSG)

    def test_happy_path_relays_summary_and_sim_dollars(self):
        body = {"summary": "agent-cost-lens[1 sources]: …", "skipped": 0,
                "advice": {"recoverable": 12.5}}
        with mock.patch.object(core.push, "send", return_value=(200, body)) as m:
            out = core.run_analyze(apilog=self.log,
                                   env={"LENS_SERVER_URL": "http://x",
                                        "LENS_API_KEY": "k"})
        m.assert_called_once()
        self.assertIn("agent-cost-lens[1 sources]", out)
        self.assertIn("up to $12.50 (simulated)", out)

    def test_server_error_relayed_not_raised(self):
        body = {"error": {"code": "revoked_key", "message": "key has been revoked"}}
        with mock.patch.object(core.push, "send", return_value=(403, body)):
            out = core.run_analyze(apilog=self.log,
                                   env={"LENS_SERVER_URL": "http://x",
                                        "LENS_API_KEY": "k"})
        self.assertIn("revoked_key", out)

    def test_unreachable_server_returns_text(self):
        with mock.patch.object(core.push, "send",
                               side_effect=push.PushError("cannot reach http://x")):
            out = core.run_analyze(apilog=self.log,
                                   env={"LENS_SERVER_URL": "http://x",
                                        "LENS_API_KEY": "k"})
        self.assertIn("cannot reach", out)

    def test_200_non_dict_body_returns_text_not_raise(self):
        for body in ("x", [1, 2]):
            with mock.patch.object(core.push, "send", return_value=(200, body)):
                out = core.run_analyze(apilog=self.log,
                                       env={"LENS_SERVER_URL": "http://x",
                                            "LENS_API_KEY": "k"})
            self.assertIsInstance(out, str)
            self.assertIn(str(body), out)

    def test_error_field_not_dict_falls_back_to_str_body(self):
        body = {"error": "revoked"}
        with mock.patch.object(core.push, "send", return_value=(403, body)):
            out = core.run_analyze(apilog=self.log,
                                   env={"LENS_SERVER_URL": "http://x",
                                        "LENS_API_KEY": "k"})
        self.assertIn("revoked", out)

    def test_server_skipped_non_int_treated_as_zero(self):
        body = {"summary": "s", "skipped": "oops"}
        with mock.patch.object(core.push, "send", return_value=(200, body)):
            out = core.run_analyze(apilog=self.log,
                                   env={"LENS_SERVER_URL": "http://x",
                                        "LENS_API_KEY": "k"})
        self.assertIn("s", out)
        self.assertNotIn("oops", out)

    def test_recoverable_non_numeric_is_ignored(self):
        body = {"summary": "ok-summary", "advice": {"recoverable": "twelve"}}
        with mock.patch.object(core.push, "send", return_value=(200, body)):
            out = core.run_analyze(apilog=self.log,
                                   env={"LENS_SERVER_URL": "http://x",
                                        "LENS_API_KEY": "k"})
        self.assertIn("ok-summary", out)
        self.assertNotIn("simulated", out)

    def test_non_str_summary_treated_as_missing(self):
        for body in ({"summary": 42}, {"summary": ["gotcha"]}):
            with mock.patch.object(core.push, "send", return_value=(200, body)):
                out = core.run_analyze(apilog=self.log,
                                       env={"LENS_SERVER_URL": "http://x",
                                            "LENS_API_KEY": "k"})
            self.assertIsInstance(out, str)
            self.assertIn("(no summary returned)", out)

class TestPreviewEdgeCases(Base):
    def test_preview_limit_zero_no_indexerror(self):
        out = core.build_preview(apilog=self.log, limit=0)
        self.assertTrue(out.endswith("Nothing was sent."))

class TestSaltFailure(Base):
    """Unreadable/uncreatable salt file (broken ~/.config perms) must not
    break the never-raise promise on either tool."""
    def test_preview_salt_oserror_returns_text_not_raise(self):
        with mock.patch("acl_mcp.core.scrub.load_or_create_salt",
                        side_effect=OSError("Permission denied")):
            out = core.build_preview(apilog=self.log)
        self.assertIsInstance(out, str)
        self.assertIn("salt", out.lower())

    def test_analyze_salt_oserror_returns_text_not_raise(self):
        with mock.patch("acl_mcp.core.scrub.load_or_create_salt",
                        side_effect=OSError("Permission denied")):
            out = core.run_analyze(apilog=self.log,
                                   env={"LENS_SERVER_URL": "http://x",
                                        "LENS_API_KEY": "k"})
        self.assertIsInstance(out, str)
        self.assertIn("salt", out.lower())

if __name__ == "__main__":
    unittest.main()
