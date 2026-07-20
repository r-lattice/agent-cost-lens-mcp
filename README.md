---
name: agent-cost-lens-mcp
description: See where your agent token money goes. Local sweep, local scrub, metadata-only upload — audit it yourself with preview_upload before anything is sent.
capabilities: [cost-analysis, cache-waste-detection, spend-reporting]
---

# Agent Cost Lens — MCP client

Two tools:
- **preview_upload** — shows exactly what would be sent (scrubbed usage
  metadata: token counts, model IDs, dates, pseudonymous tags). Sends nothing.
  Works with zero configuration.
- **analyze_costs** — sends that metadata to your Agent Cost Lens server and
  returns your spend, cache-hit rate, and what proper caching recovers
  (figures are simulated upper bounds, labeled as such).

## Privacy
Prompt text and code never leave your machine — the wire format has no field
for them. Repo and session names are HMAC-pseudonymized with a salt that
never leaves `~/.config/agent-cost-lens/salt`. Run preview_upload and read
the payload yourself; that output is the whole story.

## Setup
```json
{
  "mcpServers": {
    "agent-cost-lens": {
      "command": "acl-mcp",
      "env": {
        "LENS_SERVER_URL": "https://your-analyzer.example",
        "LENS_API_KEY": "acl_..."
      }
    }
  }
}
```
Install: `pip install <tarball>` (or `uvx --from <dir> acl-mcp`). Get a key
from the operator. `preview_upload` needs neither.
