#!/usr/bin/env python3
"""Advisory bridge from Codex to local Claude Code."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 240
DEFAULT_MAX_CONTEXT_CHARS = 60000
VALID_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
VALID_ALLOW_TOOLS = {"none", "read-only"}
VALID_TRANSPORTS = {"cli", "app-handoff"}
VALID_RESPONSE_FORMATS = {"text", "json"}
VALID_AUTH_PROVIDERS = {"default", "claude", "anthropic", "bedrock", "vertex", "foundry", "anthropic-aws"}

AUTH_PROVIDER_ENV = "CONSULTCLAUDE_AUTH_PROVIDER"

MODE_PRESETS: dict[str, dict[str, str]] = {
    "quick": {
        "model": "sonnet",
        "effort": "low",
        "fallback_model": "sonnet",
        "summary": "Fast second opinion on one narrow question.",
    },
    "design": {
        "model": "opus",
        "effort": "medium",
        "fallback_model": "sonnet",
        "summary": "UX, layout, visual hierarchy, and interaction critique.",
    },
    "layout": {
        "model": "opus",
        "effort": "medium",
        "fallback_model": "sonnet",
        "summary": "Screen structure, responsive layout, density, and hierarchy.",
    },
    "creative": {
        "model": "opus",
        "effort": "medium",
        "fallback_model": "sonnet",
        "summary": "Divergent ideas, naming, product angles, and concept variants.",
    },
    "copy": {
        "model": "sonnet",
        "effort": "medium",
        "fallback_model": "sonnet",
        "summary": "User-facing copy, messaging, tone, and clarity.",
    },
    "logic": {
        "model": "opus",
        "effort": "high",
        "fallback_model": "sonnet",
        "summary": "Assumption checks, invariants, edge cases, and reasoning gaps.",
    },
    "architecture": {
        "model": "opus",
        "effort": "high",
        "fallback_model": "sonnet",
        "summary": "System design, module boundaries, sequencing, and tradeoffs.",
    },
    "review": {
        "model": "sonnet",
        "effort": "medium",
        "fallback_model": "sonnet",
        "summary": "Independent review of an approach, diff, or implementation plan.",
    },
    "stress-test": {
        "model": "opus",
        "effort": "high",
        "fallback_model": "sonnet",
        "summary": "Adversarial critique before major decisions or risky changes.",
    },
    "general": {
        "model": "sonnet",
        "effort": "medium",
        "fallback_model": "sonnet",
        "summary": "General advisory consultation.",
    },
}

MODE_GUIDANCE: dict[str, str] = {
    "quick": "Answer the narrow question directly. Mention only the most important tradeoff.",
    "design": (
        "Critique user flow, hierarchy, affordances, accessibility, states, spacing, "
        "and whether the design fits the product domain."
    ),
    "layout": (
        "Compare layout alternatives, responsive behavior, scanability, control placement, "
        "density, and likely failure cases."
    ),
    "creative": (
        "Generate distinct directions instead of small variations. Include why each direction "
        "works, where it fails, and which one you would try first."
    ),
    "copy": (
        "Rewrite toward plain, specific, believable language. Remove hype, vague claims, "
        "and AI-sounding filler."
    ),
    "logic": (
        "Challenge assumptions, list invariants, identify counterexamples, and point out "
        "where the reasoning can break."
    ),
    "architecture": (
        "Evaluate boundaries, data flow, operational risks, migration paths, and what should "
        "stay simple."
    ),
    "review": (
        "Act as an independent reviewer. Lead with defects or missing considerations, then "
        "summarize what is sound."
    ),
    "stress-test": (
        "Be skeptical. Find the strongest objections, hidden coupling, irreversible choices, "
        "and validation gaps."
    ),
    "general": "Give practical advice, alternatives, and risks. State assumptions explicitly.",
}


@dataclass
class ConsultRequest:
    prompt: str
    mode: str = "general"
    model: str | None = None
    fallback_model: str | None = None
    effort: str | None = None
    context: str | None = None
    context_files: list[str] = field(default_factory=list)
    add_dirs: list[str] = field(default_factory=list)
    cwd: str | None = None
    auth_provider: str | None = None
    provider_region: str | None = None
    provider_project: str | None = None
    provider_base_url: str | None = None
    provider_resource: str | None = None
    provider_workspace_id: str | None = None
    allow_tools: str = "none"
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_budget_usd: float | None = None
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS
    redact: bool = True
    transport: str = "cli"
    response_format: str = "text"
    json_schema: str | None = None
    save_transcript: str | None = None
    dry_run: bool = False

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "ConsultRequest":
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        payload = {key: value for key, value in raw.items() if key in allowed}
        if "prompt" not in payload or not str(payload["prompt"]).strip():
            raise ValueError("prompt is required")
        for list_key in ("context_files", "add_dirs"):
            value = payload.get(list_key)
            if value is None:
                payload[list_key] = []
            elif isinstance(value, str):
                payload[list_key] = [value]
            elif isinstance(value, list):
                payload[list_key] = [str(item) for item in value]
            else:
                raise ValueError(f"{list_key} must be a string or array of strings")
        return cls(**payload)


def list_model_presets() -> dict[str, Any]:
    return {
        "preset_modes": MODE_PRESETS,
        "model_input": (
            "Pass any Claude Code model alias such as 'sonnet', 'opus', or 'fable', "
            "or pass a full model ID supported by the installed Claude CLI."
        ),
        "environment_overrides": {
            "CONSULTCLAUDE_AUTH_PROVIDER": "Default auth provider: default, bedrock, vertex, foundry, or anthropic-aws.",
            "CONSULTCLAUDE_MODEL": "Default model when request.model is omitted.",
            "CONSULTCLAUDE_FALLBACK_MODEL": "Comma-separated fallback chain.",
            "CONSULTCLAUDE_EFFORT": "Default effort when request.effort is omitted.",
            "CONSULTCLAUDE_CLAUDE_PATH": "Command name on PATH or explicit path to claude executable / claude.ps1.",
        },
        "auth_providers": {
            "default": "Use Claude Code's normal auth resolution: subscription login, API key, or configured provider.",
            "bedrock": "Set CLAUDE_CODE_USE_BEDROCK=1 for this consultation.",
            "vertex": "Set CLAUDE_CODE_USE_VERTEX=1 for this consultation.",
            "foundry": "Set CLAUDE_CODE_USE_FOUNDRY=1 for this consultation.",
            "anthropic-aws": "Set CLAUDE_CODE_USE_ANTHROPIC_AWS=1 for this consultation.",
        },
    }


def normalize_mode(mode: str | None) -> str:
    if not mode:
        return "general"
    normalized = str(mode).strip().lower()
    return normalized if normalized in MODE_PRESETS else "general"


def resolve_cwd(cwd: str | None) -> Path:
    if cwd:
        resolved = Path(cwd).expanduser().resolve()
    else:
        resolved = Path.cwd().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"cwd does not exist or is not a directory: {resolved}")
    return resolved


def resolve_path(path_text: str, cwd: Path) -> Path:
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def unique_existing_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    found: list[Path] = []
    for path in paths:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        key = str(resolved).lower() if os.name == "nt" else str(resolved)
        if key not in seen and resolved.exists() and resolved.is_file():
            seen.add(key)
            found.append(resolved)
    return found


def path_from_command_or_path(text: str) -> Path:
    candidate = Path(text).expanduser()
    if not candidate.is_absolute() and len(candidate.parts) == 1:
        resolved_command = shutil.which(text)
        if resolved_command:
            return Path(resolved_command)
    return candidate


def find_claude_candidates() -> list[Path]:
    candidates: list[Path] = []
    override = os.environ.get("CONSULTCLAUDE_CLAUDE_PATH")
    if override:
        candidates.append(path_from_command_or_path(override))

    path_candidate = shutil.which("claude")
    if path_candidate:
        candidates.append(Path(path_candidate))

    home = Path.home()
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            npm_dir = Path(appdata) / "npm"
            candidates.extend(
                [
                    npm_dir / "claude.ps1",
                    npm_dir / "claude.cmd",
                    npm_dir / "claude.exe",
                    npm_dir / "claude",
                ]
            )
    else:
        candidates.extend(
            [
                home / ".local" / "bin" / "claude",
                home / ".npm-global" / "bin" / "claude",
                Path("/opt/homebrew/bin/claude"),
                Path("/usr/local/bin/claude"),
                Path("/usr/bin/claude"),
            ]
        )

    return unique_existing_paths(candidates)


def command_from_claude_path(candidate: Path) -> list[str]:
    suffix = candidate.suffix.lower()
    if suffix == ".ps1":
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not powershell:
            raise FileNotFoundError("Cannot run claude.ps1 because PowerShell was not found.")
        return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(candidate)]
    return [str(candidate)]


def resolve_claude_command() -> list[str]:
    override = os.environ.get("CONSULTCLAUDE_CLAUDE_PATH")
    candidates = find_claude_candidates()
    if not candidates:
        raise FileNotFoundError(
            "Claude CLI was not found on PATH. Install/sign in to Claude Code, "
            "set CONSULTCLAUDE_CLAUDE_PATH, or use --transport app-handoff."
        )

    if override:
        override_path = path_from_command_or_path(override).expanduser().resolve()
        if override_path not in candidates:
            raise FileNotFoundError(
                f"CONSULTCLAUDE_CLAUDE_PATH does not point to a file or command on PATH: {override}"
            )
        return command_from_claude_path(override_path)

    return command_from_claude_path(candidates[0])


SECRET_PATTERNS = [
    re.compile(
        r"(?i)\b(api[_-]?key|token|secret|password|authorization)\b\s*[:=]\s*([^\s,;]+)"
    ),
    re.compile(r"(?i)\b(bearer\s+)[a-z0-9._\-+/=]{12,}"),
    re.compile(r"\b((?:sk|sk-ant|sk-proj)-[A-Za-z0-9_\-]{12,})\b"),
    re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    re.compile(r"\b(ASIA[0-9A-Z]{16})\b"),
    re.compile(r"\b((?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\b(github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\b(AIza[0-9A-Za-z_\-]{20,})\b"),
    re.compile(r"\b(xox[baprs]-[0-9A-Za-z-]{20,})\b"),
    re.compile(r"\b([A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,})\b"),
    re.compile(r"(?i)\b((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^@\s]+:[^@\s]+@[^ \n\r]+)"),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.DOTALL),
]


def redact_text(text: str) -> str:
    redacted = text
    redacted = SECRET_PATTERNS[1].sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[0].sub(lambda match: f"{match.group(1)}=[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[2].sub("[REDACTED_API_KEY]", redacted)
    redacted = SECRET_PATTERNS[3].sub("[REDACTED_AWS_ACCESS_KEY_ID]", redacted)
    redacted = SECRET_PATTERNS[4].sub("[REDACTED_AWS_TEMP_ACCESS_KEY_ID]", redacted)
    redacted = SECRET_PATTERNS[5].sub("[REDACTED_GITHUB_TOKEN]", redacted)
    redacted = SECRET_PATTERNS[6].sub("[REDACTED_GITHUB_TOKEN]", redacted)
    redacted = SECRET_PATTERNS[7].sub("[REDACTED_GOOGLE_API_KEY]", redacted)
    redacted = SECRET_PATTERNS[8].sub("[REDACTED_SLACK_TOKEN]", redacted)
    redacted = SECRET_PATTERNS[9].sub("[REDACTED_JWT]", redacted)
    redacted = SECRET_PATTERNS[10].sub("[REDACTED_CONNECTION_STRING]", redacted)
    redacted = SECRET_PATTERNS[11].sub("[REDACTED_PRIVATE_KEY]", redacted)
    return redacted


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_value(item) for key, item in value.items()}
    return value


def read_limited_text(path: Path, max_chars: int, redact: bool) -> str:
    if not path.exists():
        return f"[missing file: {path}]"
    if not path.is_file():
        return f"[not a regular file: {path}]"
    raw = path.read_text(encoding="utf-8", errors="replace")
    if redact:
        raw = redact_text(raw)
    if len(raw) <= max_chars:
        return raw
    return raw[:max_chars] + f"\n\n[truncated after {max_chars} characters]"


def gather_context(request: ConsultRequest, cwd: Path) -> str:
    chunks: list[str] = []
    remaining = max(0, int(request.max_context_chars))

    if request.context:
        context = redact_text(request.context) if request.redact else request.context
        chunks.append("## Inline Context\n\n" + context[:remaining])
        remaining -= min(len(context), remaining)

    for file_name in request.context_files:
        if remaining <= 0:
            chunks.append(f"## Context File Skipped\n\nNo context budget left for `{file_name}`.")
            continue
        path = resolve_path(file_name, cwd)
        content = read_limited_text(path, remaining, request.redact)
        chunks.append(f"## Context File: {path}\n\n{content}")
        remaining -= min(len(content), remaining)

    return "\n\n".join(chunks).strip()


def build_consultation_prompt(request: ConsultRequest, gathered_context: str) -> str:
    mode = normalize_mode(request.mode)
    guidance = MODE_GUIDANCE[mode]
    sections = [
        "# Claude Advisory Consultation",
        (
            "You are Claude advising Codex in a separate local consultation. Codex remains "
            "responsible for final decisions, file edits, commands, tests, and user-facing output."
        ),
        "Do not claim you edited files, ran commands, or inspected data that is not provided here.",
        "Prefer practical, specific recommendations over broad theory.",
        "Call out assumptions, missing context, and where Codex should verify before acting.",
        f"Consultation mode: {mode}",
        f"Mode guidance: {guidance}",
        "Return a concise response with: recommendation, reasoning, alternatives, risks, and next checks.",
        "# Request",
        redact_text(request.prompt.strip()) if request.redact else request.prompt.strip(),
    ]

    if gathered_context:
        sections.extend(["# Provided Context", gathered_context])
    else:
        sections.extend(
            [
                "# Provided Context",
                "No extra project context was provided. Base the answer only on the request.",
            ]
        )

    return "\n\n".join(sections).strip() + "\n"


def effective_model_options(request: ConsultRequest) -> dict[str, str | None]:
    mode = normalize_mode(request.mode)
    preset = MODE_PRESETS[mode]

    model = request.model or os.environ.get("CONSULTCLAUDE_MODEL") or preset["model"]
    if model == "auto":
        model = preset["model"]

    effort = request.effort or os.environ.get("CONSULTCLAUDE_EFFORT") or preset["effort"]
    if effort and effort not in VALID_EFFORTS:
        raise ValueError(f"effort must be one of {sorted(VALID_EFFORTS)}")

    fallback_model = (
        request.fallback_model
        or os.environ.get("CONSULTCLAUDE_FALLBACK_MODEL")
        or preset.get("fallback_model")
    )
    if fallback_model == "none":
        fallback_model = None

    return {"model": model, "effort": effort, "fallback_model": fallback_model}


def normalize_auth_provider(provider: str | None) -> str:
    raw = provider or os.environ.get(AUTH_PROVIDER_ENV) or "default"
    normalized = raw.strip().lower()
    if normalized in {"claude", "anthropic"}:
        return "default"
    if normalized not in VALID_AUTH_PROVIDERS:
        raise ValueError(f"auth_provider must be one of {sorted(VALID_AUTH_PROVIDERS)}")
    return normalized


def build_claude_environment(request: ConsultRequest) -> dict[str, str]:
    env = os.environ.copy()
    provider = normalize_auth_provider(request.auth_provider)

    if provider == "bedrock":
        env["CLAUDE_CODE_USE_BEDROCK"] = "1"
        if request.provider_region:
            env["AWS_REGION"] = request.provider_region
            env.setdefault("AWS_DEFAULT_REGION", request.provider_region)
        if request.provider_base_url:
            env["ANTHROPIC_BEDROCK_BASE_URL"] = request.provider_base_url
    elif provider == "vertex":
        env["CLAUDE_CODE_USE_VERTEX"] = "1"
        if request.provider_project:
            env["ANTHROPIC_VERTEX_PROJECT_ID"] = request.provider_project
        if request.provider_region:
            env["CLOUD_ML_REGION"] = request.provider_region
        if request.provider_base_url:
            env["ANTHROPIC_VERTEX_BASE_URL"] = request.provider_base_url
    elif provider == "foundry":
        env["CLAUDE_CODE_USE_FOUNDRY"] = "1"
        if request.provider_resource:
            env["ANTHROPIC_FOUNDRY_RESOURCE"] = request.provider_resource
        if request.provider_base_url:
            env["ANTHROPIC_FOUNDRY_BASE_URL"] = request.provider_base_url
    elif provider == "anthropic-aws":
        env["CLAUDE_CODE_USE_ANTHROPIC_AWS"] = "1"
        if request.provider_region:
            env["AWS_REGION"] = request.provider_region
            env.setdefault("AWS_DEFAULT_REGION", request.provider_region)
        if request.provider_base_url:
            env["ANTHROPIC_AWS_BASE_URL"] = request.provider_base_url
        if request.provider_workspace_id:
            env["ANTHROPIC_AWS_WORKSPACE_ID"] = request.provider_workspace_id

    return env


def provider_summary(env: dict[str, str], provider: str) -> dict[str, Any]:
    keys = [
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_MODEL",
        "CLAUDE_CODE_USE_BEDROCK",
        "AWS_PROFILE",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "ANTHROPIC_BEDROCK_BASE_URL",
        "AWS_BEARER_TOKEN_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "ANTHROPIC_VERTEX_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
        "GCLOUD_PROJECT",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "CLOUD_ML_REGION",
        "ANTHROPIC_VERTEX_BASE_URL",
        "CLAUDE_CODE_USE_FOUNDRY",
        "ANTHROPIC_FOUNDRY_RESOURCE",
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "CLAUDE_CODE_USE_ANTHROPIC_AWS",
        "ANTHROPIC_AWS_WORKSPACE_ID",
        "ANTHROPIC_AWS_BASE_URL",
    ]
    configured = {key: ("set" if key in env and env[key] else "unset") for key in keys}
    return {
        "auth_provider": provider,
        "configured_environment": configured,
        "note": "Values are summarized as set/unset only; secrets are not printed.",
    }


def build_claude_command(request: ConsultRequest, cwd: Path) -> list[str]:
    if request.allow_tools not in VALID_ALLOW_TOOLS:
        raise ValueError(f"allow_tools must be one of {sorted(VALID_ALLOW_TOOLS)}")
    if request.response_format not in VALID_RESPONSE_FORMATS:
        raise ValueError(f"response_format must be one of {sorted(VALID_RESPONSE_FORMATS)}")

    options = effective_model_options(request)
    command = resolve_claude_command()
    command.extend(
        [
            "--print",
            "--input-format",
            "text",
            "--output-format",
            request.response_format,
            "--model",
            str(options["model"]),
            "--effort",
            str(options["effort"]),
            "--no-session-persistence",
            "--permission-mode",
            "plan",
            "--append-system-prompt",
            (
                "You are an advisory collaborator for Codex. Do not edit files or run commands "
                "unless explicitly granted tools. Keep advice concrete and bounded."
            ),
        ]
    )

    if options["fallback_model"]:
        command.extend(["--fallback-model", str(options["fallback_model"])])

    if request.allow_tools == "none":
        command.extend(["--tools", "", "--disallowedTools", "mcp__*"])
    elif request.allow_tools == "read-only":
        command.extend(["--tools", "Read,Grep,Glob,LS", "--disallowedTools", "Edit,Write,Bash"])
        for directory in request.add_dirs:
            command.extend(["--add-dir", str(resolve_path(directory, cwd))])

    if request.max_budget_usd is not None:
        command.extend(["--max-budget-usd", str(request.max_budget_usd)])

    if request.json_schema:
        command.extend(["--json-schema", request.json_schema])

    return command


def classify_claude_failure(stderr: str, stdout: str = "") -> dict[str, str]:
    text = f"{stderr}\n{stdout}".lower()
    if "not found" in text or "not recognized" in text:
        return {
            "category": "claude_not_found",
            "remediation": "Install Claude Code and ensure `claude` is on PATH, or set CONSULTCLAUDE_CLAUDE_PATH.",
        }
    if "login" in text or "not authenticated" in text or "authentication" in text or "unauthorized" in text:
        return {
            "category": "auth_required",
            "remediation": "Run `claude` interactively and complete login, or configure the intended API/provider credentials.",
        }
    if "api key" in text and ("invalid" in text or "missing" in text or "required" in text):
        return {
            "category": "api_key_problem",
            "remediation": "Check ANTHROPIC_API_KEY or unset it if you want Claude Code to use your subscription login.",
        }
    if "quota" in text or "rate limit" in text or "billing" in text or "credit" in text:
        return {
            "category": "quota_or_billing",
            "remediation": "Check the active Claude subscription, Console billing, or cloud-provider quota for the selected auth provider.",
        }
    if "exceeded usd budget" in text or "max-budget-usd" in text:
        return {
            "category": "budget_cap_too_low",
            "remediation": "Increase the live doctor budget cap or run Claude directly to verify auth without a ConsultClaude budget cap.",
        }
    if "bedrock" in text or "aws" in text:
        return {
            "category": "bedrock_or_aws_config",
            "remediation": "Verify AWS credentials, AWS_REGION, Bedrock model access, and CLAUDE_CODE_USE_BEDROCK settings.",
        }
    if "vertex" in text or "gcloud" in text or "projectid" in text or "google" in text:
        return {
            "category": "vertex_or_gcp_config",
            "remediation": "Verify gcloud credentials, project ID, region, and CLAUDE_CODE_USE_VERTEX settings.",
        }
    if "foundry" in text or "azure" in text:
        return {
            "category": "foundry_config",
            "remediation": "Verify Foundry resource/base URL and ANTHROPIC_FOUNDRY_* credentials.",
        }
    return {
        "category": "unknown",
        "remediation": "Run `claude` directly with the same provider environment to inspect the full error.",
    }


def command_for_display(command: list[str]) -> list[str]:
    return ["[empty-arg]" if arg == "" else arg for arg in command]


def sanitize_request_for_storage(request: ConsultRequest) -> dict[str, Any]:
    data = asdict(request)
    if request.redact:
        data = redact_value(data)
    return data


def sanitize_result(result: dict[str, Any], redact: bool) -> dict[str, Any]:
    if not redact:
        return result
    sanitized = dict(result)
    for key in ("stdout", "stderr", "error"):
        if isinstance(sanitized.get(key), str):
            sanitized[key] = redact_text(str(sanitized[key]))
    return sanitized


def create_app_handoff(request: ConsultRequest, prompt_text: str, cwd: Path) -> dict[str, Any]:
    target_dir = Path(request.save_transcript).expanduser() if request.save_transcript else cwd / ".codex" / "claude-handoffs"
    if not target_dir.is_absolute():
        target_dir = cwd / target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    handoff_path = target_dir / f"claude-handoff-{timestamp}.md"
    handoff_path.write_text(prompt_text, encoding="utf-8")
    return {
        "ok": True,
        "transport": "app-handoff",
        "handoff_path": str(handoff_path),
        "message": (
            "Created a Claude app handoff prompt. Automatic request/response is only available "
            "through the CLI transport; paste this prompt into the Claude app when a manual "
            "fallback is needed."
        ),
    }


def save_transcript(request: ConsultRequest, prompt_text: str, result: dict[str, Any], cwd: Path) -> None:
    if not request.save_transcript:
        return
    target_dir = Path(request.save_transcript).expanduser()
    if not target_dir.is_absolute():
        target_dir = cwd / target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    transcript = {
        "request": sanitize_request_for_storage(request),
        "prompt": prompt_text,
        "result": sanitize_result(result, request.redact),
    }
    (target_dir / f"claude-consult-{timestamp}.json").write_text(
        json.dumps(transcript, indent=2),
        encoding="utf-8",
    )


def run_consultation(request: ConsultRequest) -> dict[str, Any]:
    if request.transport not in VALID_TRANSPORTS:
        raise ValueError(f"transport must be one of {sorted(VALID_TRANSPORTS)}")

    cwd = resolve_cwd(request.cwd)
    gathered_context = gather_context(request, cwd)
    prompt_text = build_consultation_prompt(request, gathered_context)

    if request.transport == "app-handoff":
        return create_app_handoff(request, prompt_text, cwd)

    command = build_claude_command(request, cwd)
    options = effective_model_options(request)
    provider = normalize_auth_provider(request.auth_provider)
    env = build_claude_environment(request)

    if request.dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "cwd": str(cwd),
            "command": command_for_display(command),
            "model": options["model"],
            "effort": options["effort"],
            "fallback_model": options["fallback_model"],
            "auth_provider": provider,
            "provider_summary": provider_summary(env, provider),
            "prompt_chars": len(prompt_text),
        }

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            input=prompt_text,
            cwd=str(cwd),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=int(request.timeout_seconds),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        result = {
            "ok": False,
            "error": f"Claude consultation timed out after {request.timeout_seconds} seconds.",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "command": command_for_display(command),
        }
        result = sanitize_result(result, request.redact)
        save_transcript(request, prompt_text, result, cwd)
        return result

    result = {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "command": command_for_display(command),
        "model": options["model"],
        "effort": options["effort"],
        "fallback_model": options["fallback_model"],
        "auth_provider": provider,
    }
    if not result["ok"]:
        result["diagnosis"] = classify_claude_failure(completed.stderr, completed.stdout)
    result = sanitize_result(result, request.redact)
    save_transcript(request, prompt_text, result, cwd)
    return result


def run_doctor(live: bool = False, cwd: str | None = None, auth_provider: str | None = None) -> dict[str, Any]:
    doctor_request = ConsultRequest(prompt="ConsultClaude doctor", cwd=cwd, auth_provider=auth_provider)
    provider = normalize_auth_provider(auth_provider)
    env = build_claude_environment(doctor_request)
    result: dict[str, Any] = {
        "ok": False,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
            "executable": sys.executable,
        },
        "auth_provider": provider,
        "provider_summary": provider_summary(env, provider),
        "claude_candidates": [str(path) for path in find_claude_candidates()],
        "checks": [],
    }

    try:
        command = resolve_claude_command()
    except Exception as exc:
        result["checks"].append({"name": "resolve_claude", "ok": False, "error": str(exc)})
        result["diagnosis"] = classify_claude_failure(str(exc))
        return result

    result["claude_command"] = command_for_display(command)
    version_completed = subprocess.run(
        command + ["--version"],
        cwd=str(resolve_cwd(cwd)),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )
    version_ok = version_completed.returncode == 0
    result["checks"].append(
        {
            "name": "claude_version",
            "ok": version_ok,
            "returncode": version_completed.returncode,
            "stdout": redact_text(version_completed.stdout).strip(),
            "stderr": redact_text(version_completed.stderr).strip(),
        }
    )
    if not version_ok:
        result["diagnosis"] = classify_claude_failure(version_completed.stderr, version_completed.stdout)
        return result

    if live:
        smoke = ConsultRequest(
            prompt="Reply with exactly: ConsultClaude ready",
            mode="quick",
            cwd=cwd,
            auth_provider=auth_provider,
            timeout_seconds=90,
            max_budget_usd=0.10,
            max_context_chars=1000,
        )
        smoke_result = run_consultation(smoke)
        result["checks"].append(
            {
                "name": "claude_live_smoke",
                "ok": bool(smoke_result.get("ok")),
                "returncode": smoke_result.get("returncode"),
                "elapsed_seconds": smoke_result.get("elapsed_seconds"),
                "diagnosis": smoke_result.get("diagnosis"),
                "stdout_preview": redact_text(str(smoke_result.get("stdout", "")))[:500],
                "stderr_preview": redact_text(str(smoke_result.get("stderr", "")))[:500],
            }
        )
        if not smoke_result.get("ok"):
            result["diagnosis"] = smoke_result.get("diagnosis") or classify_claude_failure(
                str(smoke_result.get("stderr", "")), str(smoke_result.get("stdout", ""))
            )
            return result
    else:
        result["checks"].append(
            {
                "name": "claude_live_smoke",
                "ok": None,
                "skipped": True,
                "message": "Run with --doctor-live to verify auth, subscription, quota, and provider routing.",
            }
        )

    result["ok"] = all(check.get("ok") is not False for check in result["checks"])
    return result


def read_prompt_from_args(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.prompt:
        parts.append(args.prompt)
    if args.prompt_file:
        path = Path(args.prompt_file).expanduser().resolve()
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    if not parts and not sys.stdin.isatty():
        stdin_text = sys.stdin.read()
        if stdin_text.strip():
            parts.append(stdin_text)
    prompt = "\n\n".join(part.strip() for part in parts if part.strip())
    if not prompt:
        raise ValueError("Provide --prompt, --prompt-file, or stdin text.")
    return prompt


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ask local Claude Code for advisory input.")
    parser.add_argument("--prompt", help="Consultation question or task.")
    parser.add_argument("--prompt-file", help="File containing the consultation prompt.")
    parser.add_argument("--mode", default="general", help=f"Consultation mode: {', '.join(MODE_PRESETS)}")
    parser.add_argument("--model", help="Claude model alias or full model ID. Use 'auto' for mode default.")
    parser.add_argument("--fallback-model", help="Comma-separated fallback model chain, or 'none'.")
    parser.add_argument("--effort", choices=sorted(VALID_EFFORTS), help="Claude effort level.")
    parser.add_argument("--context", help="Inline context to include.")
    parser.add_argument("--context-file", action="append", default=[], help="Context file to include. Repeatable.")
    parser.add_argument("--add-dir", action="append", default=[], help="Directory Claude may read in read-only mode.")
    parser.add_argument("--cwd", help="Working directory for the Claude invocation.")
    parser.add_argument(
        "--auth-provider",
        choices=sorted(VALID_AUTH_PROVIDERS),
        help="Claude Code auth/provider route. Defaults to Claude Code's normal auth resolution.",
    )
    parser.add_argument("--provider-region", help="Provider region for Bedrock, Vertex, or Anthropic AWS.")
    parser.add_argument("--provider-project", help="Vertex AI project ID.")
    parser.add_argument("--provider-base-url", help="Provider or gateway base URL override.")
    parser.add_argument("--provider-resource", help="Foundry resource name.")
    parser.add_argument("--provider-workspace-id", help="Anthropic AWS workspace ID.")
    parser.add_argument("--allow-tools", choices=sorted(VALID_ALLOW_TOOLS), default="none")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-budget-usd", type=float)
    parser.add_argument("--max-context-chars", type=int, default=DEFAULT_MAX_CONTEXT_CHARS)
    parser.add_argument("--no-redact", action="store_true", help="Disable basic secret redaction.")
    parser.add_argument("--transport", choices=sorted(VALID_TRANSPORTS), default="cli")
    parser.add_argument("--response-format", choices=sorted(VALID_RESPONSE_FORMATS), default="text")
    parser.add_argument("--json-schema", help="JSON schema string passed to Claude CLI.")
    parser.add_argument("--save-transcript", help="Directory for consultation transcripts or app handoffs.")
    parser.add_argument("--dry-run", action="store_true", help="Show command metadata without calling Claude.")
    parser.add_argument("--doctor", action="store_true", help="Check Claude CLI discovery and configuration.")
    parser.add_argument("--doctor-live", action="store_true", help="Run doctor plus a live Claude smoke test.")
    parser.add_argument("--list-models", action="store_true", help="Print model presets and exit.")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Wrapper output format.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_models:
        print(json.dumps(list_model_presets(), indent=2))
        return 0

    if args.doctor or args.doctor_live:
        result = run_doctor(live=args.doctor_live, cwd=args.cwd, auth_provider=args.auth_provider)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    try:
        request = ConsultRequest(
            prompt=read_prompt_from_args(args),
            mode=args.mode,
            model=args.model,
            fallback_model=args.fallback_model,
            effort=args.effort,
            context=args.context,
            context_files=args.context_file,
            add_dirs=args.add_dir,
            cwd=args.cwd,
            auth_provider=args.auth_provider,
            provider_region=args.provider_region,
            provider_project=args.provider_project,
            provider_base_url=args.provider_base_url,
            provider_resource=args.provider_resource,
            provider_workspace_id=args.provider_workspace_id,
            allow_tools=args.allow_tools,
            timeout_seconds=args.timeout_seconds,
            max_budget_usd=args.max_budget_usd,
            max_context_chars=args.max_context_chars,
            redact=not args.no_redact,
            transport=args.transport,
            response_format=args.response_format,
            json_schema=args.json_schema,
            save_transcript=args.save_transcript,
            dry_run=args.dry_run,
        )
        result = run_consultation(request)
    except Exception as exc:
        if args.output == "json":
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"consultclaude_cli error: {exc}", file=sys.stderr)
        return 2

    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        if result.get("ok") and result.get("stdout"):
            print(str(result["stdout"]).rstrip())
        elif result.get("ok"):
            print(json.dumps(result, indent=2))
        else:
            print(result.get("stderr") or result.get("error") or json.dumps(result), file=sys.stderr)

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
