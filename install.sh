#!/usr/bin/env bash
set -euo pipefail

SOURCE="${SOURCE:-Retro2512/ConsultClaude}"
REF="${REF:-main}"
MARKETPLACE="${MARKETPLACE:-consultclaude}"
PLUGIN="${PLUGIN:-consultclaude}"
SKIP_CLAUDE_CHECK="${SKIP_CLAUDE_CHECK:-0}"
VERIFY_CLAUDE="${VERIFY_CLAUDE:-0}"
PYTHON_COMMAND="${PYTHON_COMMAND:-python}"

require_command() {
  local name="$1"
  local hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Error: $name was not found on PATH. $hint" >&2
    exit 1
  fi
}

require_command codex "Install or update Codex CLI, then rerun this installer."
require_command "$PYTHON_COMMAND" "Install Python 3.10 or newer with a 'python' command, then rerun this installer."

if [[ "$SKIP_CLAUDE_CHECK" != "1" ]] && ! command -v claude >/dev/null 2>&1; then
  echo "Warning: Claude Code CLI was not found on PATH. The plugin will install, but consultations need 'claude' available or CONSULTCLAUDE_CLAUDE_PATH set." >&2
fi

echo "Adding Codex marketplace $SOURCE at ref $REF..."
if ! codex plugin marketplace add "$SOURCE" --ref "$REF" --json; then
  echo "Marketplace add did not complete. Trying to refresh existing marketplace '$MARKETPLACE'." >&2
fi

echo "Refreshing marketplace $MARKETPLACE..."
codex plugin marketplace upgrade "$MARKETPLACE" --json

echo "Removing any existing $PLUGIN install..."
if ! codex plugin remove "$PLUGIN@$MARKETPLACE" --json; then
  echo "No existing $PLUGIN install to remove."
fi

echo "Installing $PLUGIN from marketplace $MARKETPLACE..."
codex plugin add "$PLUGIN@$MARKETPLACE"

codex_home="${CODEX_HOME:-$HOME/.codex}"
cache_root="$codex_home/plugins/cache/$MARKETPLACE/$PLUGIN"
installed_path=""
if [[ -d "$cache_root" ]]; then
  while IFS= read -r candidate; do
    if [[ -f "$candidate/scripts/consultclaude_cli.py" ]]; then
      installed_path="$candidate"
      break
    fi
  done < <(find "$cache_root" -mindepth 1 -maxdepth 1 -type d | sort -Vr)
fi

if [[ "$SKIP_CLAUDE_CHECK" != "1" ]]; then
  if [[ -z "$installed_path" ]]; then
    echo "Warning: ConsultClaude installed, but the doctor check was skipped because the installed path could not be determined." >&2
  else
    echo "Running ConsultClaude doctor..."
    doctor_args=("$installed_path/scripts/consultclaude_cli.py" "--doctor" "--output" "json")
    if [[ "$VERIFY_CLAUDE" == "1" ]]; then
      doctor_args=("$installed_path/scripts/consultclaude_cli.py" "--doctor-live" "--output" "json")
    fi
    if ! "$PYTHON_COMMAND" "${doctor_args[@]}"; then
      echo "Warning: ConsultClaude installed, but the doctor check failed. Run 'claude' interactively or configure CONSULTCLAUDE_CLAUDE_PATH / CONSULTCLAUDE_AUTH_PROVIDER, then start a new Codex thread." >&2
    fi
  fi
fi

echo
echo "Installed $PLUGIN. Start a new Codex thread so the skill and MCP tools are loaded."
