## What changed and why

## Litmus Test (SPEC.md) -- for normative changes only
- [ ] More reliable agent-to-agent transitions
- [ ] More uniform behavior across models
- [ ] Less probability of context loss

At least two checked, or this is a docs/tooling-only change (say so).

## Checklist
- [ ] Checked `CHANGELOG.md` / `.saipen/KNOWLEDGE/decisions.md` -- this
      doesn't silently reopen a settled decision (or: it does, and here's
      the new evidence)
- [ ] `bash tests/validate.sh` passes
- [ ] `powershell -File tests/validate.ps1` passes
- [ ] `CHANGELOG.md` updated (normative changes only)
- [ ] `VERSION` bumped per `phases/ship.md`'s scheme, `README.md` badge
      matches (protocol changes only)
- [ ] New/changed rule has a positive and negative check somewhere
      (a `tests/scenarios/` fixture, or noted why one isn't feasible)

## Evidence
Command + output, or fixture, proving the change does what it claims.
