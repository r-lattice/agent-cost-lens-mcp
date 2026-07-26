"""Optional subscription-plan context (Claude Pro / Max plans).

On a flat-fee plan, per-token dollar figures are API-EQUIVALENT VALUE, not
spend — marginal cost is $0 and "recoverable" means usage-limit headroom, not
dollars. This module loads the user's plan config so reports can say so
(the headline owns its footnote).

Config lives OUTSIDE the repo — it's user config, not product config:
    ~/.config/agent-cost-lens/plan.json   (override with $ACL_PLAN_PATH)
    {"name": "Max 20x", "monthly_cost": 200.0}

Absent file -> None (fail dark: plan-unaware output is a designed state and
must stay byte-identical to pre-plan behavior). Present-but-malformed -> exit
loudly; a silently ignored typo would mislabel every dollar figure.
"""
import json, os, sys

_REQUIRED = ("name", "monthly_cost")


def plan_path():
    return os.environ.get("ACL_PLAN_PATH") or os.path.expanduser(
        "~/.config/agent-cost-lens/plan.json")


def load_plan(path=None):
    path = path or plan_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            p = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"agent-cost-lens: plan config malformed at {path}: {e}")
    missing = [k for k in _REQUIRED if k not in p]
    if missing:
        sys.exit(f"agent-cost-lens: plan config missing keys {missing} at {path}")
    if not isinstance(p["monthly_cost"], (int, float)) or p["monthly_cost"] <= 0:
        sys.exit(f"agent-cost-lens: plan monthly_cost must be a positive number at {path}")
    return p


def run_rate_line(plan, total, n_days):
    """'equiv run-rate ≈ $X/mo = K.K× plan price' — or '' when the span is unknown."""
    if not n_days or total is None:
        return ""
    monthly_equiv = total / n_days * 30.0
    mult = monthly_equiv / plan["monthly_cost"]
    return (f" · equiv run-rate ≈ ${monthly_equiv:,.0f}/mo"
            f" = {mult:,.1f}× plan price")


def context_line(plan):
    """One-line annotation for output composed elsewhere (e.g. a server summary
    we can't reword): states the interpretation without recomputing figures."""
    return (f"plan: {plan['name']} (flat ${plan['monthly_cost']:,.0f}/mo) — "
            f"dollar figures above are API-equivalent value, not spend; "
            f"marginal cost $0, recoverable = usage-limit headroom")
