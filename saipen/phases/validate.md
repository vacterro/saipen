# Phase: VALIDATE

## Purpose and entry

Check and, where authorized, repair only SAIPEN structural conformance.
Terminal execution is required. Without it, LOG
`RUN: validate -> FAIL, no terminal` and enter BLOCKED.

## Action

Run the canonical stdlib validator:

- bound project: `python <saipen-home>/tools/validate.py`;
- explicit target: add `--project-root <path>`.

It owns STATE/schema, BOARD dependency, LOG graph, phase/capability, and root
binding checks. With no Python, run the portable subset from the already bound
root: `tests\validate.ps1` on Windows or `tests/validate.sh` on Unix. State
that degraded evidence is a subset.

PASS: LOG the command and result. FAIL under `mode: read-only`: report the
exact error and change nothing. Otherwise repair only structural corruption,
rerun, and preserve historical meaning. VALIDATE may fix malformed shape,
missing required fields/headings, and structural references; it **must not
rewrite LOG history or product content to make a gate green**.

## Exit

Passed/repaired: SCOUT for workable tickets, PLAN for unrefined work, DONE for
an empty TODO, or BLOCKED when no ticket is workable. The canonical checkpoint
and DONE->maintenance route remain in CORE/MAINTENANCE.
