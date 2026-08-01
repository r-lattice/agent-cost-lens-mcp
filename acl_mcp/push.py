"""Build and send the scrubbed wire payload (spec: API contract + client).
Scrub is not optional: build_payload always pseudonymizes source and session."""
import gzip, json, urllib.error, urllib.request
import scrub

class PushError(Exception):
    pass

def to_record(e):
    """Event -> apilog-v1 record. Exact inverse of parse_apilog._event.

    Compact by construction: the date carries no time half (the reader slices
    [:10]) and zero-valued counters are omitted rather than spelled out, because
    _int_field treats absent as 0. Both are the reader's existing behavior, so
    this stays apilog-v1 — an older server reads it unchanged. Measured
    2026-07-30 on 9,548 real events: 403 -> 274 bytes/record, and
    server_tool_use was all-zero on 100% of them."""
    usage = {
        "input_tokens": e.input_tokens,
        "output_tokens": e.output_tokens,
        "cache_read_input_tokens": e.cache_read,
        "cache_creation_input_tokens": e.cache_write_5m,
        "cache_creation_1h_input_tokens": e.cache_write_1h,
    }
    usage = {k: v for k, v in usage.items() if v}
    tools = {k: v for k, v in (("web_search_requests", e.web_search),
                               ("web_fetch_requests", e.web_fetch)) if v}
    if tools:
        usage["server_tool_use"] = tools
    return {
        "ts": e.date or "",
        "source": e.project,
        "session": e.session,
        "response": {"id": e.message_id, "model": e.model, "usage": usage},
    }

def build_payload(events, salt, plan=None):
    recs = []
    for e in events:
        r = to_record(e)
        r["source"] = scrub.tag(salt, e.project, "src-")
        r["session"] = scrub.tag(salt, e.session, "s-")
        # An Anthropic message id is an upstream identifier, not ours to forward.
        # It is only ever a dedupe key (parse._dedupe), and a stable tag is an
        # equally good key — so nothing downstream loses a capability.
        r["response"]["id"] = scrub.tag(salt, e.message_id, "m-")
        recs.append(r)
    payload = {"schema": "apilog-v1", "events": recs}
    if plan:
        # Plan is user-supplied, non-sensitive context ({name, monthly_cost})
        # that lets the server word its summary honestly for flat-fee plans.
        # Send ONLY the two fields the wire needs — never the raw config dict.
        payload["plan"] = {"name": str(plan["name"]),
                           "monthly_cost": float(plan["monthly_cost"])}
    return payload

def server_accepts(url, coding, timeout=10):
    """Ask the server whether it accepts a body coding before using one.

    Fail-dark by construction (F4): ANY failure — an old server with no
    `accepts` key, no /v1/health at all, a timeout, a proxy returning HTML —
    answers False and the caller sends a plain body, which every server this
    project has ever deployed still reads. Compression is an optimization and
    is never allowed to be the reason a push fails."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/v1/health",
                                    timeout=timeout) as resp:
            return coding in (json.loads(resp.read().decode()).get("accepts") or [])
    except Exception:
        return False

def send(payload, url, key, timeout=30):
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {key}"}
    if server_accepts(url, "gzip", timeout=timeout):
        # mtime=0 explicitly, NOT by default: gzip stamps the clock into the
        # header, and which behavior you get depends on the interpreter (3.11
        # made 0 the default; this package supports >=3.10). A wire property
        # must not vary with the user's Python — so it is stated, not inherited.
        data = gzip.compress(data, mtime=0)
        headers["Content-Encoding"] = "gzip"
    req = urllib.request.Request(
        url.rstrip("/") + "/v1/analyze",
        data=data,
        headers=headers,
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except ValueError as ex:
                raise PushError(
                    f"{url} returned {resp.status} with a non-JSON body "
                    f"(wrong URL? not an agent-cost-lens server?): {ex}") from ex
    except urllib.error.HTTPError as ex:
        try:
            body = json.loads(ex.read().decode())
        except Exception:
            body = {"error": {"code": "bad_response", "message": str(ex)}}
        return ex.code, body
    except (urllib.error.URLError, TimeoutError, OSError) as ex:
        raise PushError(f"cannot reach {url}: {ex}") from ex
    except ValueError as ex:
        # e.g. a key/header containing a newline fails urllib's own header
        # validation before any connection is made -- surface it the same
        # never-raise way as a transport failure, not a raw traceback.
        raise PushError(f"invalid request to {url}: {ex}") from ex
