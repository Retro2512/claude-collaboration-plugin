#!/usr/bin/env python3
"""Validate the public release shape for the ConsultClaude plugin."""

from __future__ import annotations

import importlib.util
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_NAME = "consultclaude"
MARKETPLACE_NAME = "consultclaude"
REPOSITORY_URL = "https://github.com/Retro2512/ConsultClaude"


def fail(message: str) -> None:
    raise AssertionError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"Missing required file: {path.relative_to(REPO_ROOT)}")
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"Expected JSON object in {path.relative_to(REPO_ROOT)}")
    return value


def assert_exists(relative_path: str) -> Path:
    path = REPO_ROOT / relative_path
    if not path.exists():
        fail(f"Missing required file: {relative_path}")
    return path


def assert_https_url(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.startswith("https://"):
        fail(f"{field} must be an absolute https:// URL")


def validate_required_files() -> None:
    required = [
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "install.ps1",
        "install.sh",
        ".agents/plugins/marketplace.json",
        ".github/workflows/ci.yml",
        f"plugins/{PLUGIN_NAME}/.codex-plugin/plugin.json",
        f"plugins/{PLUGIN_NAME}/.mcp.json",
        f"plugins/{PLUGIN_NAME}/scripts/consultclaude_cli.py",
        f"plugins/{PLUGIN_NAME}/scripts/consultclaude_mcp.py",
        f"plugins/{PLUGIN_NAME}/skills/{PLUGIN_NAME}/SKILL.md",
    ]
    for path in required:
        assert_exists(path)


def validate_marketplace() -> None:
    marketplace = load_json(REPO_ROOT / ".agents/plugins/marketplace.json")
    if marketplace.get("name") != MARKETPLACE_NAME:
        fail("Marketplace name must match the install selector.")
    if marketplace.get("interface", {}).get("displayName") != "ConsultClaude":
        fail("Marketplace display name is incorrect.")

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        fail("Marketplace must contain exactly one plugin entry.")

    entry = plugins[0]
    if entry.get("name") != PLUGIN_NAME:
        fail("Marketplace plugin name is incorrect.")
    if entry.get("source") != {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"}:
        fail("Marketplace source must point to the repo-local plugin path.")
    if entry.get("policy", {}).get("installation") != "AVAILABLE":
        fail("Marketplace installation policy must be AVAILABLE.")
    if entry.get("policy", {}).get("authentication") != "ON_INSTALL":
        fail("Marketplace authentication policy must be ON_INSTALL.")
    if entry.get("category") != "Productivity":
        fail("Marketplace category must be Productivity.")


def validate_manifest() -> None:
    manifest_path = REPO_ROOT / f"plugins/{PLUGIN_NAME}/.codex-plugin/plugin.json"
    manifest = load_json(manifest_path)
    raw_manifest = manifest_path.read_text(encoding="utf-8")

    if "[TODO:" in raw_manifest or "Local developer" in raw_manifest:
        fail("Plugin manifest still contains placeholder developer metadata.")
    if manifest.get("name") != PLUGIN_NAME:
        fail("Plugin manifest name is incorrect.")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", str(manifest.get("version", ""))):
        fail("Plugin version must be semver-like.")
    if manifest.get("repository") != REPOSITORY_URL:
        fail("Plugin repository URL is incorrect.")
    if manifest.get("homepage") != f"{REPOSITORY_URL}#readme":
        fail("Plugin homepage URL is incorrect.")
    if manifest.get("license") != "MIT":
        fail("Plugin license must be MIT.")

    author = manifest.get("author", {})
    if author.get("name") != "Azhika":
        fail("Plugin author name is incorrect.")
    assert_https_url(author.get("url", ""), "author.url")

    interface = manifest.get("interface", {})
    required_interface = [
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    ]
    missing = [field for field in required_interface if field not in interface]
    if missing:
        fail(f"Plugin interface is missing fields: {', '.join(missing)}")
    if interface.get("developerName") != "Azhika":
        fail("Plugin interface developerName is incorrect.")
    if interface.get("websiteURL") != REPOSITORY_URL:
        fail("Plugin interface websiteURL is incorrect.")
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or len(prompts) > 3 or not prompts:
        fail("Plugin defaultPrompt must contain 1 to 3 entries.")
    for prompt in prompts:
        if not isinstance(prompt, str) or len(prompt) > 128:
            fail("Plugin defaultPrompt entries must be strings of at most 128 characters.")


def validate_mcp_config() -> None:
    config = load_json(REPO_ROOT / f"plugins/{PLUGIN_NAME}/.mcp.json")
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or PLUGIN_NAME not in servers:
        fail("MCP config must declare the consultclaude server.")
    server = servers[PLUGIN_NAME]
    if server.get("command") not in {"python", "python3"}:
        fail("MCP server command should use python or python3.")
    if server.get("args") != ["./scripts/consultclaude_mcp.py"]:
        fail("MCP server args should point at the bundled MCP script.")


def validate_python() -> None:
    script_paths = [
        REPO_ROOT / f"plugins/{PLUGIN_NAME}/scripts/consultclaude_cli.py",
        REPO_ROOT / f"plugins/{PLUGIN_NAME}/scripts/consultclaude_mcp.py",
    ]
    for path in script_paths:
        py_compile.compile(str(path), doraise=True)

    env = os.environ.copy()
    env["CONSULTCLAUDE_CLAUDE_PATH"] = sys.executable
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / f"plugins/{PLUGIN_NAME}/scripts/consultclaude_cli.py"),
            "--prompt",
            "Smoke test",
            "--dry-run",
            "--output",
            "json",
            "--cwd",
            str(REPO_ROOT),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        fail(f"Bridge dry run failed: {completed.stderr or completed.stdout}")
    dry_run = json.loads(completed.stdout)
    if dry_run.get("ok") is not True or dry_run.get("dry_run") is not True:
        fail("Bridge dry run did not return expected metadata.")


def validate_mcp_smoke() -> None:
    mcp_path = REPO_ROOT / f"plugins/{PLUGIN_NAME}/scripts/consultclaude_mcp.py"
    spec = importlib.util.spec_from_file_location("consultclaude_mcp", mcp_path)
    if spec is None or spec.loader is None:
        fail("Could not import MCP server module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    tools_response = module.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = tools_response.get("result", {}).get("tools", [])
    names = {tool.get("name") for tool in tools}
    if {"consult_claude", "consultclaude_presets", "consultclaude_doctor"} - names:
        fail("MCP tools/list is missing expected tools.")
    consult_schema = next(tool["inputSchema"] for tool in tools if tool.get("name") == "consult_claude")
    allow_enum = consult_schema["properties"]["allow_tools"]["enum"]
    if "default" in allow_enum:
        fail("MCP consult_claude schema must not expose allow_tools=default.")

    models_response = module.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "consultclaude_presets", "arguments": {}},
        }
    )
    if "preset_modes" not in models_response.get("result", {}).get("content", [{}])[0].get("text", ""):
        fail("MCP consultclaude_presets tool did not return model presets.")

    os.environ["CONSULTCLAUDE_CLAUDE_PATH"] = sys.executable
    dry_response = module.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "consult_claude",
                "arguments": {
                    "prompt": "MCP dry run",
                    "dry_run": True,
                    "cwd": str(REPO_ROOT),
                    "auth_provider": "bedrock",
                    "provider_region": "us-east-1",
                },
            },
        }
    )
    dry_text = dry_response.get("result", {}).get("content", [{}])[0].get("text", "")
    if "CLAUDE_CODE_USE_BEDROCK" not in dry_text or '"auth_provider": "bedrock"' not in dry_text:
        fail("MCP consult_claude dry-run path did not include provider metadata.")

    doctor_response = module.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "consultclaude_doctor", "arguments": {"live": False, "cwd": str(REPO_ROOT)}},
        }
    )
    doctor_text = doctor_response.get("result", {}).get("content", [{}])[0].get("text", "")
    if "claude_candidates" not in doctor_text or "provider_summary" not in doctor_text:
        fail("MCP consultclaude_doctor did not return expected diagnostics.")
    os.environ.pop("CONSULTCLAUDE_CLAUDE_PATH", None)


def validate_runtime_security() -> None:
    cli_path = REPO_ROOT / f"plugins/{PLUGIN_NAME}/scripts/consultclaude_cli.py"
    spec = importlib.util.spec_from_file_location("consultclaude_cli", cli_path)
    if spec is None or spec.loader is None:
        fail("Could not import CLI module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fake_openai_key = "sk-" + "testSECRET1234567890"
    fake_aws_key = "AKIA" + "ABCDEFGHIJKLMNOP"
    fake_github_token = "ghp_" + "abcdefghijklmnopqrstuvwxyz123456"
    fake_bearer = "abcdefghijklmnopqrstuvwx"
    fake_slack_token = "xoxb-" + "123456789012-" + "abcdefghijklmnopqrstuvwxyz"
    secret_prompt = f"Review token {fake_openai_key} and AWS {fake_aws_key}."
    request = module.ConsultRequest(prompt=secret_prompt, context=f"github token {fake_github_token}")
    gathered_context = module.gather_context(request, REPO_ROOT)
    prompt_text = module.build_consultation_prompt(request, gathered_context)
    forbidden = [fake_openai_key, fake_aws_key, fake_github_token]
    if any(item in prompt_text for item in forbidden):
        fail("Redaction failed for prompt or context secrets.")

    redacted = module.redact_text(
        """
        token=plainsecret
        Authorization: Bearer {fake_bearer}
        {fake_slack_token}
        postgresql://user:password@example.com/db
        -----BEGIN PRIVATE KEY-----
        abc
        -----END PRIVATE KEY-----
        """.format(fake_bearer=fake_bearer, fake_slack_token=fake_slack_token)
    )
    for leaked in ["plainsecret", fake_bearer, "xoxb-", "password@example.com", "BEGIN PRIVATE KEY"]:
        if leaked in redacted:
            fail(f"Redaction missed secret pattern: {leaked}")

    provider_request = module.ConsultRequest(
        prompt="provider test",
        auth_provider="vertex",
        provider_project="demo-project",
        provider_region="us-central1",
    )
    provider_env = module.build_claude_environment(provider_request)
    if provider_env.get("CLAUDE_CODE_USE_VERTEX") != "1":
        fail("Vertex provider did not set CLAUDE_CODE_USE_VERTEX.")
    if provider_env.get("ANTHROPIC_VERTEX_PROJECT_ID") != "demo-project":
        fail("Vertex provider did not set project ID.")

    try:
        module.ConsultRequest(prompt="bad", allow_tools="default")
        module.build_claude_command(module.ConsultRequest(prompt="bad", allow_tools="default"), REPO_ROOT)
        fail("allow_tools=default should be rejected.")
    except ValueError:
        pass

    with tempfile.TemporaryDirectory() as transcript_dir:
        os.environ["CONSULTCLAUDE_CLAUDE_PATH"] = sys.executable
        result = module.run_consultation(
            module.ConsultRequest(
                prompt=secret_prompt,
                cwd=str(REPO_ROOT),
                save_transcript=transcript_dir,
                timeout_seconds=30,
            )
        )
        if result.get("ok"):
            fail("Expected fake Claude command to fail.")
        transcript_files = list(Path(transcript_dir).glob("*.json"))
        if len(transcript_files) != 1:
            fail("Expected one saved transcript.")
        transcript_text = transcript_files[0].read_text(encoding="utf-8")
        if any(item in transcript_text for item in forbidden):
            fail("Transcript persisted unredacted secrets.")
        os.environ.pop("CONSULTCLAUDE_CLAUDE_PATH", None)


def main() -> int:
    validate_required_files()
    validate_marketplace()
    validate_manifest()
    validate_mcp_config()
    validate_python()
    validate_mcp_smoke()
    validate_runtime_security()
    print("Public release validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
