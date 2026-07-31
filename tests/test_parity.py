import os, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "..", "acl_mcp")
ROOT = os.path.join(HERE, "..", "..")
VENDORED = ("parse.py", "parse_apilog.py", "scrub.py", "push.py", "plan.py")

# In the published snapshot the canonical engine repo is absent by design —
# parity is enforced upstream, before this snapshot is cut.
_IN_MOTHER_REPO = all(os.path.exists(os.path.join(ROOT, n)) for n in VENDORED)


@unittest.skipUnless(_IN_MOTHER_REPO, "canonical modules absent (published snapshot)")
class TestParity(unittest.TestCase):
    def test_vendored_files_byte_identical(self):
        for name in VENDORED:
            with open(os.path.join(ROOT, name), "rb") as f:
                canonical = f.read()
            with open(os.path.join(PKG, name), "rb") as f:
                vendored = f.read()
            self.assertEqual(canonical, vendored,
                             f"{name} drifted — run python3 vendor_client.py")


if __name__ == "__main__":
    unittest.main()
