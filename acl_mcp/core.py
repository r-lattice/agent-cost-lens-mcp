# mcp-client/acl_mcp/core.py
"""Tool logic, MCP-free so it tests offline. Scrubbing is structural:
everything flows through push.build_payload — no unscrubbed path exists."""
import json, os

import parse
import parse_apilog
import plan
import push
import scrub

SETUP_MSG = (
    "Agent Cost Lens is not configured yet. Add to this MCP server's env block:\n"
    '  "LENS_SERVER_URL": "<your analyzer URL>"\n'
    '  "LENS_API_KEY": "<your key>"\n'
    "preview_upload works without them — try it to see exactly what would be sent."
)


def _load_salt():
    """scrub.load_or_create_salt() can raise OSError on a broken ~/.config
    (unreadable salt file, uncreatable parent dir) -- never let that escape
    either tool. Returns (salt, error_text); exactly one is not None."""
    try:
        return scrub.load_or_create_salt(), None
    except OSError as ex:
        return None, f"Could not load or create the local salt file: {ex}"


def _sweep(since, until, apilog):
    if apilog:
        events, skipped = parse_apilog.sweep_apilog(apilog)
        where = apilog
    else:
        events, skipped = parse.sweep(), 0
        where = parse.DEFAULT_GLOB
    return parse.filter_by_date(events, since, until), skipped, where


def build_preview(since=None, until=None, apilog=None, limit=5):
    events, skipped, where = _sweep(since, until, apilog)
    if not events:
        return f"Nothing found for that range in {where}. Nothing was sent."
    salt, err = _load_salt()
    if err:
        return err
    payload = push.build_payload(events, salt, plan=plan.load_plan())
    recs = payload["events"][:max(0, int(limit))]
    lines = [f"{len(payload['events'])} scrubbed records ready "
             f"(schema {payload['schema']})."]
    if recs:
        lines.append(f"Record fields: {', '.join(sorted(recs[0].keys()))}")
        lines.append(f"First {len(recs)} record(s):")
        lines.append(json.dumps(recs, indent=1))
    else:
        lines.append("0 record(s) shown.")
    if skipped:
        lines.append(f"{skipped} malformed records were skipped.")
    lines.append("Nothing was sent.")
    return "\n".join(lines)


def _rejection_text(status, body):
    """Non-200 response: body.error may be missing, a dict, or hostile-server
    junk (a string, a list, ...) — never trust its shape."""
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return f"({status} {err.get('code')}): {err.get('message')}"
    return f"({status}): {body}"


def run_analyze(since=None, until=None, apilog=None, env=os.environ):
    url, key = env.get("LENS_SERVER_URL"), env.get("LENS_API_KEY")
    if not url or not key:
        return SETUP_MSG
    events, skipped, where = _sweep(since, until, apilog)
    if not events:
        return f"Nothing found for that range in {where}. Nothing was sent."
    salt, err = _load_salt()
    if err:
        return err
    payload = push.build_payload(events, salt, plan=plan.load_plan())
    try:
        status, body = push.send(payload, url, key)
    except push.PushError as ex:
        return f"Could not reach the analyzer: {ex}"
    if status != 200:
        return f"The analyzer rejected the upload {_rejection_text(status, body)}"
    if not isinstance(body, dict):
        return f"The analyzer returned an unexpected response: {body}"
    s = body.get("summary")
    lines = [s if isinstance(s, str) and s else "(no summary returned)"]
    # The server composed that summary without knowing the user's billing model.
    # On a flat-fee plan (Claude Pro/Max) its dollar figures are API-equivalent
    # value, not spend — annotate client-side rather than rewording server text.
    _plan = plan.load_plan()
    if _plan and not (isinstance(s, str) and "API-equivalent" in s):
        # Old/plan-unaware server: annotate client-side. A plan-aware server
        # already worded the summary itself — don't say it twice.
        lines.append(plan.context_line(_plan))
    adv = body.get("advice") or {}
    recoverable = adv.get("recoverable") if isinstance(adv, dict) else None
    if (isinstance(recoverable, (int, float)) and not isinstance(recoverable, bool)
            and recoverable >= 0.01):
        lines.append(f"Proper caching recovers up to "
                     f"${recoverable:,.2f} (simulated).")
    server_skipped = body.get("skipped")
    if not isinstance(server_skipped, int) or isinstance(server_skipped, bool):
        server_skipped = 0
    total_skipped = skipped + server_skipped
    if total_skipped:
        lines.append(f"{total_skipped} malformed records were skipped.")
    return "\n".join(lines)
