#!/usr/bin/env python3
"""Minimal stdio MCP server for ConsultClaude."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from consultclaude_cli import ConsultRequest, list_model_presets, run_consultation, run_doctor  # noqa: E402


SERVER_NAME = "consultclaude"
SERVER_VERSION = "0.2.0"


def log(message: str) -> None:
    print(f"[{SERVER_NAME}] {message}", file=sys.stderr, flush=True)


def send(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":")), flush=True)


def result_response(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def error_response(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def consultation_tool_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Question or task for Claude to critique, rethink, or ideate on.",
            },
            "mode": {
                "type": "string",
                "description": "Consultation mode.",
                "enum": [
                    "quick",
                    "design",
                    "layout",
                    "creative",
                    "copy",
                    "logic",
                    "architecture",
                    "review",
                    "stress-test",
                    "general",
                ],
            },
            "model": {
                "type": "string",
                "description": "Claude model alias such as sonnet, opus, fable, or a full model ID.",
            },
            "fallback_model": {
                "type": "string",
                "description": "Comma-separated fallback model chain, or 'none'.",
            },
            "effort": {
                "type": "string",
                "enum": ["low", "medium", "high", "xhigh", "max"],
            },
            "context": {
                "type": "string",
                "description": "Small curated context block. Do not include secrets.",
            },
            "context_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Text files to include as context, resolved relative to cwd.",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for resolving context files and running Claude.",
            },
            "auth_provider": {
                "type": "string",
                "enum": ["default", "claude", "anthropic", "bedrock", "vertex", "foundry", "anthropic-aws"],
                "description": "Claude Code auth/provider route. Default uses Claude Code's normal auth resolution.",
            },
            "provider_region": {
                "type": "string",
                "description": "Provider region for Bedrock, Vertex, or Anthropic AWS.",
            },
            "provider_project": {
                "type": "string",
                "description": "Vertex AI project ID.",
            },
            "provider_base_url": {
                "type": "string",
                "description": "Provider or gateway base URL override.",
            },
            "provider_resource": {
                "type": "string",
                "description": "Foundry resource name.",
            },
            "provider_workspace_id": {
                "type": "string",
                "description": "Anthropic AWS workspace ID.",
            },
            "allow_tools": {
                "type": "string",
                "enum": ["none", "read-only"],
                "description": "Default none keeps Claude advisory-only.",
            },
            "add_dirs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Directories Claude may read when allow_tools is read-only.",
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 10,
                "maximum": 1800,
            },
            "max_budget_usd": {
                "type": "number",
                "minimum": 0,
            },
            "max_context_chars": {
                "type": "integer",
                "minimum": 1000,
                "maximum": 250000,
            },
            "transport": {
                "type": "string",
                "enum": ["cli", "app-handoff"],
                "description": "Use cli for automatic response; app-handoff creates a manual Claude app prompt file.",
            },
            "response_format": {
                "type": "string",
                "enum": ["text", "json"],
            },
            "json_schema": {
                "type": "string",
                "description": "Optional JSON schema string passed through to Claude CLI.",
            },
            "save_transcript": {
                "type": "string",
                "description": "Optional directory for transcript JSON or app handoff files.",
            },
            "dry_run": {
                "type": "boolean",
                "description": "Return command metadata without calling Claude.",
            },
        },
        "required": ["prompt"],
        "additionalProperties": False,
    }


def tools_list() -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": "consult_claude",
                "description": (
                    "Ask local Claude Code for an advisory second opinion on design, layout, "
                    "creative direction, architecture, logic, copy, or review decisions."
                ),
                "inputSchema": consultation_tool_schema(),
            },
            {
                "name": "consultclaude_presets",
                "description": "Return supported mode presets and model-selection guidance for Claude consultations.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "consultclaude_doctor",
                "description": "Check Claude CLI discovery and optionally run a live auth/provider smoke test.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "live": {
                            "type": "boolean",
                            "description": "Run a live Claude smoke test to verify auth, quota, and provider routing.",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "Working directory for the doctor check.",
                        },
                        "auth_provider": {
                            "type": "string",
                            "enum": ["default", "claude", "anthropic", "bedrock", "vertex", "foundry", "anthropic-aws"],
                        },
                    },
                    "additionalProperties": False,
                },
            },
        ]
    }


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "consultclaude_presets":
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(list_model_presets(), indent=2),
                }
            ]
        }

    if name == "consultclaude_doctor":
        result = run_doctor(
            live=bool(arguments.get("live", False)),
            cwd=arguments.get("cwd"),
            auth_provider=arguments.get("auth_provider"),
        )
        return {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "isError": not bool(result.get("ok")),
        }

    if name != "consult_claude":
        raise ValueError(f"Unknown tool: {name}")

    request = ConsultRequest.from_mapping(arguments)
    result = run_consultation(request)
    if result.get("ok") and result.get("stdout"):
        text = str(result["stdout"]).strip()
    else:
        text = json.dumps(result, indent=2)
    return {"content": [{"type": "text", "text": text}], "isError": not bool(result.get("ok"))}


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    message_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if message_id is None:
        return None

    try:
        if method == "initialize":
            protocol_version = params.get("protocolVersion", "2025-06-18")
            return result_response(
                message_id,
                {
                    "protocolVersion": protocol_version,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            )
        if method == "ping":
            return result_response(message_id, {})
        if method == "tools/list":
            return result_response(message_id, tools_list())
        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(arguments, dict):
                raise ValueError("tools/call arguments must be an object")
            return result_response(message_id, call_tool(str(tool_name), arguments))
        if method in {"resources/list", "prompts/list"}:
            key = "resources" if method == "resources/list" else "prompts"
            return result_response(message_id, {key: []})
        return error_response(message_id, -32601, f"Method not found: {method}")
    except Exception as exc:
        log(str(exc))
        return error_response(message_id, -32000, str(exc))


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            log(f"Invalid JSON-RPC message: {exc}")
            continue
        response = handle_request(message)
        if response is not None:
            send(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
