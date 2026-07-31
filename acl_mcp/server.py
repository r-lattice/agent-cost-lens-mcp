"""FastMCP stdio entry. Thin on purpose: all logic and copy live in core."""
from mcp.server.fastmcp import FastMCP

from acl_mcp import core

mcp = FastMCP("agent-cost-lens")


@mcp.tool()
def analyze_costs(since: str = "", until: str = "", apilog: str = "") -> str:
    """Analyze your Claude Code / Anthropic API token spend. Sweeps your local
    transcripts (or apilog JSONL files via `apilog` glob), scrubs identifiers
    on your machine, sends usage metadata only to your configured Agent Cost
    Lens server, and returns the cost summary with recoverable savings.
    Dates are YYYY-MM-DD. Use preview_upload first to audit what gets sent."""
    return core.run_analyze(since or None, until or None, apilog or None)


@mcp.tool()
def preview_upload(since: str = "", until: str = "", apilog: str = "",
                   limit: int = 5) -> str:
    """Show exactly what analyze_costs WOULD upload — the scrubbed records,
    nothing else. Sends nothing; needs no key. This is the audit step."""
    return core.build_preview(since or None, until or None, apilog or None, limit)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
