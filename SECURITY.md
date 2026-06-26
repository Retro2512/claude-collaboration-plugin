# Security Policy

## Supported Versions

Security fixes target the latest release on `main`.

## Reporting a Vulnerability

Open a private vulnerability report through GitHub Security Advisories when available, or contact the maintainer through the repository owner profile.

Please include:

- A clear description of the issue.
- Steps to reproduce.
- Impact and affected versions.
- Any suggested mitigation.

## Security Model

This plugin asks the local Claude Code CLI for advisory responses. Codex controls what context is sent. The bridge has basic redaction, but users and contributors should treat context selection as the real security boundary.

Do not design features that automatically include credentials, `.env` files, private keys, browser cookies, unrelated source trees, or large unreviewed data dumps in Claude consultations.
