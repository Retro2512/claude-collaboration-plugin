[CmdletBinding()]
param(
    [string]$Source = "Retro2512/ConsultClaude",
    [string]$Ref = "main",
    [string]$Marketplace = "consultclaude",
    [string]$Plugin = "consultclaude",
    [switch]$SkipClaudeCheck
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$InstallHint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name was not found on PATH. $InstallHint"
    }
}

function Invoke-CodexCommand {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & codex @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "codex $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

Require-Command -Name "codex" -InstallHint "Install or update Codex CLI, then rerun this installer."
Require-Command -Name "python" -InstallHint "Install Python 3.10 or newer, then rerun this installer."

if (-not $SkipClaudeCheck -and -not (Get-Command "claude" -ErrorAction SilentlyContinue)) {
    Write-Warning "Claude Code CLI was not found on PATH. The plugin will install, but consultations need 'claude' available or CONSULTCLAUDE_CLAUDE_PATH set."
}

Write-Host "Adding Codex marketplace $Source at ref $Ref..."
try {
    Invoke-CodexCommand -Arguments @("plugin", "marketplace", "add", $Source, "--ref", $Ref, "--json")
}
catch {
    Write-Warning "Marketplace add did not complete. Trying to refresh existing marketplace '$Marketplace'."
}

Write-Host "Refreshing marketplace $Marketplace..."
Invoke-CodexCommand -Arguments @("plugin", "marketplace", "upgrade", $Marketplace, "--json")

Write-Host "Installing $Plugin from marketplace $Marketplace..."
Invoke-CodexCommand -Arguments @("plugin", "add", "$Plugin@$Marketplace", "--json")

Write-Host ""
Write-Host "Installed $Plugin. Start a new Codex thread so the skill and MCP tools are loaded."
