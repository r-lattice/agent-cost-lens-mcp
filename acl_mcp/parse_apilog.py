# parse_apilog.py — apilog v1: what a raw-API app can trivially log. One JSON
# object per line: {"ts": ISO8601, "source": app, "session": id,
#                   "response": {"id", "model", "usage": {...}}}
# Emits the same Event dataclass parse.py does, so price/analyze/report need
# no changes. Spec: docs/superpowers/specs/2026-07-13-phase2a-ingestion-design.md
import glob, json, sys
from parse import Event, _dedupe

_BAD = object()  # sentinel: field present but wrong-typed -> caller must skip the record

def _int_field(v):
    """None/absent -> 0 (default, as today). int -> pass through. Anything else
    (e.g. a numeric string like "9000") -> _BAD, so the record can be skipped
    instead of silently coerced to a wrong zero."""
    if v is None:
        return 0
    return v if isinstance(v, int) else _BAD

def _event(rec):
    if not isinstance(rec, dict):
        return None
    resp = rec.get("response") or {}
    if not isinstance(resp, dict):
        return None
    model = resp.get("model")
    u = resp.get("usage")
    if not model or not isinstance(u, dict):
        return None

    ts = rec.get("ts")
    if ts is not None and not isinstance(ts, str):
        return None  # malformed, not "no timestamp" -> skip, don't default to ""

    src = rec.get("source")
    if src is not None and not isinstance(src, str):
        return None
    src = src or "apilog"

    session = rec.get("session")
    if session is not None and not isinstance(session, str):
        return None
    session = session or ""

    st = u.get("server_tool_use")
    if not isinstance(st, dict):
        st = {}   # optional field; non-dict (or missing) is tolerated, not fatal

    input_tokens = _int_field(u.get("input_tokens"))
    output_tokens = _int_field(u.get("output_tokens"))
    cache_read = _int_field(u.get("cache_read_input_tokens"))
    cache_write_5m = _int_field(u.get("cache_creation_input_tokens"))
    cache_write_1h = _int_field(u.get("cache_creation_1h_input_tokens", 0))
    web_search = _int_field(st.get("web_search_requests"))
    web_fetch = _int_field(st.get("web_fetch_requests"))
    if _BAD in (input_tokens, output_tokens, cache_read, cache_write_5m, cache_write_1h, web_search, web_fetch):
        return None

    return Event(
        session=session,
        project=src,
        date=(ts or "")[:10],
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read=cache_read,
        cache_write_5m=cache_write_5m,
        cache_write_1h=cache_write_1h,
        web_search=web_search,
        web_fetch=web_fetch,
        tools=[], skills=[],
        message_id=resp.get("id") or "",
        source=src,
    )

def parse_apilog_file(path):
    """-> (events, n_skipped). Junk lines and records missing/wrong-typed fields
    are skipped-and-counted, never fatal (the caller surfaces the count). The
    try/except around _event is belt-and-braces: even a shape nobody predicted
    must not crash the whole run."""
    events, skipped = [], 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    continue
                try:
                    ev = _event(rec)
                except Exception:
                    skipped += 1
                    continue
                if ev is None:
                    skipped += 1
                else:
                    events.append(ev)
    except OSError:
        print(f"parse_apilog: cannot read {path}", file=sys.stderr)
        return [], 0
    return events, skipped

def sweep_apilog(pattern):
    """Glob-sweep apilog files; dedupe by response.id (apps can log retries twice)."""
    events, skipped = [], 0
    for p in sorted(glob.glob(pattern)):
        evs, sk = parse_apilog_file(p)
        events.extend(evs)
        skipped += sk
    return _dedupe(events), skipped
