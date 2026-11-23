# Security Extension -- EXAMPLE, copy into your project

This file lives in the SAIPEN home as a template, same role as
`extensions/templates/`. Nothing reads this copy automatically -- copy this
folder into *your project's own* `.saipen/extensions/security/` if you want the
hook (RFC § 1.9). Adjust the commands below to your actual toolchain.

This extension attaches to the `VERIFY` phase.

When an agent enters the `VERIFY` phase on a project that has its own
`.saipen/extensions/security/` (or legacy root `extensions/security/`), it MUST read that directory to discover any
security-related constraints or scanners it needs to run before allowing a
transition to `REVIEW`.

## Example Usage
- Run `npm audit` or `pip-audit`.
- Check for secrets in diff using `trufflehog`.
- Ensure no hardcoded credentials exist in source files.
