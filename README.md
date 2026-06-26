# ConsultClaude

Codex plugin that lets Codex consult your local Claude Code CLI for advisory second opinions on design, UX, copy, architecture, logic, and reviews while Codex keeps ownership of edits and verification.

## Quick Install

PowerShell:

```powershell
irm https://raw.githubusercontent.com/Retro2512/ConsultClaude/main/install.ps1 | iex
```

macOS/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/Retro2512/ConsultClaude/main/install.sh | bash
```

Start a new Codex thread after installing so the plugin skills and MCP tools are loaded.

## Manual Install

```bash
codex plugin marketplace add Retro2512/ConsultClaude --ref main
codex plugin add consultclaude@consultclaude
```

## Requirements

- Codex CLI with plugin support (`codex plugin --help` should work).
- Python 3.10 or newer.
- Claude Code CLI installed and signed in (`claude --version` should work).

The plugin runs Claude locally through your Claude Code CLI. It does not bundle Claude, manage Anthropic credentials, or send context anywhere except the Claude CLI you already use.

## What It Adds

- A Codex skill named `consultclaude`.
- A local stdio MCP server exposing `consult_claude` and `consultclaude_presets`.
- A dependency-free Python bridge around `claude --print`.
- Safety defaults that keep Claude advisory-only unless Codex explicitly grants read-only context.

## Example Use

Ask Codex things like:

```text
Ask Claude to critique this settings screen before you implement it.
```

```text
Use Claude as a second reviewer for this architecture plan.
```

Codex should curate the context, ask Claude for bounded advice, compare the answer against local evidence, then make the final implementation and testing decisions.

## Update

```bash
codex plugin marketplace upgrade consultclaude
codex plugin add consultclaude@consultclaude
```

Open a new Codex thread after updating.

## Uninstall

```bash
codex plugin remove consultclaude
codex plugin marketplace remove consultclaude
```

## Local Smoke Tests

From the repo root:

```bash
python .github/scripts/validate_public_release.py
python plugins/consultclaude/scripts/consultclaude_cli.py --list-models --output json
```

Bridge dry run without requiring Claude on PATH:

```bash
CONSULTCLAUDE_CLAUDE_PATH=python python plugins/consultclaude/scripts/consultclaude_cli.py --prompt "Smoke test" --dry-run --output json
```

On PowerShell:

```powershell
$env:CONSULTCLAUDE_CLAUDE_PATH = "python"
python plugins/consultclaude/scripts/consultclaude_cli.py --prompt "Smoke test" --dry-run --output json
Remove-Item Env:\CONSULTCLAUDE_CLAUDE_PATH
```

## Security Notes

- The one-command installers run `codex plugin marketplace add` and `codex plugin add`; inspect `install.ps1` or `install.sh` first if you prefer.
- Do not pass secrets, `.env` files, private keys, or unrelated repository dumps to Claude consultations.
- The bridge includes basic redaction for common token and password patterns, but redaction is not a substitute for careful context selection.
- Claude receives only the prompt/context Codex provides to the local Claude Code CLI.

## Repository Layout

```text
.agents/plugins/marketplace.json
plugins/consultclaude/.codex-plugin/plugin.json
plugins/consultclaude/.mcp.json
plugins/consultclaude/scripts/
plugins/consultclaude/skills/
```

## License

MIT
