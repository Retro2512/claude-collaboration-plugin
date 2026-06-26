---
name: consultclaude
description: Consult local Claude Code from Codex as an advisory second model for design critique, creative ideation, layout rethinking, UX alternatives, product copy, architecture tradeoffs, logic stress tests, and independent reviews. Use when the user asks Codex to involve Claude, Claude CLI, or the Claude app; when a project benefits from divergent creative thinking or a second reasoning pass; or before major UI, product, architecture, or algorithm decisions where Claude should critique options before Codex implements.
---

# ConsultClaude

## Overview

Use this skill to ask Claude for advisory input while Codex stays responsible for implementation, verification, and the final response. The default posture is safe and bounded: pass curated context, ask for critique or alternatives, then synthesize Claude's answer instead of obeying it blindly.

For model selection details and prompt patterns, read `references/workflow-and-models.md`.

## Consultation Loop

1. Decide whether Claude adds value: creative range, UX/layout critique, copy judgment, architectural tradeoffs, logical stress testing, or independent review.
2. Gather only the context Claude needs. Summarize first, then include small relevant files or snippets. Do not pass secrets or whole-repo dumps.
3. Pick a mode: `design`, `layout`, `creative`, `copy`, `logic`, `architecture`, `review`, `stress-test`, `quick`, or `general`.
4. Pick the model only when needed. Use mode defaults for routine work; use `opus` for deep judgment; use `sonnet` for fast or cost-sensitive review; pass any user-requested Claude model alias or full ID.
5. Ask Claude for a bounded response: recommendation, reasoning, alternatives, risks, and next checks.
6. Compare Claude's answer against the codebase and user request. Codex makes final decisions, edits files, runs tests, and explains the outcome.
7. Save durable Claude findings only in the project's existing planning notes when they affect implementation decisions.

## Preferred Tool Path

Use the plugin MCP tool when available. The host may expose it with a namespaced name, but the server tool is `consult_claude`.

Typical MCP arguments:

```json
{
  "prompt": "Critique this settings layout before I implement it.",
  "mode": "design",
  "model": "auto",
  "auth_provider": "default",
  "context_files": ["src/screens/Settings.tsx"],
  "cwd": "/absolute/project/path",
  "allow_tools": "none"
}
```

Keep `allow_tools` as `none` unless Claude must inspect files directly. If inspection is necessary, use `read-only`; Codex still performs all edits.

Use `auth_provider` only when the user or environment explicitly needs a non-default Claude Code route:
`default`, `bedrock`, `vertex`, `foundry`, or `anthropic-aws`. The aliases `claude` and `anthropic` are accepted and resolve to `default`. Secret credentials should remain in environment variables or Claude Code settings, not in prompts or MCP arguments.

Use `consultclaude_doctor` before depending on Claude in a new environment. Set `live=true` only when a small real Claude request is acceptable.

## Script Fallback

If the MCP tool is not available, run the bridge script from the plugin root:

```bash
python scripts/consultclaude_cli.py \
  --mode design \
  --model auto \
  --auth-provider default \
  --prompt "Critique this dashboard layout before implementation." \
  --context-file src/Dashboard.tsx \
  --cwd /absolute/project/path
```

Use `--dry-run --output json` to inspect command construction without calling Claude.
Use `--doctor --output json` to check local install/configuration, or `--doctor-live --output json` to verify auth, quota, and provider routing with a tiny live smoke prompt.

## Claude App Fallback

Automatic response collection uses Claude CLI. If the user explicitly wants the Claude app or the CLI is unavailable, create a manual handoff prompt:

```bash
python scripts/consultclaude_cli.py \
  --transport app-handoff \
  --mode creative \
  --prompt "Generate three visual directions for this onboarding flow." \
  --cwd /absolute/project/path
```

This writes a prompt under `.codex/claude-handoffs/` for manual use. Do not wait for an app response unless the user asks for that handoff.

## Guardrails

- Do not consult Claude for simple deterministic tasks, routine terminal output, or facts that require current web verification.
- Do not pass credentials, environment files, private keys, or large unrelated code dumps.
- Do not let Claude's response override local evidence, tests, user constraints, or platform rules.
- Do not grant edit or shell tools through this bridge for ordinary consultations.
- Do not use `allow_tools=default`; supported values are `none` and `read-only`.
- Do not cite Claude as an external authority in the final answer; present the synthesized engineering decision.

## Resources

- `../../scripts/consultclaude_cli.py`: CLI wrapper for Claude consultations.
- `../../scripts/consultclaude_mcp.py`: dependency-free stdio MCP server exposing `consult_claude`, `consultclaude_presets`, and `consultclaude_doctor`.
- `agents/openai.yaml`: Codex agent prompt wiring for ConsultClaude.
- `references/workflow-and-models.md`: mode presets, model heuristics, context hygiene, and prompt examples.
