# Changelog

## 0.2.0 - 2026-06-26

- Adds `consultclaude_doctor` and `--doctor` / `--doctor-live` diagnostics.
- Adds explicit auth provider routing for default Claude Code auth, Bedrock, Vertex, Foundry, and Claude Platform on AWS.
- Redacts prompts, context, command errors, and saved transcripts with broader secret patterns.
- Removes unsafe `allow_tools=default`; supported values are `none` and `read-only`.
- Expands validation coverage for redaction, transcripts, provider env mapping, MCP dry-run, and doctor output.
- Adds Linux, macOS, and Windows CI.
- Installers now run a post-install doctor check and support optional live verification.

## 0.1.0 - 2026-06-26

- Initial public release.
- Adds the `consultclaude` Codex skill.
- Adds a local Claude Code bridge and stdio MCP server.
- Adds Git-backed marketplace metadata and one-command installers.
