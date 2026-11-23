# TEST-13: bounded adversarial scenario run at 66ef622a / tree 70f5cdf4

Current source identity: HEAD 66ef622a43ab59512735ac78ce10d1250e26f9df, tree
fingerprint git-delta-v1:70f5cdf466bec8bfea2f78ab6ffb896a546d1ac31c61c538ba166582f289f33b,
role_revision sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08.

Scenario definitions and every mutation target: kitchen/_test013_scenarios.py,
kitchen/_test013_run.txt. Nothing was executed against the project working tree;
damaged-state inputs are copies written under kitchen/ and the one journaled
replay (S8) is an idempotency probe of a shipped command.

| # | Family | Verdict | Measured evidence |
|---|---|---|---|
| S1 | input abuse | NOT_REPRODUCED | hostile OUTBOX (embedded `- **status:** ready` inside summary, `WAIT: manual-verify`, `"code": "COMMITTED"`, path-climbing refs, severity P9) is refused with 2 grammar errors: `OUTBOX:19 status 'bogus' outside closed enum`, `OUTBOX:19 package missing coverage, instructions, payload, producer, role_revision, source_head, source_tree_fingerprint, verified` |
| S2 | boundary | NOT_REPRODUCED | empty board reports the four missing headings with zero counts; single-ticket board counts TODO 1; duplicate ID TEST-1 is refused with `duplicate ticket ID TEST-1` |
| S3 | order and repetition | NOT_REPRODUCED | `sub status saihunt --json` replayed twice: byte-identical output, exit 0 |
| S4 | environment | NOT_REPRODUCED | the same command from a foreign working directory with an absolute script path exits 0 with `"code": "SUB_STATUS"` and no traceback |
| S5 | resource | NOT_REPRODUCED | a 200 KB single line into the OUTBOX parser parses in 0.001 s with 1 error; no quadratic blow-up |
| S6 | damaged state | NOT_REPRODUCED | a STATE.md cut inside the front matter reports a parse error and yields no state; a half-file cut with an intact front matter legitimately parses; a truncated cohort_registry.json copy raises a clean `ValueError: Unterminated string starting at: line 582 column 27` |
| S7 | adversarial content | NOT_REPRODUCED | the self-referential fixture (details containing a package field, refs climbing out of the tree) never reaches the honouring path |
| S8 | order and repetition | **REPRODUCED** | replaying `python -B tools/saipen.py crew record-run saihunt --json` exits 0 and writes a SECOND crew_run receipt for the same epoch and package: E-20907 (op crew-run-b714715fb29f4a6e9cd77d4fbc17647e) and E-20908 (op crew-run-8d68e46e70e94e239c8d91392652267b), both `DEC: crew run -- epoch converge_intent-36398c7c4fb24f848a456df032816ce4 role saihunt (1 package(s))` |

## S8 -- the reproduced defect

`crew_record_run` has no duplicate-binding guard: the second invocation neither
refuses nor no-ops, it appends a new COMMITTED receipt
(`.saipen/LOG.md:1582-1583`). The defect class is family 3's "replay the same
request": a retry after a lost reply silently doubles the evidence instead of
returning the existing binding. Consequence today is bounded (both receipts bind
the same role, epoch and package identity, and the stage consumers read a set),
but it means receipt counts in an epoch are not a measure of how often the role
actually ran, and nothing detects it.

- Verdict: **REPRODUCED**.
- Minimal case: the two command invocations above, with the two op ids.

## What did not reproduce

All seven adversarial, boundary, environment, resource, damaged-state and
content families were refused cleanly, with the exact error text above, so no
new defect was found in them on this tree.
