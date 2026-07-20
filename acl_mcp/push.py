"""Build and send the scrubbed wire payload (spec: API contract + client).
Scrub is not optional: build_payload always pseudonymizes source and session."""
import json, urllib.error, urllib.request
import scrub

class PushError(Exception):
    pass

def to_record(e):
    """Event -> apilog-v1 record. Exact inverse of parse_apilog._event."""
    return {
        "ts": (e.date or "") + "T00:00:00Z",
        "source": e.project,
        "session": e.session,
        "response": {
            "id": e.message_id, "model": e.model,
            "usage": {
                "input_tokens": e.input_tokens,
                "output_tokens": e.output_tokens,
                "cache_read_input_tokens": e.cache_read,
                "cache_creation_input_tokens": e.cache_write_5m,
                "cache_creation_1h_input_tokens": e.cache_write_1h,
                "server_tool_use": {"web_search_requests": e.web_search,
                                    "web_fetch_requests": e.web_fetch},
            },
        },
    }

def build_payload(events, salt, plan=None):
    recs = []
    for e in events:
        r = to_record(e)
        r["source"] = scrub.tag(salt, e.project, "src-")
        r["session"] = scrub.tag(salt, e.session, "s-")
        recs.append(r)
    payload = {"schema": "apilog-v1", "events": recs}
    if plan:
        # Plan is user-supplied, non-sensitive context ({name, monthly_cost})
        # that lets the server word its summary honestly for flat-fee plans.
        # Send ONLY the two fields the wire needs — never the raw config dict.
        payload["plan"] = {"name": str(plan["name"]),
                           "monthly_cost": float(plan["monthly_cost"])}
    return payload

def send(payload, url, key, timeout=30):
    req = urllib.request.Request(
        url.rstrip("/") + "/v1/analyze",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
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
