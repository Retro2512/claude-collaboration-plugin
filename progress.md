# ConsultClaude Production Readiness Progress

## Current Findings

- Baseline before this production-readiness pass is saved and pushed at `d7d1195` on `main`.
- Public repo is `https://github.com/Retro2512/ConsultClaude`.
- Current install flow works for users with Codex CLI, Python, and a usable Claude Code CLI.
- The repo is not yet production-ready for broad users because Claude detection is mostly `PATH`-based and subscription/provider readiness is not diagnosed.
- Claude Code owns actual authentication and entitlement. ConsultClaude should verify that Claude Code can answer a smoke prompt and explain likely auth/provider problems, not claim to inspect subscription tiers directly.
- Claude Code supports multiple auth/provider modes; ConsultClaude should default to normal Claude Code auth but allow explicit provider/env configuration for Bedrock, Vertex, Foundry, and Claude Platform on AWS.
- Audit point merit:
  - Redaction skipping prompt is real and high priority.
  - Redaction patterns are too shallow for a public safety posture.
  - Runtime/security tests are too narrow.
  - CI should cover Windows because the `.ps1` resolution branch matters.
  - `allow_tools="default"` is a footgun and should be removed or made explicit. Prefer removing it.
  - Transcript persistence currently risks storing raw request data.
  - Local workspace rename is cosmetic and still blocked by live Windows handles.
- Local-only `.claude/` and generated Python cache files exist or can exist during development; they must stay ignored and unshipped.

## Roadmap

- [x] Confirm clean saved baseline before production-readiness edits.
- [x] Research current Codex plugin guidance and Claude Code auth/provider shape.
- [x] Add robust Claude CLI discovery and doctor diagnostics.
- [x] Add provider configuration options while keeping normal Claude Code auth as default.
- [x] Fix prompt and transcript redaction.
- [x] Expand redaction coverage for common secret formats.
- [x] Remove or safely replace `allow_tools="default"`.
- [x] Improve installer postflight and documentation.
- [x] Expand validation tests across runtime, security, MCP dry-run, and Windows behavior.
- [x] Add CI matrix for Linux, macOS, and Windows.
- [x] Run full local validation.
- [x] Commit, push, and verify public install again.
