# TEST-16: bounded adversarial scenarios at dc39709c (tree c9c3e86c)

Current identity: `dc39709c0c17a3272126c01a626ffcaa4176140b` /
`git-delta-v1:c9c3e86c3626f36973a4e75543aeebc51f174d8fa3c2271c89e1afe963a229a1`.
Role revision: `sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08`.
Raw captures: `_test16_audit_probe.json`, `_test16_validate_installed_full.txt`,
`_test16_validate_repo_full.txt`, `_test16_crew_a.json`, `_test16_crew_b.json`,
`_test16_pre.sha`/`_test16_post.sha`, `_test16_s4_probe.json`.

Every probe below was read-only or refused before writing. No project file
was created, edited or deleted by this role.

## Scenario 1 -- audit route executes as a dead end (damaged state): REPRODUCED

Minimal input: the current audit inbox projection, which routes
`saipen audit ingest` for `audit/SAIHANDOFF_BZ_REA_AGENT_DRIFT_RECOVERY.md`
(SRC-386, `state: CLOSED_PENDING_DELETE`, `work: T-2016`).

Command:

```
saipen audit ingest --dry-run --json
```

Observed output (`_test16_audit_probe.json`, exit 1):

```json
{"ok": false, "code": "SOURCE_UNRESOLVED", "detail": "linked Work T-2016 is not DONE",
 "receipt": "SRC-386", "action": "saipen audit status"}
```

What breaks: the canonical validator FAILs `STATE.md audit route not followed`
whenever `next_action` is not the routed `saipen audit ingest`, but the routed
command itself refuses while linked Work T-2016 is not DONE, and T-2016 is
`BLOCKED_EXTERNAL` (SRC-386:R004 lives in the REA project). The route and its
own executor disagree about the precondition. Verdict: **REPRODUCED**.

## Scenario 2 -- verifier home decides the manifest verdict (environment): REPRODUCED

Minimal input: the same validator bytes, invoked against two homes.

```
sha256sum C:/Users/vac34/AppData/Local/saipen/scheduled-source/tools/validate.py tools/validate.py
# both fb495f7ea8d51c9e8351041a1a00345ccf1f86960ecb7c89ed43ec64cf7ee20a
PYTHONPATH=C:/Users/vac34/AppData/Local/saipen/scheduled-source/tools \
  python C:/Users/vac34/AppData/Local/saipen/scheduled-source/tools/validate.py
python -B tools/validate.py
```

Observed: installed home `Validation FAILED: 3 problem(s), 17 warning(s)`
(`_test16_validate_installed_full.txt`); repo home
`Validation FAILED: 27 problem(s), 35 warning(s)`
(`_test16_validate_repo_full.txt`). The repo-only set is the 26
runtime-manifest paths Git does not track; the installed-only set is the audit
route and FG-0046. Cause: `home_path("MANIFEST.json")` resolves inside the
running home, so the installed gate inspects its own manifest and cannot see
the project manifest's untracked files.

What breaks: identical verifier bytes produce verdicts over different input
sets, so "the controlling gate passed" says nothing about the project
manifest. This is the identity class the night shift names, measured rather
than asserted. Verdict: **REPRODUCED**.

## Scenario 3 -- consecutive crew plans are idempotent and write nothing (order/repetition): REPRODUCED

Minimal input: run the same plan derivation twice with no intervening action.

```
saipen crew --dry-run --json   # _test16_crew_a.json
saipen crew --dry-run --json   # _test16_crew_b.json
sha256sum .saipen/STATE.md .saipen/LOG.md   # before/after
```

Observed: STATE.md and LOG.md hashes byte-identical before and after
(`_test16_pre.sha` vs `_test16_post.sha`, `diff` empty); both runs report
`first_unsatisfied: SC-3`; the only JSON difference is the scanned-file count
in the SC-5 reason, `61721` -> `61722`, because the first run's own capture
files were written between the two runs. No plan field, stage order or action
changed. Verdict: **REPRODUCED** (idempotent plan derivation).

## Scenario 4 -- binding an unknown package fails closed (input abuse): REPRODUCED

Minimal input: a package id that does not exist.

```
saipen crew record-run saitest --package TEST-99 --json
```

Observed (exit 1, `_test16_s4_probe.json`):

```
code: STALE_PACKAGE
TEST-99 is not a current saitest package: it must be ready or reviewed and
carry the live source triple and the current role revision
```

STATE.md and LOG.md hashes unchanged after the refusal. The gate refuses before
writing; it does not record a partial receipt. Verdict: **REPRODUCED**
(negative control for the writer this role must use).

## Limits

- No full test family was run; no load scenario exceeded the bounded probes
  above.
- Scenario 2 measures a design asymmetry of the manifest check; it does not
  decide which generation should own the check.
- Scenario 3's byte comparison covers STATE.md and LOG.md only, not every file
  under `.saipen/`.
- The role wrote only inside `.saipen/extensions/subs/saitest/`.
