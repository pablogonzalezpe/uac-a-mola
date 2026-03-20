# uacamola MCP (v1 Skeleton)

This folder contains a first MCP skeleton to orchestrate `uacamola` from agents (for example Langflow), with a safe-by-default policy.

## Scope (v1)
- Non-destructive investigative tools only.
- `attack.*` and `mitigation.*` are denied by default.

## Implemented MCP tools
- `healthcheck`
- `tool_contract`
- `list_modules(kind)`
- `show_module(module_id)`
- `set_option(module_id, option_name, option_value)`
- `clear_module_state(module_id)`
- `run_investigate(module_id, options_json)`
- `parse_procmon_xml(xml_path)`
- `search_events(...)`

## Guardrails
- Execution allowlist is enabled by default.
- Current executable allowlist:
  - `investigate.autoElevate_search`
- Other modules can be inspected but not executed.
- Calls are logged in `mcp_uacamola/audit.log`.

## Run locally
1. Install dependency:
   - `pip install mcp`
2. Run server:
   - `python mcp_uacamola/server.py`

## Smoke test (local)
- `python -m unittest tests/test_mcp_server.py -v`

## Langflow profile
- Example profile file:
  - `mcp_uacamola/langflow_profile.json`
- It uses `stdio` transport and runs:
  - `python mcp_uacamola/server.py`

## Langflow integration idea
- Add this process as an MCP server over stdio.
- Use these tools in your agent chain:
  - discovery: `healthcheck`, `tool_contract`, `list_modules`, `show_module`
  - stateful prep: `set_option`, `clear_module_state`
  - execution: `run_investigate`
  - data analysis: `parse_procmon_xml`, `search_events`
