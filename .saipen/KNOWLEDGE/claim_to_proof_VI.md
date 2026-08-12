# Claim-to-proof VI -- FOUNDATION SEAL + REAL CRITIC DOGFOOD (T-625)

The sixth proof level. The learned hierarchy was UNIT / COMPOSITION /
CANONICAL / GATE / PROVENANCE. Dogfood VI seals the foundational wave
(T-992 provenance chain, T-991 role freshness, T-639 audit isolation,
T-638 pre-apply integrity) with a real cold role=critic lifecycle and the
EVIDENCE_ADVERSARY lens.

> A green proof is useful only if falsifying its witness makes it red.

## The repaired claims, five dimensions each

Every foundational fix from the external provenance audit (v7.223.7-v7.223.10)
is claimed, then adversarially falsified. The witness of each claim was
mutated while the claimed end-state was left superficially valid; a gate that
stayed green would be a finding. All gates went red on falsification.

| Repair | UNIT | COMPOSITION | CANONICAL | GATE | PROVENANCE |
|---|---|---|---|---|---|
| T-992 installed_protocol_fingerprint (manifest-owned, framed, required-refusal) | missing required doc refuses; byte-boundary transfer changes hash | cross-directory identical; IMPROVE/SAICRITIC mutation changes hash | validate.py conformant | writer derives fingerprint; caller digest refused on mismatch | fingerprint binds installed protocol bytes, never a caller constant |
| T-992 validate_strict_provenance / validate_bound_report | blank scalar/control-injection/unknown-header/agent-mismatch all refuse | resume/append/complete/verify/status/validator share ONE bound bar | validate.py ACTIVE strict scan green | resume refuses forged metadata (INVALID_REPORT, never resumed:true) | agent compared to ROSTER seat (owning dir), never to itself |
| T-992 saipen_version install-only | foreign project VERSION 1.2.3 can never become saipen_version | writer + resume + validator all use install truth | README/badges match | version derived, never caller-supplied | report identity = install version, not target-project |
| T-991 role freshness fails closed | missing home/charter/exception => UNAVAILABLE, never fresh | sub_collect refuses STALE + UNAVAILABLE ready evidence | validator scans | collect returns structured PACKAGE_INCOMPLETE | role_revision verified against charter, not trusted |
| T-639 warn-ownership isolation | probe asserts WARN slug SET delta (control==red==green sets) | red differs from control ONLY by target ownership FAIL | warn-owner validator green without self-ownership | probe proves isolation, not just returncode | no test passes because its own ticket prose owns the slug |
| T-638 invalid base never mutated | invalid-manifest abort/complete/archive refuse with ZERO writes | create_cycle invalid created_at leaves no directory | validator conformant | load_valid_manifest single validated snapshot | no first-read/second-read ambiguity |
| T-638 invalid proposed never written | create_cycle/apppend/abort/complete/archive validate their own proposed output | malformed SWEEP/report cannot be extended | validator conformant | journal never sees known-invalid PREPARED/APPLY | proposed state proven before bytes written |
| T-638 cycle_aborted single meaning | ACTIVE/COMPLETE+aborted invalid; duplicate/unknown invalid | ARCHIVED+canonical draft-preserved valid | validator treats only valid aborted state specially | abort is journaled + byte-preserving | aborted manifest cannot pose as normal archived |

## The real cold critic lifecycle (role=critic, public path only)

Cycle `imp-vacterro-saipen-20260812-2`, seat `claude-01`, role critic.
Run exclusively through the CLI mechanical path with zero raw evidence edits:

`saipen improve --role critic --new-seat` (strict cycle + draft report + real
git-delta-v1 fingerprint) -> `saipen improve submit` (RUN-1, NO_FINDINGS
marker) -> `saipen improve complete` (bound completion bar) ->
`saipen improve verify` PASS -> `saipen improve cycle-complete` ->
`saipen improve clean` (archived with provenance).

An earlier cycle (`imp-vacterro-saipen-20260812-1`) was aborted when its first
RUN was submitted as prose without the NO_FINDINGS marker -- the abort path
worked mechanically and byte-preserved the draft, proving T-621/T-638 live.

## EVIDENCE_ADVERSARY verdict

The critic adversarially falsified each green claim's witness (stale
fingerprint, forged agent, malformed SWEEP, duplicate composite, warn-slug
set-delta, fabricated protocol fingerprint, cycle_aborted misuse). Every
mutation made its gate go red as required. **No foundational P0/P1 reproduced.**

## Sequential stability seal

One ordinary post-fix sequential release was completed end-to-end
(SCOUT -> BUILD -> VERIFY -> REVIEW -> SHIP -> DONE) with a recovery-clean
journal chain. Recorded for T-442 (the v8 gate): see the sequential release
commit below.
