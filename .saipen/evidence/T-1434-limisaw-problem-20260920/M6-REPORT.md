# T-1434 / SRC-088 — Milestone 6 evidence: foreign observation authority

Date: 2026-09-21. Phase BUILD. Continuation of T-1434 (SRC-088).

Mission: distinguish "I am deliberately observing/operating on explicit
project X" from "my inherited ambient session claims Y and I pointed mutation
at X" without weakening wrong-root protection; generalise the provenance
model beyond `fix == local patch`; prove a safe foreign read-only observation
and a refused wrong-root mutation live.

## Defect reproduced before patch

`resolve_project_root` refused an explicit `--project-root B` whenever the
ambient `SAIPEN_PROJECT_LINEAGE` named another project A -- for EVERY command,
including pure diagnostics. Measured repeatedly during M1-M3: the LIMISAW
acceptance runs had to clear all four `SAIPEN_*` carriers by hand, which is a
useful technique but not an operator contract. The serializer also fed the
same refusal through the validator (both the CLI front door and validate.py
itself resolve the root), so even `saipen validate --project-root B` from an
A-bound session was blind.

## Implemented primitives

1. `paths.resolve_project_root(..., authority="mutation"|"observe")` -- a
   CLOSED authority value for the explicit branch:

   | caller use | explicit foreign root under ambient A | effect |
   |---|---|---|
   | `observe` (DIAGNOSTIC effects) | binds deliberately | observation, no mutation authority inherited |
   | `mutation` (everything else) | REFUSES `PROJECT_LINEAGE_MISMATCH` | wrong-root mutation stays impossible |

   The non-explicit resolutions (carrier/cwd/git/ancestor) are byte-for-byte
   unchanged under both authorities; the value is derived mechanically from
   `command_effects.classify_invocation` in the CLI, and `validate.py` always
   resolves under `observe` (its only write is the conformance receipt for
   the tree it was pointed at).

2. Cross-repository provenance audit (M6.2): the five required semantic
   classes each resolve to a durable, machine-checked representation
   (OPS.md section 12): `own_patch`; `external_implementation` + the three
   `RESOLUTION_REASONS`; `superseded_verified` + `superseded_by`. External
   authority is a stable identity (`lineage-<32hex>`), never a URL; the
   implementation is `T-###@commit` and receipts bind the installed engine
   generation -- the `_AUTHORITY_RE` grammar refuses URLs, ticket ids and
   free text.

Files (sha256[:16] at capture):
- tools/saipen_engine/paths.py 1bd5f083ca1a16e5
- tools/saipen.py 4bad25a80b7a25ab, tools/validate.py ab07a2e3ea81e4d6
- tools/test_foreign_observation_authority.py 3a9e871d1f8e1f49 (new, 13 tests)
- saipen/OPS.md 87d51e0d8bfdfb0e (section 12)

## Verification (current bytes)

- `python tools/test_foreign_observation_authority.py` -> 13/13 OK:
  observation binds a foreign explicit root; mutation refuses it; mutation
  succeeds with coherent carriers and with none; unknown authority refused;
  CLI `status` and `validate` observe LIMISAW-style foreign targets with
  ambient A carriers present; wrong-root `ticket add` refuses
  PROJECT_LINEAGE_MISMATCH with ZERO mutation in the foreign board; coherent
  carriers mutate the target and leave project A byte-untouched; the five
  provenance classes resolve to their mechanisms; external authority refuses
  URL/T-id/malformed lineage shapes.
- Binding/guard neighbours: test_session_binding 17/17,
  test_guard_admission 15/15, test_guard_hostile_matrix 43/43,
  test_field_fixture_isolation 46/46, test_t1412_conformance_truth 10/10;
  test_check_inventory 37/42 and test_public_closure_cli 9/10 (same recorded
  pre-existing reds, unchanged).

## M6.3 safe foreign read-only observation -- regression

Two throwaway projects with distinct lineages, carriers naming A:
- `status --project-root B` -> ok, binds B; no PROJECT_LINEAGE_MISMATCH.
- `validate --project-root B` -> NO lineage refusal (validator resolved under
  observe).
- consequential mutation (`ticket add`) against B -> refused, and B's BOARD
  is byte-unchanged by the attempt.
- coherent carriers for B (root + lineage) -> the mutation commits in B and
  leaves A untouched.

## M6.4 current T-1361 carrier cluster

Shared root cause confirmed for the OBSERVATIONAL half: the explicit-root
binding refused read-only foreign probes under inherited carriers. The
fixture half was already repaired by T-1361's own E-7692
(`session_carrier_isolation()` in run_scenarios). Manifestations of that
class that should disappear when T-1361 resumes its remeasure: read-only
foreign-root probes (`validate`/`status`-style fixture calls) that failed
PROJECT_LINEAGE_MISMATCH solely because carriers were inherited. Mutation
path occurrences and any failures with a different root cause stay owned by
T-1361; no full-suite run was attempted here (T-1361 owns that baseline).

## M6.5 live LIMISAW binding (no manual carrier clearing)

With this session's ambient A carriers PRESENT:
- `saipen --project-root <LIMISAW> status --json` -> ok, binds LIMISAW;
- `saipen --project-root <LIMISAW> validate --json` -> runs and returns
  CONFORMANCE_UNHEALTHY for LIMISAW's own current state (no lineage refusal,
  CURRENT_FAIL receipt for LIMISAW);
- wrong-root mutation `ticket reasoning T-53 ...` -> refused
  PROJECT_LINEAGE_MISMATCH (expected `lineage-a41c0e3a81534f02a4cc4520a399cca6`,
  ambient `lineage-b512942bac884a8691f6c98afcd6ddb9`);
- with coherent LIMISAW carriers (root + lineage set in the child env) the
  same repair surface resolves: `ticket reasoning T-53` -> ALREADY_LINKED,
  zero writes -- reachable without clearing anything.

## Milestone exit check

- read-only foreign observation does not require unsafe environment surgery: yes;
- wrong-project consequential mutation remains protected: yes (unit + live);
- `fix == local patch` assumptions generalised into the five-class model: yes;
- no arbitrary URLs authoritative: yes (grammar + gate);
- no new pre-existing debt introduced: yes (check-inventory count unchanged).

## Exact next action

M7 (SRC-088): real LIMISAW end-to-end recovery with canonical operations --
per-ticket `work reverify` with EXECUTED evidence (honest FAILs stay FAIL);
re-resolve EX-000001..3 on the final engine generation; confirm the strict
cycle terminal + sweep linkage; confirm SRC-007 retired and SRC-011 ACTIVE
with R005..R015 preserved; then run the required final acceptance
(structural gate, receipt PASS, `saipen validate --gate core` PASS,
conformance PASS, router not blocked, 0 current errors).
