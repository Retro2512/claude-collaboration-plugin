# Contributing

Thanks for helping improve ConsultClaude.

## Development Setup

1. Install Python 3.10 or newer.
2. Install Codex CLI with plugin support.
3. Install and sign in to Claude Code CLI if you want to run live consultations.
4. Run validation from the repo root:

```bash
python .github/scripts/validate_public_release.py
```

## Pull Requests

- Keep the plugin dependency-free unless the added dependency is clearly worth the install cost.
- Keep Claude advisory by default; Codex should remain responsible for edits and verification.
- Do not add behavior that passes secrets, whole repositories, or environment files to Claude automatically.
- Update `README.md` and `CHANGELOG.md` when changing install behavior, plugin metadata, tools, or user-visible workflows.
- Include a short validation note in the PR description.

## Release Checklist

1. Run `python .github/scripts/validate_public_release.py`.
2. Run a bridge dry run.
3. Confirm the marketplace install commands in `README.md`.
4. Tag the release after the GitHub push if publishing a versioned release.
