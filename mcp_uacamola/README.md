# uacamola MCP (v0 Skeleton)

This folder contains a first MCP skeleton to orchestrate `uacamola` from agents (for example Langflow), with a safe-by-default policy.

## Scope (v0)
- Non-destructive investigative tools only.
- `attack.*` and `mitigation.*` are denied by default.
- No direct module execution bridge yet (validation-only placeholder).

## Implemented MCP tools
- `healthcheck`
- `list_modules(kind)`
- `show_module(module_id)`
- `run_investigate(module_id, options_json)` (placeholder)

## Run locally
1. Install dependency:
   - `pip install mcp`
2. Run server:
   - `python mcp_uacamola/server.py`

## Langflow integration idea
- Add this process as an MCP tool server over stdio.
- Expose only:
  - `healthcheck`
  - `list_modules`
  - `show_module`
  - `run_investigate`
- Keep execution bridge disabled until VM guardrails and audit logs are implemented.
