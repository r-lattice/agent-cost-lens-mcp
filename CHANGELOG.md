# Changelog — Agent Cost Lens

Format: [Keep a Changelog](https://keepachangelog.com/) · versioning: semver.
"Live" means deployed to https://lens.r-lattice.com. Postable per-release notes
live in `releases/`. The deployed version is verifiable at `/v1/health`
(`{"version": ...}`) — bump it in `server/app.py` with every release.

## [1.6.0] — 2026-07-30
### Changed
- **A single request now carries up to 55,000 events, up from 50,000.** The
  byte limit (15 MB) and the event limit are now sized to meet at real record
  sizes — they admit the same amount of history, so neither can quietly be
  raised past what the other allows.
- **Stored aggregates are now components, not ratios.** The per-day figures the
  hosted tier keeps for your key were stored as percentages, and a stored
  percentage can never be re-aggregated — the denominators are gone. They are
  now stored as the token counts they derive from, so exact whole-window
  figures can be recomputed later. Findings moved to their own per-push record
  at the same time. Nothing about what leaves your machine changed: same wire,
  same pseudonyms, same `preview_upload` audit.
- Client 1.3.1: comment cleanups only, no behavior change.

## [1.5.0] — 2026-07-30
### Added
- **Uploads can now be compressed, and the two ends agree before they are.**
  The client asks `/v1/health` which body encodings the server accepts and
  gzips the upload only if gzip is on that list. A server that does not offer
  it receives exactly the plain body it receives today, so clients and servers
  can be upgraded in either order and in either combination. Measured on 9,978
  real records: **2.72 MB → 225 KB (12.1×)**. This is still `apilog-v1` — the
  document is unchanged, only the number of bytes it travels in.

- **The upload limit is now 15 MB, up from 5 MB.** At the sizes people actually
  push that is three times the history in one request — and comfortably above
  the most a single request can carry under the 50,000-event limit. The limit is
  pinned to the memory the service is deployed with — the server refuses to
  start if the two disagree — so it cannot quietly be raised into an
  out-of-memory failure. The per-request event limit (50,000) is unchanged and
  is now the first limit most people will meet.

### Changed
- **The size cap now bounds decompression instead of measuring it afterwards.**
  A compressed body that would expand past the limit is refused *without being
  expanded* — both the bytes read off the wire and the decompressed size are
  capped, so a small upload cannot claim a large amount of server memory. The
  per-request event limit still applies after decompression.
- **A `Content-Encoding` the server never advertised is refused by name.**
  Previously an unrecognized encoding would have been read as plain text and
  reported as malformed JSON, which describes the wrong problem.

## [1.4.0] — 2026-07-30
### Changed
- **The wire no longer forwards upstream message ids.** A record's
  `response.id` was travelling to the analyzer verbatim — the only field on the
  wire that was not already a local HMAC pseudonym. It is now tagged like
  `source` and `session` are. Nothing reads it downstream (it serves only as a
  dedupe key), so no capability changed; the raw Anthropic id simply stops
  leaving your machine.
- **A record costs 32% fewer bytes.** Every timestamp carried a
  `T00:00:00Z` the reader immediately discards, and the server-tool counters
  were spelled out as zeros on every single record. Both are now omitted.
  Measured on 9,548 real events: 403 → 272 bytes each. This stays
  `apilog-v1` — the reader already tolerated both, now pinned by a contract
  test, so an older server reads the new records unchanged and clients and
  servers can upgrade in either order.
- **Size-cap refusals name the remedy.** `too_large` and `too_many_events`
  said only what the limit was, which reads as a broken server rather than
  "ask for less history". They now say to narrow the window with
  `--since` / `--until`.

### Added
- **The fix advice now appears on the default path.** `advise()` was gated on
  `--apilog`, so a plain `lens.py` run over local transcripts — the way most
  runs happen — never showed the pattern catalog or the simulated recovery,
  while the hosted analyzer showed both for the same data. It reads no
  apilog-only field, and its simulator's ground-truth band was measured
  against real Claude Code transcripts (re-measured this release at 0.797,
  inside [0.70, 1.30]), so the transcript path is the validated case. A run
  the simulator cannot improve keeps its previous wording exactly.

### Known limits
- Chunked upload is still absent, so a single analysis is bounded by the
  server's `max_body_bytes`. The compaction above roughly triples the history
  that fits (~12,400 → ~18,350 records) but does not remove the ceiling; when
  you hit it, narrow the date window. `max_events` remains unreachable —
  the body cap binds first.

## [1.3.0] — 2026-07-26
### Added
- **Landing: "It names the fix."** The page now tells the consultation half:
  a pattern catalog (uncached history, cache churn, volatile prefix, honest
  nothing-to-fix) with the volatile-prefix advice quoted verbatim from the
  engine, so page and product can never drift. Title, meta description,
  og:description, JSON-LD, hero, and llms.txt all carry one positioning
  phrasing — pinned by test.
- **Link-preview card.** `og:image` + Twitter card served at `/og-card.png`,
  rendered at build time from the same constants as the hero
  (`server/build_og_card.py`); a manifest (constants + sha256) is test-pinned
  so a stale card fails the suite instead of shipping.
- **SEO mechanicals.** `/robots.txt` and `/sitemap.xml` routes.
- **Pricing: claude-opus-5** ($5/$25 per MTok, dated rate card) rides this
  deploy — staged 2026-07-24 by pricing_watch, verified against both live pages.

## [1.2.11] — 2026-07-24
### Added
- **Beta keys can expire.** API keys may now carry an expiry; a request made
  with an expired key is rejected with a clear message — "beta expired —
  subscribe at lens.r-lattice.com" — instead of continuing to work silently
  past the beta window. Existing keys (no expiry set) are unaffected.
- `mint_key.py` now accepts `--expires-days N` to set a key's expiry window at
  creation time.

## [1.2.10] — 2026-07-24
### Changed
- Dogfood report refreshed project-to-date through 2026-07-24 (same
  folder-scoped method, figures unedited): $207.55 actual vs $1,569.50
  without caching (simulated), 87% saved as headroom, five cents still
  recoverable. Landing hero figures updated in lockstep. Added an explicit
  method caveat: sessions launched outside the product folder are excluded,
  conservatively, from both columns.

## [1.2.9] — 2026-07-24
### Fixed
- A dropped pooled DB connection (idle SSL recycle) permanently poisoned the
  serving instance — every authenticated request 500'd until Cloud Run happened
  to replace the container (incident 2026-07-24, three requests lost). Storage
  now reopens the connection once and retries the statement on
  `psycopg.OperationalError`; sqlite/test paths are byte-identical (defaults
  catch nothing).
- `server/requirements.txt` pinned to the serving image's exact versions —
  rebuilds can no longer silently change the pooler-facing client library.

## [1.2.8] — 2026-07-22
### Removed
- The $1,918 demo-replay claim, per Ross — the hero now carries only the
  dogfood build figures and the report's supporting line (five cents left
  recoverable), linking straight to /dogfood.pdf.

## [1.2.7] — 2026-07-22
### Changed
- Hero now leads with the dogfood numbers ($191.83 vs $1,427.52 simulated
  uncached, 87% saved) — same figures as the report section, single-sourced
  in code so top and bottom can never disagree. Demo-replay recoverable
  ($1,918, simulated) stays as the secondary claim.

## [1.2.6] — 2026-07-22
### Added
- **Dogfood report.** Project-to-date cost analysis of the lens's own build,
  served at [/dogfood.pdf](https://lens.r-lattice.com/dogfood.pdf) and
  summarized on the landing page: $191.83 actual vs $1,427.52 without caching
  (simulated) across 74 sessions — 87% saved as headroom, $0.05 left
  recoverable. Generated by the shipped lens.py, figures unedited, every
  counterfactual labeled.

## [1.2.5] — 2026-07-22
### Changed
- **Version-free quickstart.** Install is now one line —
  `pip install "agent-cost-lens-mcp @ https://lens.r-lattice.com/download"` —
  verified against the live endpoint. No version number on the page, so it can
  never go stale; /download always serves the current build. (Also fixes the
  old two-step: `curl -LO` saved the file under the wrong name.)

## [1.2.4] — 2026-07-22
### Fixed
- Audit video length stated correctly (1:23, not 30 seconds) on the landing
  page and in the 1.2.1 entry below — the "30s" came from an internal show
  name, not the actual cut.

## [1.2.3] — 2026-07-22
### Changed
- Hero copy, Ross's exact phrasing: headline figure now reads
  "up to $1,918 of headroom recovered (simulated)."

## [1.2.2] — 2026-07-22
### Changed
- **Landing copy: "recover" → "save in headroom with efficiency gains."**
  Same honesty labels (every figure still "up to" + "(simulated)"), clearer
  framing — savings are usage headroom and efficiency, not found money.

## [1.2.1] — 2026-07-22
### Added
- **The audit, on video.** The landing page now embeds the 1:23
  ["Don't trust us — audit us"](https://youtu.be/EcxSYQlHWyQ) demo —
  click-to-load with the privacy-enhanced player, so nothing loads from
  YouTube until you press play.

## [1.2.0] — 2026-07-22
### Added
- **Public changelog page.** This release history is now served at
  [lens.r-lattice.com/changelog](https://lens.r-lattice.com/changelog) —
  rendered from this file, so the page can never drift from the record.
  Linked from the landing page and llms.txt.

## [1.1.1] — 2026-07-22
### Fixed
- **Sonnet 5 intro pricing honored.** Reports priced Sonnet 5 at the standard
  $3/$15 per MTok; Anthropic's introductory $2/$10 (through 2026-08-31) now
  applies by record date. Sonnet 5 costs in earlier reports were overstated by
  up to ~33% during the intro window — re-run for corrected figures.
- **Web fetch now free**, matching Anthropic's current pricing (was billed at
  $0.01/call).
### Added
- **Nightly pricing verification.** Rates are checked every night against
  Anthropic's published pricing pages by an automated watcher; any drift is
  corrected or escalated to a human — never silently ignored.

## [1.1.0] — 2026-07-20
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
