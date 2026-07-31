"""Flat-import shim: the vendored modules import each other by bare name
(push imports scrub; parse_apilog imports parse) exactly as at the repo
root, so the package dir joins sys.path once, at package import."""
import os, sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
