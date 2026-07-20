# Changelog — Agent Cost Lens

Format: [Keep a Changelog](https://keepachangelog.com/) · versioning: semver.
"Live" means deployed to https://lens.r-lattice.com. Postable per-release notes
live in `releases/`. The deployed version is verifiable at `/v1/health`
(`{"version": ...}`) — bump it in `server/app.py` with every release.

## [1.1.0] — 2026-07-20 (pending deploy)
### Added
- **Plan-aware reporting for flat-fee subscriptions (Claude Max/Pro).**
  Configure once (`~/.config/agent-cost-lens/plan.json`: `{name, monthly_cost}`)
  and every figure is worded for subscription reality: dollars become
  *API-equivalent value*, savings and recoverable become *usage-limit headroom*,
  and the summary adds an equivalent-run-rate multiple of the plan price.
- Optional `plan` field on the `apilog-v1` wire envelope — strictly validated
  (`bad_plan` 400 on malformed), absent for every existing client.
- Landing page states the plan-aware framing; the claim is unit-test-enforced
  (no dollar-savings language for flat-fee users).
- `/v1/health` now reports the real release version (was a stale phase tag).

### Unchanged (by contract, test-locked)
- No plan configured → output byte-identical to 1.0.0, locally and hosted.
- Wire format still cannot carry prompt text or code; the plan field carries
  exactly two values: plan name and monthly price.
- Deploy order: **server first, then clients** — the 1.0.0 ingress rejects
  unknown envelope keys, so a 1.1.0 client with a plan configured cannot push
  to a 1.0.0 server.

### Tests
Root 119 · client 19 (incl. byte-parity, now a vendored quintet) · server 58.

## [1.0.0] — 2026-07-18 (live)
First public version — everything currently serving at lens.r-lattice.com.
Retroactively tagged; see `releases/v1.0.0.md` for the full report.

### Highlights (built 2026-07-12 → 2026-07-18, 70 commits)
- **Local engine**: transcript sweep + apilog ingest, per-content-block dedupe,
  dated pricing config, cache-hit analysis, HTML report, `--push`.
- **Simulator (`advise.py`)**: ground-truth-gated (sim/CC ratio locked by test);
  every estimate labeled *simulated* / *up to*.
- **Hosted analyzer**: FastAPI on Cloud Run; hash-only API keys, flag-flip
  revocation, strict ingress, per-key rate limit; events die with the request,
  only (key, source, day) aggregates persist.
- **Privacy as surface**: structural scrubbing (HMAC pseudonyms; the wire format
  has no field for prompt text or code) + auditable preview.
- **Extractable MCP client**: vendored collection modules under a byte-parity
  test; `analyze_costs` + `preview_upload` tools; never raises past itself.
- **Billing**: Stripe Payment Link ($29/mo), shown-once key claim,
  signature-checked auto-revoke webhook; billing 503s until configured and is
  never load-bearing for analysis.
- **Public front door**: SEO landing, `llms.txt`, `/download` tarball,
  lens.r-lattice.com domain.
