#!/usr/bin/env bash
set -euo pipefail

SOURCE="${SOURCE:-Retro2512/ConsultClaude}"
REF="${REF:-main}"
MARKETPLACE="${MARKETPLACE:-consultclaude}"
PLUGIN="${PLUGIN:-consultclaude}"
SKIP_CLAUDE_CHECK="${SKIP_CLAUDE_CHECK:-0}"

require_command() {
  local name="$1"
  local hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Error: $name was not found on PATH. $hint" >&2
    exit 1
  fi
}

require_command codex "Install or update Codex CLI, then rerun this installer."
require_command python3 "Install Python 3.10 or newer, then rerun this installer."

if [[ "$SKIP_CLAUDE_CHECK" != "1" ]] && ! command -v claude >/dev/null 2>&1; then
  echo "Warning: Claude Code CLI was not found on PATH. The plugin will install, but consultations need 'claude' available or CONSULTCLAUDE_CLAUDE_PATH set." >&2
fi

echo "Adding Codex marketplace $SOURCE at ref $REF..."
if ! codex plugin marketplace add "$SOURCE" --ref "$REF" --json; then
  echo "Marketplace add did not complete. Trying to refresh existing marketplace '$MARKETPLACE'." >&2
fi

echo "Refreshing marketplace $MARKETPLACE..."
codex plugin marketplace upgrade "$MARKETPLACE" --json

echo "Installing $PLUGIN from marketplace $MARKETPLACE..."
codex plugin add "$PLUGIN@$MARKETPLACE" --json

echo
echo "Installed $PLUGIN. Start a new Codex thread so the skill and MCP tools are loaded."
