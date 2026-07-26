import os
import unittest

from acl_mcp import server


os.environ["ACL_PLAN_PATH"] = "/nonexistent"  # hermetic: ignore the runner's real plan config
class TestServer(unittest.TestCase):
    def test_exactly_two_tools(self):
        import asyncio
        tools = asyncio.run(server.mcp.list_tools())
        self.assertEqual(sorted(t.name for t in tools),
                         ["analyze_costs", "preview_upload"])

    def test_tools_delegate_to_core(self):
        from unittest import mock
        with mock.patch("acl_mcp.core.build_preview",
                        return_value="PREVIEW") as m:
            out = server.preview_upload(limit=2)
        self.assertEqual(out, "PREVIEW")
        m.assert_called_once_with(None, None, None, 2)


if __name__ == "__main__":
    unittest.main()
