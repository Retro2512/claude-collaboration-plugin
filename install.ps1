[CmdletBinding()]
param(
    [string]$Source = "Retro2512/ConsultClaude",
    [string]$Ref = "main",
    [string]$Marketplace = "consultclaude",
    [string]$Plugin = "consultclaude",
    [switch]$SkipClaudeCheck,
    [switch]$VerifyClaude
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

Write-Host "Removing any existing $Plugin install..."
try {
    Invoke-CodexCommand -Arguments @("plugin", "remove", "$Plugin@$Marketplace", "--json")
}
catch {
    Write-Host "No existing $Plugin install to remove."
}

Write-Host "Installing $Plugin from marketplace $Marketplace..."
Invoke-CodexCommand -Arguments @("plugin", "add", "$Plugin@$Marketplace")

$installedPath = $null
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$cacheRoot = Join-Path $codexHome "plugins\cache\$Marketplace\$Plugin"
if (Test-Path $cacheRoot) {
    $installedPath = Get-ChildItem -LiteralPath $cacheRoot -Directory |
        Sort-Object LastWriteTime -Descending |
        Where-Object { Test-Path (Join-Path $_.FullName "scripts\consultclaude_cli.py") } |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not $SkipClaudeCheck) {
    if (-not $installedPath) {
        Write-Warning "ConsultClaude installed, but the doctor check was skipped because the installed path could not be determined."
    }
    else {
        $doctorArgs = @("$installedPath\scripts\consultclaude_cli.py", "--doctor", "--output", "json")
        if ($VerifyClaude) {
            $doctorArgs = @("$installedPath\scripts\consultclaude_cli.py", "--doctor-live", "--output", "json")
        }
        Write-Host "Running ConsultClaude doctor..."
        & python @doctorArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "ConsultClaude installed, but the doctor check failed. Run 'claude' interactively or configure CONSULTCLAUDE_CLAUDE_PATH / CONSULTCLAUDE_AUTH_PROVIDER, then start a new Codex thread."
        }
    }
}

Write-Host ""
Write-Host "Installed $Plugin. Start a new Codex thread so the skill and MCP tools are loaded."
