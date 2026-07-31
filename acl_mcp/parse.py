# parse.py — adapted from an earlier private transcript walker (same transcripts).
import glob, json, os
from dataclasses import dataclass

DEFAULT_GLOB = os.path.expanduser("~/.claude/projects/*/*.jsonl")
SKIP_MODELS = {"<synthetic>"}

@dataclass
class Event:
    session: str
    project: str
    date: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read: int
    cache_write_5m: int
    cache_write_1h: int
    web_search: int
    web_fetch: int
    tools: list
    skills: list
    message_id: str = ""
    source: str = "claude-code"

def _event(rec, session, project):
    if not isinstance(rec, dict):
        return None
    if rec.get("type") != "assistant":
        return None
    msg = rec.get("message") or {}
    model = msg.get("model")
    if not model or model in SKIP_MODELS:
        return None
    u = msg.get("usage") or {}
    cc = u.get("cache_creation") or {}
    w5 = cc.get("ephemeral_5m_input_tokens")
    w1 = cc.get("ephemeral_1h_input_tokens")
    if w5 is None and w1 is None:                     # no TTL split -> treat top-level as 5m
        w5 = u.get("cache_creation_input_tokens") or 0
        w1 = 0
    st = u.get("server_tool_use") or {}
    message_id = msg.get("id") or ""
    tools, skills = [], []
    for c in (msg.get("content") or []):
        if isinstance(c, dict) and c.get("type") == "tool_use":
            name = c.get("name")
            if name:
                tools.append(name)
            if name == "Skill":
                s = (c.get("input") or {}).get("skill") or (c.get("input") or {}).get("command")
                if s:
                    skills.append(s.lstrip("/"))
    return Event(
        session=session, project=project, date=(rec.get("timestamp") or "")[:10],
        model=model,
        input_tokens=u.get("input_tokens") or 0,
        output_tokens=u.get("output_tokens") or 0,
        cache_read=u.get("cache_read_input_tokens") or 0,
        cache_write_5m=w5 or 0, cache_write_1h=w1 or 0,
        web_search=st.get("web_search_requests") or 0,
        web_fetch=st.get("web_fetch_requests") or 0,
        tools=tools, skills=skills,
        message_id=message_id,
    )

def parse_file(path):
    session = os.path.basename(path)
    project = os.path.basename(os.path.dirname(path))
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ev = _event(rec, session, project)
                if ev:
                    out.append(ev)
    except OSError:
        return []
    return out

def _dedupe(events):
    """Claude Code writes one JSONL record per assistant content block (thinking/
    text/tool_use), and every record for the same message carries an identical
    message.id and the SAME full usage object. Keep the first-seen record per
    message_id (its usage is the whole message's usage, counted once), but union
    in tools/skills discovered on that message's later lines (tool_use blocks
    often land on later lines than thinking/text). Events without a message_id
    pass through unchanged — each is its own event."""
    seen = {}
    out = []
    for e in events:
        if not e.message_id:
            out.append(e)
            continue
        first = seen.get(e.message_id)
        if first is None:
            seen[e.message_id] = e
            out.append(e)
            continue
        for t in e.tools:
            if t not in first.tools:
                first.tools.append(t)
        for s in e.skills:
            if s not in first.skills:
                first.skills.append(s)
    return out

def sweep(pattern=DEFAULT_GLOB):
    out = []
    for p in sorted(glob.glob(pattern)):
        out.extend(parse_file(p))
    return _dedupe(out)

def full_input(e):
    """Input-side context of one turn: fresh input + cache reads + cache writes.
    A naive no-cache client would pay all of it as fresh input. Single home of
    this identity — cache_hit_ratio, recoverable_loose, no_cache_cost_of and the
    vanilla-replay generator all consume it."""
    return e.input_tokens + e.cache_read + e.cache_write_5m + e.cache_write_1h

def filter_by_date(events, since, until):
    def ok(e):
        if since and (e.date or "") < since: return False
        if until and (e.date or "") > until: return False
        return True
    return [e for e in events if ok(e)]
