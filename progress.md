# ConsultClaude Rename Progress

## Findings

- Current project is being renamed fully to `ConsultClaude`.
- Public/user-facing brand should be `ConsultClaude`.
- Codex plugin, marketplace, and install selectors should use the lowercase machine ID `consultclaude`.
- Public repository target is `https://github.com/Retro2512/ConsultClaude`.
- The plugin source path should be `plugins/consultclaude`.
- The MCP server should expose `consult_claude` and `consultclaude_presets`.
- Generated Python cache files are not part of the release and should stay out of the tree.
- The public branch history, tag, release metadata, configured marketplace, and local workspace path all need to align with the new name.
- Public repo, release metadata, tag, Codex marketplace install, and one-command installer have been verified for `ConsultClaude`.
- A live Windows handle kept one empty untracked legacy directory from being removed during this session; it is outside git and contains no files.

## Roadmap

- [x] Confirm clean saved git state before rename.
- [x] Replace project branding with `ConsultClaude`.
- [x] Rename plugin, skill, script, marketplace, MCP, and installer identifiers.
- [x] Rewrite public documentation and validation metadata for the new repository.
- [x] Remove remaining stale git ref and cache traces where possible.
- [x] Run validation and smoke tests.
- [x] Publish `Retro2512/ConsultClaude`.
- [x] Update release metadata and verify GitHub install.
- [ ] Rename local workspace folder to `ConsultClaude`.
