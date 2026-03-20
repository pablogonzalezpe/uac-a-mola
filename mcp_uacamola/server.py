#!/usr/bin/env python3
"""
MCP server for uacamola orchestration.

Scope v1:
- Investigative, non-destructive workflows first.
- attack/* and mitigation/* are denied by default.
"""

from __future__ import annotations

import datetime as dt
import importlib
import io
import json
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Dict, List

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    FastMCP = None  # type: ignore[assignment]
    _MCP_IMPORT_ERROR = exc
else:
    _MCP_IMPORT_ERROR = None


REPO_ROOT = Path(__file__).resolve().parents[1]
UACAMOLA_ROOT = REPO_ROOT / "uacamola"
MODULES_ROOT = UACAMOLA_ROOT / "modules"
AUDIT_LOG = REPO_ROOT / "mcp_uacamola" / "audit.log"
RUNTIME_DIR = REPO_ROOT / "mcp_uacamola" / "runtime"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if FastMCP is not None:
    mcp = FastMCP("uacamola-mcp")
else:
    class _DummyMCP:
        def tool(self):
            return lambda func: func

        def run(self):
            raise SystemExit(
                "Missing dependency 'mcp'. Install with: pip install mcp"
            )

    mcp = _DummyMCP()

MODULE_STATE: Dict[str, Dict[str, Any]] = {}
SAFE_EXECUTION_ALLOWLIST = {
    "investigate.autoElevate_search",
}


def _module_path_to_id(path: Path) -> str:
    rel = path.relative_to(MODULES_ROOT)
    return ".".join(rel.with_suffix("").parts)


def _module_id_to_path(module_id: str) -> Path:
    candidate = MODULES_ROOT.joinpath(*module_id.split(".")).with_suffix(".py")
    return candidate


def _deny_if_sensitive(module_id: str) -> None:
    if module_id.startswith("attack.") or module_id.startswith("mitigation."):
        raise ValueError(
            "Module blocked by default policy (attack/mitigation disabled in MCP local mode)."
        )


def _audit(tool: str, args: Dict[str, Any], status: str, error: str = "") -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "ts": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        "tool": tool,
        "status": status,
        "args": args,
        "error": error,
    }
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=True) + "\n")


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


def _load_custom_module(module_id: str):
    py_mod = f"uacamola.modules.{module_id}"
    mod = importlib.import_module(py_mod)
    if not hasattr(mod, "CustomModule"):
        raise ValueError(f"Module has no CustomModule class: {module_id}")
    return mod.CustomModule()


def _extract_options(module_obj) -> Dict[str, Dict[str, str]]:
    options = {}
    for name, value in module_obj.get_options_dict().items():
        options[name] = {
            "value": str(value[0]),
            "description": str(value[1]),
            "required": str(bool(value[2])).lower(),
        }
    return options


def _event_to_dict(event) -> Dict[str, str]:
    def _get(field: str) -> str:
        node = event.find(field)
        return node.text if node is not None and node.text is not None else ""

    return {
        "Process_Name": _get("Process_Name"),
        "PID": _get("PID"),
        "Operation": _get("Operation"),
        "Path": _get("Path"),
        "Result": _get("Result"),
        "Detail": _get("Detail"),
    }


@mcp.tool()
def list_modules(kind: str = "investigate") -> List[str]:
    """
    List module ids from uacamola/modules.
    kind accepted: investigate, attack, mitigation, all
    """
    valid = {"investigate", "attack", "mitigation", "all"}
    if kind not in valid:
        raise ValueError(f"Invalid kind: {kind}. Valid values: {sorted(valid)}")

    files = sorted(MODULES_ROOT.rglob("*.py"))
    files = [p for p in files if p.name != "__init__.py"]
    ids = [_module_path_to_id(p) for p in files]
    _audit("list_modules", {"kind": kind}, "ok")
    if kind == "all":
        return ids
    return [m for m in ids if m.startswith(kind + ".")]


@mcp.tool()
def show_module(module_id: str) -> Dict[str, Any]:
    """
    Return module metadata and options.
    Tries to import module for richer metadata; falls back to static view.
    """
    path = _module_id_to_path(module_id)
    result: Dict[str, Any] = {
        "module_id": module_id,
        "path": str(path),
        "exists": str(path.exists()).lower(),
        "category": module_id.split(".")[0] if "." in module_id else "unknown",
    }
    if not path.exists():
        _audit("show_module", {"module_id": module_id}, "error", "module_not_found")
        return result

    try:
        module_obj = _load_custom_module(module_id)
        result["information"] = module_obj.get_information()
        result["options"] = _extract_options(module_obj)
        _audit("show_module", {"module_id": module_id}, "ok")
    except Exception as error:
        result["import_error"] = str(error)
        _audit("show_module", {"module_id": module_id}, "error", str(error))
    return result


@mcp.tool()
def set_option(module_id: str, option_name: str, option_value: str) -> Dict[str, str]:
    """Persist a module option in MCP runtime state."""
    _deny_if_sensitive(module_id)
    MODULE_STATE.setdefault(module_id, {})[option_name] = option_value
    _audit(
        "set_option",
        {
            "module_id": module_id,
            "option_name": option_name,
            "option_value": option_value,
        },
        "ok",
    )
    return {
        "status": "ok",
        "module_id": module_id,
        "option_name": option_name,
        "option_value": option_value,
    }


@mcp.tool()
def clear_module_state(module_id: str) -> Dict[str, str]:
    """Clear cached options for a module."""
    MODULE_STATE.pop(module_id, None)
    _audit("clear_module_state", {"module_id": module_id}, "ok")
    return {"status": "ok", "module_id": module_id}


@mcp.tool()
def run_investigate(module_id: str, options_json: str = "{}") -> Dict[str, Any]:
    """
    Execute investigate module through a guarded runtime bridge.
    For safety v1, only an allowlist is executable.
    """
    try:
        _deny_if_sensitive(module_id)
        if not module_id.startswith("investigate."):
            raise ValueError("MCP supports run_investigate only for investigate.*")
        if module_id not in SAFE_EXECUTION_ALLOWLIST:
            raise ValueError(
                f"Module '{module_id}' is not enabled for execution in local MCP mode."
            )

        options = json.loads(options_json)
        if not isinstance(options, dict):
            raise ValueError("options_json must decode to a JSON object")

        path = _module_id_to_path(module_id)
        if not path.exists():
            raise FileNotFoundError(f"Module not found: {module_id}")

        module_obj = _load_custom_module(module_id)
        merged_options = dict(MODULE_STATE.get(module_id, {}))
        merged_options.update(options)

        if module_id == "investigate.autoElevate_search":
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            output_path = RUNTIME_DIR / "autoelevate_result.txt"
            merged_options["output"] = str(output_path)

        for key, value in merged_options.items():
            if key in module_obj.get_options_names():
                module_obj.set_value(key, value)

        if not module_obj.check_arguments():
            raise ValueError("Missing required arguments after merge (state + options_json)")

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            module_obj.run_module()

        out_file = merged_options.get("output", "")
        lines: List[str] = []
        if out_file:
            output_p = _resolve_path(str(out_file))
            if output_p.exists():
                lines = output_p.read_text(encoding="utf-8", errors="ignore").splitlines()

        result = {
            "status": "ok",
            "module_id": module_id,
            "applied_options": {k: str(v) for k, v in merged_options.items()},
            "stdout_tail": stdout_buf.getvalue()[-4000:],
            "stderr_tail": stderr_buf.getvalue()[-2000:],
            "output_lines": lines[:500],
            "output_line_count": len(lines),
        }
        _audit("run_investigate", {"module_id": module_id, "options": merged_options}, "ok")
        return result
    except json.JSONDecodeError as error:
        msg = f"Invalid options_json: {error}"
        _audit("run_investigate", {"module_id": module_id}, "error", msg)
        raise ValueError(msg) from error
    except Exception as error:
        _audit("run_investigate", {"module_id": module_id, "options_json": options_json}, "error", str(error))
        raise


@mcp.tool()
def parse_procmon_xml(xml_path: str) -> Dict[str, Any]:
    """Parse Procmon XML and return aggregate counts by operation."""
    args = {"xml_path": xml_path}
    try:
        from uacamola.support.procmonXMLparser import ProcmonXmlParser

        resolved = _resolve_path(xml_path)
        if not resolved.exists():
            raise FileNotFoundError(f"XML file not found: {resolved}")

        parser = ProcmonXmlParser(str(resolved))
        events = parser.parse()
        counts = {k: len(v) for k, v in events.items()}
        result = {
            "status": "ok",
            "xml_path": str(resolved),
            "operations": counts,
            "total_events": sum(counts.values()),
        }
        _audit("parse_procmon_xml", args, "ok")
        return result
    except Exception as error:
        _audit("parse_procmon_xml", args, "error", str(error))
        raise


@mcp.tool()
def search_events(
    xml_path: str,
    operation: str = "",
    result: str = "",
    process_name: str = "",
    pid: str = "",
    path: str = "",
    pattern_json: str = "[]",
    limit: int = 100,
) -> Dict[str, Any]:
    """Search events in procmon XML with optional filters."""
    args = {
        "xml_path": xml_path,
        "operation": operation,
        "result": result,
        "process_name": process_name,
        "pid": pid,
        "path": path,
        "pattern_json": pattern_json,
        "limit": limit,
    }
    try:
        from uacamola.support.procmonXMLparser import ProcmonXmlParser
        from uacamola.support import procmonXMLfilter as filt

        resolved = _resolve_path(xml_path)
        if not resolved.exists():
            raise FileNotFoundError(f"XML file not found: {resolved}")

        parser = ProcmonXmlParser(str(resolved))
        events = parser.parse()

        if operation:
            events = filt.by_operation(events, operation)
        if result:
            events = filt.by_result(events, result)
        if process_name:
            events = filt.by_process(events, process_name)
        if path:
            events = filt.by_path(events, path)
        if pid:
            events = filt.by_pid(events, pid)
        if pattern_json:
            pattern = json.loads(pattern_json)
            if pattern:
                events = filt.by_pattern(events, pattern)

        matched = []
        for op_name, op_events in events.items():
            for e in op_events:
                d = _event_to_dict(e)
                d["OperationGroup"] = op_name
                matched.append(d)
                if len(matched) >= limit:
                    break
            if len(matched) >= limit:
                break

        counts = {k: len(v) for k, v in events.items()}
        payload = {
            "status": "ok",
            "xml_path": str(resolved),
            "matched_count": len(matched),
            "operation_counts": counts,
            "events": matched,
        }
        _audit("search_events", args, "ok")
        return payload
    except Exception as error:
        _audit("search_events", args, "error", traceback.format_exc(limit=2))
        raise


@mcp.tool()
def healthcheck() -> Dict[str, Any]:
    """Basic MCP health endpoint."""
    data = {
        "status": "ok",
        "repo_root": str(REPO_ROOT),
        "modules_root": str(MODULES_ROOT),
        "runtime_dir": str(RUNTIME_DIR),
        "audit_log": str(AUDIT_LOG),
        "allowlist": sorted(SAFE_EXECUTION_ALLOWLIST),
    }
    _audit("healthcheck", {}, "ok")
    return data


@mcp.tool()
def tool_contract() -> Dict[str, Any]:
    """Return a compact MCP contract intended for agent/tool orchestration layers."""
    contract = {
        "name": "uacamola-mcp",
        "mode": "safe-default",
        "blocked_prefixes": ["attack.", "mitigation."],
        "execution_allowlist": sorted(SAFE_EXECUTION_ALLOWLIST),
        "tools": [
            {"name": "healthcheck", "intent": "server health and paths"},
            {"name": "list_modules", "intent": "discover available modules"},
            {"name": "show_module", "intent": "inspect metadata/options"},
            {"name": "set_option", "intent": "set runtime option for module"},
            {"name": "clear_module_state", "intent": "clear runtime option cache"},
            {
                "name": "run_investigate",
                "intent": "execute allowlisted investigate modules in guarded mode",
            },
            {"name": "parse_procmon_xml", "intent": "aggregate counts from procmon xml"},
            {"name": "search_events", "intent": "filter procmon events with constraints"},
        ],
    }
    _audit("tool_contract", {}, "ok")
    return contract


if __name__ == "__main__":
    mcp.run()
