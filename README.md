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

The installer registers the marketplace, installs the plugin, refreshes the marketplace snapshot, and runs a non-live doctor check. It does not spend Claude usage by default.

## Manual Install

```bash
codex plugin marketplace add Retro2512/ConsultClaude --ref main
codex plugin add consultclaude@consultclaude
```

## Requirements

- Codex CLI with plugin support (`codex plugin --help` should work).
- Python 3.10 or newer available as `python`.
- Claude Code CLI installed and signed in (`claude --version` should work).

The plugin runs Claude locally through your Claude Code CLI. It does not bundle Claude, manage Anthropic credentials, or send context anywhere except the Claude CLI you already use.

Claude Code supports subscription login, Console/API credentials, and enterprise cloud providers. ConsultClaude does not inspect private subscription tiers directly; it verifies whether the local Claude Code CLI can be found and, with `--doctor-live`, whether it can answer a small smoke prompt.

## What It Adds

- A Codex skill named `consultclaude`.
- A local stdio MCP server exposing `consult_claude` and `consultclaude_presets`.
- A dependency-free Python bridge around `claude --print`.
- Safety defaults that keep Claude advisory-only unless Codex explicitly grants read-only context.
- Doctor diagnostics for install/auth/provider readiness.
- Provider routing for Claude Code default auth, Amazon Bedrock, Google Vertex AI, Microsoft Foundry, and Claude Platform on AWS.

## Doctor Checks

After install:

```bash
python path/to/installed/plugin/scripts/consultclaude_cli.py --doctor --output json
```

Live auth, quota, and provider smoke test:

```bash
python path/to/installed/plugin/scripts/consultclaude_cli.py --doctor-live --output json
```

The live check asks Claude for a tiny fixed response with a `$0.10` budget cap. It is the only reliable way ConsultClaude can verify that the selected Claude Code auth path can actually answer.

## Auth And Provider Configuration

Default behavior uses Claude Code's normal authentication resolution. That covers Claude Pro, Max, Team, Enterprise, Console/API, configured OAuth tokens, and whatever provider environment Claude Code already uses.

Use `CONSULTCLAUDE_AUTH_PROVIDER` or the `auth_provider` MCP/CLI field when you want ConsultClaude to force a provider route for the spawned Claude Code process:

```bash
export CONSULTCLAUDE_AUTH_PROVIDER=bedrock
export AWS_PROFILE=my-profile
export AWS_REGION=us-east-1
```

```bash
export CONSULTCLAUDE_AUTH_PROVIDER=vertex
export ANTHROPIC_VERTEX_PROJECT_ID=my-project
export CLOUD_ML_REGION=global
```

```bash
export CONSULTCLAUDE_AUTH_PROVIDER=foundry
export ANTHROPIC_FOUNDRY_RESOURCE=my-resource
```

```bash
export CONSULTCLAUDE_AUTH_PROVIDER=anthropic-aws
export ANTHROPIC_AWS_WORKSPACE_ID=wrkspc_...
export AWS_REGION=us-east-1
```

Supported `auth_provider` values are `default`, `bedrock`, `vertex`, `foundry`, and `anthropic-aws`. Secret values should stay in environment variables or Claude Code settings, not in prompts.

If your active Claude subscription should be used but `ANTHROPIC_API_KEY` is set, Claude Code may prefer the API key. Unset that variable or check Claude Code `/status` if auth fails unexpectedly.

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

`CONSULTCLAUDE_CLAUDE_PATH` may be either a command name on `PATH` or an explicit executable path.

## Security Notes

- The one-command installers run `codex plugin marketplace add` and `codex plugin add`; inspect `install.ps1` or `install.sh` first if you prefer.
- Do not pass secrets, `.env` files, private keys, or unrelated repository dumps to Claude consultations.
- The bridge redacts common token, key, bearer, private-key, JWT, Slack, GitHub, Google, AWS, and database-URL patterns in prompts, context, stderr/stdout errors, and saved transcripts. Redaction is still not a substitute for careful context selection.
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
