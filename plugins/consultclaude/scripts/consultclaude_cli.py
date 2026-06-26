#!/usr/bin/env python3
"""Advisory bridge from Codex to local Claude Code."""

from __future__ import annotations

import argparse
import json
import os
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
VALID_ALLOW_TOOLS = {"none", "read-only", "default"}
VALID_TRANSPORTS = {"cli", "app-handoff"}
VALID_RESPONSE_FORMATS = {"text", "json"}

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
            "CONSULTCLAUDE_MODEL": "Default model when request.model is omitted.",
            "CONSULTCLAUDE_FALLBACK_MODEL": "Comma-separated fallback chain.",
            "CONSULTCLAUDE_EFFORT": "Default effort when request.effort is omitted.",
            "CONSULTCLAUDE_CLAUDE_PATH": "Explicit path to claude executable or claude.ps1.",
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


def resolve_claude_command() -> list[str]:
    override = os.environ.get("CONSULTCLAUDE_CLAUDE_PATH")
    candidate = override or shutil.which("claude")
    if not candidate:
        raise FileNotFoundError(
            "Claude CLI was not found on PATH. Install/sign in to Claude Code, "
            "set CONSULTCLAUDE_CLAUDE_PATH, or use --transport app-handoff."
        )

    suffix = Path(candidate).suffix.lower()
    if suffix == ".ps1":
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not powershell:
            raise FileNotFoundError("Cannot run claude.ps1 because PowerShell was not found.")
        return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", candidate]
    return [candidate]


SECRET_PATTERNS = [
    re.compile(
        r"(?i)\b(api[_-]?key|token|secret|password|authorization)\b\s*[:=]\s*([^\s,;]+)"
    ),
    re.compile(r"(?i)\b(bearer\s+)[a-z0-9._\-+/=]{12,}"),
    re.compile(r"\b(sk-[A-Za-z0-9_\-]{16,})\b"),
]


def redact_text(text: str) -> str:
    redacted = text
    redacted = SECRET_PATTERNS[0].sub(lambda match: f"{match.group(1)}=[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[1].sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[2].sub("[REDACTED_API_KEY]", redacted)
    return redacted


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
        request.prompt.strip(),
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


def command_for_display(command: list[str]) -> list[str]:
    return ["[empty-arg]" if arg == "" else arg for arg in command]


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
        "request": asdict(request),
        "prompt": prompt_text,
        "result": result,
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

    if request.dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "cwd": str(cwd),
            "command": command_for_display(command),
            "model": options["model"],
            "effort": options["effort"],
            "fallback_model": options["fallback_model"],
            "prompt_chars": len(prompt_text),
        }

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            input=prompt_text,
            cwd=str(cwd),
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
    }
    save_transcript(request, prompt_text, result, cwd)
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
    parser.add_argument("--list-models", action="store_true", help="Print model presets and exit.")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Wrapper output format.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_models:
        print(json.dumps(list_model_presets(), indent=2))
        return 0

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
