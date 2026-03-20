#!/usr/bin/env python3
"""
Minimal MCP server skeleton for uacamola orchestration.

Scope v0:
- Investigative, non-destructive tooling only.
- attack/* and mitigation/* are denied by default.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency 'mcp'. Install with: pip install mcp"
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
UACAMOLA_ROOT = REPO_ROOT / "uacamola"
MODULES_ROOT = UACAMOLA_ROOT / "modules"

mcp = FastMCP("uacamola-mcp")


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
    files = [
        p for p in files
        if p.name != "__init__.py"
    ]
    ids = [_module_path_to_id(p) for p in files]
    if kind == "all":
        return ids
    return [m for m in ids if m.startswith(kind + ".")]


@mcp.tool()
def show_module(module_id: str) -> Dict[str, str]:
    """
    Return static metadata about a module file (path, exists, category).
    This does not execute the module.
    """
    path = _module_id_to_path(module_id)
    return {
        "module_id": module_id,
        "path": str(path),
        "exists": str(path.exists()),
        "category": module_id.split(".")[0] if "." in module_id else "unknown",
    }


@mcp.tool()
def run_investigate(module_id: str, options_json: str = "{}") -> Dict[str, str]:
    """
    MCP v0 placeholder for running investigate modules via controlled bridge.
    For now: only policy and input validation; no module execution yet.
    """
    _deny_if_sensitive(module_id)
    if not module_id.startswith("investigate."):
        raise ValueError("MCP v0 only supports investigate.* execution.")

    path = _module_id_to_path(module_id)
    if not path.exists():
        raise FileNotFoundError(f"Module not found: {module_id}")

    try:
        options = json.loads(options_json)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid options_json: {error}") from error

    return {
        "status": "not_implemented",
        "module_id": module_id,
        "module_path": str(path),
        "validated_options_count": str(len(options)),
        "message": "Execution bridge not implemented yet (planned in MCP v1).",
    }


@mcp.tool()
def healthcheck() -> Dict[str, str]:
    """Basic MCP health endpoint."""
    return {
        "status": "ok",
        "repo_root": str(REPO_ROOT),
        "modules_root": str(MODULES_ROOT),
    }


if __name__ == "__main__":
    mcp.run()
