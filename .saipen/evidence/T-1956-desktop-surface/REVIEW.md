# T-1956 REVIEW -- independent re-measurement, and what this change does not claim

## Re-run, not re-quoted

REVIEW did not accept VERIFY's transcript. Both oracles were executed again on
the same tree, after the checkpoint:

```
$ python -B -m unittest tools.test_host_bootstrap.ActivationDeliveryTests.test_32_installed_desktop_loader_reads_the_injected_block -v
test_32_installed_desktop_loader_reads_the_injected_block ... ok
Ran 1 test in 0.197s
OK

$ python -B -m unittest tools.test_instruction_loader_contracts -v
Ran 9 tests in 0.152s
OK
```

**PASS.** The second oracle matters because this ticket touches the test that
*measures* the loader contract; the contract test is the independent reader of
the same fact and it stayed green without being modified.

## Scope audit: the diff is what REVIEW was told it is

```
 tools/core_unit_baseline.json  |  15 +---
 tools/saipen_engine/journal.py |   1 -
 tools/test_host_bootstrap.py   | 178 +++++++++++++++++++++++++++++------------
 3 files changed, 132 insertions(+), 62 deletions(-)
```

Three files, and each has a stated reason:

- `test_host_bootstrap.py` -- the ticket's own deliverable.
- `journal.py` -- the one-line incompleteness repair T-1955's VERIFY caught
  (`OP_CLASSES` still registered `producer-integration-` after its writer was
  deleted; the registry's own converse test is what found it).
- `core_unit_baseline.json` -- rewritten from a fresh full sweep because the
  red it was grown for is now green, and two legacy-lifecycle reds cleared
  independently.

`extensions/adapters/registry.json` is **untouched** (`git diff --stat` on it
returns empty). That is deliberate: see "Carried forward" below.

## The self-audit: where this ticket would be wrong if I were sloppy

**A test that passes because the extractor silently returns nothing.** This is
the failure mode the old `test_32` actually had -- it asserted delivery from a
surface, and after the host update that assertion could have been satisfied by
an extractor that found no function and answered `""`. That is why leg 2 exists
(`assertEqual(probe(home_only), "")`) and leg 3 exists (a loader name the
bundle never defined must exit non-zero and print `EXTRACT_FAILED`). Without
leg 3, leg 2 is not evidence of anything: `""` from a correct "the home surface
is gone" and `""` from a broken probe are the same bytes.

**A green test that proves the host, not the repository.** The suite is
`skipUnless` the installed orchestrator and `node` exist. On a machine without
the desktop app this test does not run at all -- so it cannot be counted as
coverage of the injector. The injector's own coverage is
`test_33_pre_fix_injector_is_a_red_control` and `test_instruction_loader_contracts`,
both of which were already green and stay green.

**Reading the update as a regression.** It is not. The 2026-10-29 desktop build
moved instruction delivery from a home scanner to a project-root reader. Our
test was pinned to the removed function. The correct response to a host that
moved is to move the oracle with it -- not to assert the old contract and red
forever. That is the distinction VERIFY drew and REVIEW re-checked: the bundle
mtime (08:27:12) sits between the last green run of the old test and its first
red, on the same HEAD `b152e6de`, and reverting both of my edits reproduced the
identical failure. Host drift, not our regression.

## What this ticket deliberately does NOT decide

The registry still declares, for `FreeBuff Desktop`:

```json
{ "name": "FreeBuff Desktop", "surfaces": ["~/.AGENTS.md", "~/.CLAUDE.md"] }
```

Measured against the shipped bundle, both of those strings occur **zero**
times, and the loader that remains reads the *project* root. So
`autoinject.instruction_contract_status` answers `current` on this machine on a
premise the running code no longer implements -- and this repository has no root
`AGENTS.md` (`PROJECT_BLOCK_ABSENT`) while `~/.AGENTS.md` exists. The desktop
activation path therefore has nothing to read here.

That is a **registration-strategy decision**, not a test repair: it changes
which file the installer writes, carries its own contract test
(`test_instruction_loader_contracts` asserts the exact surface lists), and
changes behaviour for every project on this host. Folding it into a test-fix
ticket would have shipped a behavioural change with no ticket, no decision
record and no rollback story. Filed as **T-1957** (`--needs T-1956`), with the
byte evidence carried into its verify clause.

## Verdict

Criterion 1 measured green twice (VERIFY and REVIEW, independently).
Criterion 2 has three controls, including HEAD-restored, so the patch is
attributable. Criterion 3 is answered with a named artifact, its byte count,
its mtime, and the code path that selects it. Scope is three files with one
reason each. **REVIEW approves SHIP.**
