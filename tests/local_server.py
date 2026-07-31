# mcp-client/tests/local_server.py
"""Serve the 2C app on 127.0.0.1 with sqlite for the 2D round-trip proof.
Run with the SERVER venv: server/.venv/bin/python mcp-client/tests/local_server.py PORT
Prints "KEY <raw>" then "READY", then serves until killed."""
import os, sqlite3, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "server"))

import app as app_mod        # noqa: E402
import auth, storage         # noqa: E402

def main():
    port = int(sys.argv[1])
    store = storage.Storage(sqlite3.connect(":memory:", check_same_thread=False),
                            ph="?")
    store.ensure_schema()
    raw = auth.mint()
    store.insert_key(auth.hash_key(raw), "roundtrip-proof")
    cfg = {"max_body_bytes": 50_000_000, "max_events": 500_000, "max_commas_per_event": 16,
           "rate_limit_per_minute": 1000, "buy_url": "https://buy.example/t"}
    application = app_mod.create_app(store, cfg)
    print(f"KEY {raw}", flush=True)
    print("READY", flush=True)
    import uvicorn
    uvicorn.run(application, host="127.0.0.1", port=port, log_level="error")

if __name__ == "__main__":
    main()
