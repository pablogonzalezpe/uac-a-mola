# UAC-A-MOLA 2026 - Phase Tracker

Last update: 2026-03-20
Branch: feat/uacamola3-porting-smoke

## Phase 1 - Python 3 migration closure (uacamola)

### Done
- [x] Branch checked and clean working tree verified.
- [x] Non-destructive test suite executed successfully (`13 tests OK`).
- [x] Full package compile check executed (`python -m compileall -q uacamola`).
- [x] Smoke test of interactive console flow (`load/show/set/back/quit`) with an investigate module.
- [x] Import smoke for all modules in `attack`, `investigate`, `mitigation` (`15 modules imported`).

### Pending
- [ ] Add CI workflow (tests + compile checks) so this validation is automatic.
- [ ] Expand unit tests for support/mitigation surfaces with mocks.

## Phase 2 - Technical inventory and compatibility assessment (uacamola^3)

### Done
- [x] Inventory completed: 9 files in `uac-a-mola^3` (Ruby dispatcher/extension + Python meterpreter extension).
- [x] Main integration points identified:
  - Ruby command dispatcher: `.../ui/console/command_dispatcher/uacamola.rb`
  - Ruby extension API: `.../extensions/uacamola/*.rb`
  - Python extension server: `.../data/meterpreter/ext_server_uacamola.py`
- [x] Python syntax check executed on `ext_server_uacamola.py` (compiles, with escape-sequence warning).
- [x] Legacy compatibility risks identified in Python extension:
  - `xrange` still used.
  - `WindowsError` still used.
  - mixed `_winreg` / `winreg` compatibility paths.
  - invalid escape string in scheduled task command (`\Microsoft\windows...`).
- [x] Documentation drift identified in `uac-a-mola^3/README.md`:
  - hardcoded old Metasploit path (`gems/2.5.0`, payload version pin).

### Pending
- [ ] Create migrated layout for `uacamola^3` decoupled from hardcoded gem version paths.
- [x] Port `ext_server_uacamola.py` runtime issues (`xrange`, `WindowsError`, string escaping).
- [ ] Validate Ruby extension compatibility with current Metasploit framework API.
- [ ] Add `uacamola^3` test strategy (at least syntax/load checks, then VM functional checks).
- [ ] Update `uac-a-mola^3/README.md` for 2026 install/load flow.

## Porting sprint - uacamola^3 (in progress)

### Done in this sprint
- [x] Ported `ext_server_uacamola.py` to modern Python runtime semantics:
  - removed fragile Python 2/3 builtins override block.
  - normalized text decoding via `to_text`.
  - replaced legacy `xrange` and old registry exception patterns.
  - fixed escaped scheduled-task string.
  - fixed missing returns in `dll_hijacking_wusa` success/error paths.
  - kept `_winreg` fallback only as compatibility fallback.
- [x] Added defensive checks for missing `winreg` in meterpreter runtime.
- [x] Python syntax validation passed for `ext_server_uacamola.py`.
- [x] Hardened Ruby dispatcher loop (`uacamola.rb`):
  - removed `eval` execution path.
  - handles EOF/empty input safely.
  - reports unknown commands and missing usage params.

### Pending in this sprint
- [ ] Restructure `uacamola^3` packaging so paths are version-agnostic (not pinned to `gems/2.5.0/...`).
- [ ] Validate Ruby files with a Ruby runtime + minimal load test.
- [ ] Define install script/copy strategy for current Metasploit layouts.
- [ ] Run functional checks in VM with real meterpreter session.

## Status declaration - uacamola^3

### Accepted for now
- [x] `uacamola^3` accepted as **partial** for roadmap continuation.
- [x] Keep current focus on extension load/runtime compatibility and tooling.

### Explicitly pending (known gaps)
- [ ] Attack path validated end-to-end in supported meterpreter type.
- [ ] Mitigation path validated end-to-end in supported meterpreter type.
- [ ] Full functional parity claim with original scope.

## Phase 3 - MCP enablement for agent orchestration (Langflow-compatible)

### Goal
- Expose `uacamola` capabilities via MCP so an agent (e.g. Langflow) can run guided investigations.

### Done
- [x] Scope agreed: start with non-destructive investigative tools first.

### Pending
- [x] Define MCP tool contract v0:
  - `list_modules`
  - `show_module`
  - `set_option`
  - `run_investigate`
  - `parse_procmon_xml`
  - `search_events`
- [x] Implement MCP server skeleton (`stdio`) with structured JSON I/O.
- [x] Add guardrails:
  - deny `attack/*` and `mitigation/*` by default in local mode.
  - explicit allowlist switch for isolated VM mode.
- [ ] Add Langflow integration profile:
- [x] Add Langflow integration profile:
  - tool names
  - tool descriptions
  - expected input schemas
- [x] Add audit logging for each MCP tool call.
- [x] Add smoke tests for MCP server startup and tool discovery.

### MCP implementation notes (current)
- [x] Runtime MCP state added (`set_option` / `clear_module_state`).
- [x] Investigative execution bridge enabled in safe mode for:
  - `investigate.autoElevate_search`
- [x] Procmon data tools implemented:
  - `parse_procmon_xml`
  - `search_events`
- [ ] Expand safe execution allowlist after VM validation.
- [x] MCP runtime smoke tests added (`tests/test_mcp_server.py`).

## Decision log
- Continue and migrate `uacamola^3` as part of the 2026 roadmap.
- Keep destructive/offensive functional tests only in isolated VM.
- `uacamola^3` is considered partial-accepted for now; attack/mitigation validation remains explicitly pending.
- MCP line starts with investigative, non-destructive capabilities first.
