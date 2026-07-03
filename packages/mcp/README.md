# openorg-mcp

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that
exposes [Open Org](https://openorg.good-ship.co.uk) data to AI agents.

## Public read-only tools

| Tool | Description |
|------|-------------|
| `get_profile` | Fetch an org's full profile JSON by org_id |
| `search_profiles` | Search by theme, place, or name |
| `get_ideas` | List published ideas for an org |
| `get_strategies` | List published strategies for an org |
| `get_evidence` | List evidence items from a profile |
| `get_graph` | Discovery graph data (nodes + edges) |
| `get_themes` | Controlled theme vocabulary |

## Resources

- `openorg://orgs/{org_id}/profile` — full profile JSON
- `openorg://orgs/{org_id}/ideas/{slug}` — individual idea
- `openorg://orgs/{org_id}/strategies/{slug}` — individual strategy
- `openorg://themes` — controlled vocabulary

## Transport

Set `MCP_TRANSPORT` to `stdio` (default, for Claude Desktop) or
`streamable-http` (for remote agents).

## Running

```bash
openorg-mcp                  # uses MCP_TRANSPORT env var (default: stdio)
python -m openorg_mcp.server
```