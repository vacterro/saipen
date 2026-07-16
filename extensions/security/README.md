# Security Extension

This extension attaches to the `VERIFY` phase.

When an agent enters the `VERIFY` phase, it MUST read this directory to discover any security-related constraints or scanners it needs to run before allowing a transition to `REVIEW`.

## Example Usage
- Run `npm audit` or `pip-audit`.
- Check for secrets in diff using `trufflehog`.
- Ensure no hardcoded credentials exist in source files.
