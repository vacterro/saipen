---
name: Protocol gap or bug
about: Something in RFC.md, a phase doc, a schema, or the validators is wrong, ambiguous, or inconsistent
title: ""
labels: bug
assignees: ""
---

**Where**
Which file and section: `saipen/RFC.md § X.Y`, `saipen/phases/X.md`, a
schema under `extensions/schemas/`, `tests/validate.sh`/`.ps1`, or a
`tests/scenarios/` fixture.

**Evidence**
The concrete evidence, not a feeling. A quote from the file, a `grep`
command and its actual output, or a minimal reproduction of the
inconsistency (e.g. "RFC's transition table says X, but `phases/X.md`
does Y").

**Expected**
What you'd expect instead, and why -- which of the three Litmus Test
questions (SPEC.md) it improves.

**Checked first**
- [ ] I checked `CHANGELOG.md` and `.saipen/KNOWLEDGE/decisions.md` for
      whether this was already discussed and deliberately decided
      otherwise.
