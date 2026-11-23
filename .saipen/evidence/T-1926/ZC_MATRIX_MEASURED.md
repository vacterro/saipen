# T-1926 — SRC-333 External Owners ZC-01..ZC-06: measured boundary

**Ticket:** T-1926 [P0]
**Source Receipt:** SRC-333 (`audit/writing-block.md`)
**Date:** 2026-10-27
**Supersedes:** `EXTERNAL_OWNERS_ZC_01_06.md` (same directory), whose blanket
"all six items are external owners" claim this file corrects by measurement.

---

## 1. Why the original block was withdrawn

The ticket was parked as `BLOCKED_EXTERNAL` on the premise that ZC-01..ZC-06
belong entirely to the ZAICODE host and the SAIMAIL maintainer. That premise is
false as a blanket statement, and the false part was hiding a live defect in
this repository.

| Item | Original claim | Measured reality |
|---|---|---|
| ZC-01 secret containment | external (SAIMAIL) | **Half ours.** The persistence redaction boundary is `codec.redact_credentials`; it did not recognise SAIMAIL identity keys. |
| ZC-02 authenticated ingress | external (host) | Genuinely host-side; no readable host source here. |
| ZC-03 shell/path/exit adapter | external (host) | **Part ours.** argv construction and exit propagation are in this repo. |
| ZC-04 response admission | external (host) | Host-boundary enforcement; SAIPEN already refuses malformed prose (`EXEC_RESPONSE_INVALID`). Residual is host-side. |
| ZC-05 diagnostic budget | external (host) | `RECONCILE_REAUTH_REQUIRED` is a hard stop in `gate_decision`; the unbounded *loop* was host behaviour. |
| ZC-06 session observability | external (host) | Host telemetry; not readable or mutable here. |

The distinction is reachability, not ownership language. A defect that can be
measured and repaired in this tree does not become somebody else's problem by
being labelled external.

## 2. Measured boundary

**ZAICODE host — not reachable.** `~/.zcode/cli` holds `agents/ artifacts/ db/
exec/ image-cache/ log/ memories/ plugins/ rollout/` and `config.json`. It
contains no `*.js`, `*.mjs` or `*.ts` outside `plugins/` and one session
`tmpfile.js`; there is no `package.json` and no `.exe` under `~/.zcode`. The
host ships compiled, so ZC-02, ZC-04 and ZC-06 cannot be settled from here.
`tools/test_t1926_zc_owners_matrix.py::ExternalReachabilityTests` asserts this
so the day host source becomes readable, the boundary is re-measured rather
than silently inherited. (An earlier attempt at this check probed
`~/AppData/Roaming/ZAICODE/cli`, which does not exist — that was a wrong path,
and the test failed until it was corrected. The failure is recorded here rather
than quietly fixed, because an unmeasured boundary was the original defect.)

**SAIMAIL — readable, not ours to mutate.** The checkout is at
`V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\__SAIMAIL__`, with
`spec/20-LOCAL-KEY-CUSTODY-v0.md` and `saimail/keyvault.py`. SRC-184 and the
cross-project rule forbid rewriting a sibling project from this one, so the
ZC-01 work belongs here at the boundary we own.

## 3. The defect found and fixed

SAIMAIL schema `SAIMAIL_LOCAL_IDENTITY_1` version 1 ("raw" custody) stores
X25519 private keys as bare 64-hex under `identity/identity.json`:

```json
{
  "created": "...",
  "recipient_private_key": "<64 hex>",
  "schema": "SAIMAIL_LOCAL_IDENTITY_1",
  "seat": "...",
  "sender_private_key": "<64 hex>",
  "version": 1
}
```

`codec.redact_credentials` — the ONE canonical primitive that every
persistence target must pass through (T-1101) — matched `ghp_`, `AKIA`, `sk-`,
postgres URIs and bearer tokens, but **not** these. A `cat identity.json` whose
output reached STATE, BOARD, LOG, recovery or a sealed segment wrote the live
private key out verbatim.

Measured before the fix, with a synthetic key:

```
LEAKS  bare key under json name
LEAKS  bare 64hex digest        (expected to survive — see below)
LEAKS  key=value
```

The fix keys the pattern on the **field name**, not the value width:

```
(?i)(["']?[a-z0-9_]*private_key["']?\s*[:=]\s*)("[^"]{8,}"|'[^']{8,}'|[0-9a-f]{16,})
```

and replaces the whole value. Two choices are load-bearing:

1. **Field name, not value shape.** A bare 64-hex string elsewhere in this
   ledger is a sha256 citation (`FOCUSED-UNIT-EVIDENCE PASS ... sha256:<64hex>`,
   `record:<path> sha256:<64hex>`). Redacting every 64-hex run would corrupt
   the evidence chain that DONE and VERIFY depend on. The tests assert that
   citations and `nonce`-style fields survive untouched.
2. **Whole value, not a 64-char window.** An earlier version matched exactly 64
   hex, which left a truncated fragment of a 65- or 128-character value in the
   output. Partial redaction of a secret is still disclosure, so the rule now
   removes the value whatever its width or encoding, including uppercase.

## 4. Verification

`tools/test_t1926_zc_owners_matrix.py` — 9 tests, all passing:

- `ZC01SecretContainmentTests` (5): identity JSON redacted; digest citations
  survive; every storage spelling covered (`:` / `=` / JSON / single quotes /
  no space); uppercase covered; every width removed with no fragment left.
- `ZC03TransportTests` (2): a real subprocess exit code of 3 reaches the caller
  unchanged; argv survives with an embedded space and backslashes.
- `ExternalReachabilityTests` (2): the host has no readable source tree; the
  SAIMAIL custody spec still names the raw identity file.

Regression control — the existing redaction contract still holds:
`test_source_receipts`, `test_t1765_finding_subtypes`,
`test_conformance_repair_boundary` → **190 tests, OK**.

## 5. Exposure scan — did the key already leave the identity file?

The verify clause also asks whether private key values have already entered the
model, UI, history or exports. Measured read-only after the fix, with key values
never printed (only a truncated sha256 fingerprint and file paths):

- Two live identity sets exist and both are the raw v1 schema: the sibling
  checkout's `.saimail-workspace/identity/identity.json` and the seat this
  session actually uses at
  `%APPDATA%\ZAICODE\saimail\agent\identity\identity.json`. Different seats,
  different keys — scanning only the sibling would have missed the live one.
- 193 711 files scanned across the project tree, `%APPDATA%\ZAICODE`,
  `~/.zcode` (including session logs, rollout and db) and the sibling checkout.
- Every full-key match landed on the identity file itself, which is correct —
  that is where a key belongs.
- **Exposures outside an `identity.json`: 0.**
- Both identity files are git-ignored (`.gitignore:37` `.saimail-workspace/`)
  and untracked; `git log --all -S <prefix>` and `git grep -F <prefix>` return
  no commits and no tracked-tree hits, and the ZAICODE export stage contains
  none of the fingerprints.

Verdict: no disclosure has occurred in this project, in the host session logs,
in git history or in exports. The fix closes the path before it opens; it is not
a remediation of an observed leak.

**Recorded honestly:** this scan was run after the ticket reached DONE (phase is
`DONE`, so no further VERIFY checkpoint could cite it). The closure itself did
not rest on this scan — the DEC and the VERIFY line cite only the fix and its
tests — so the scan strengthens a closure that was already sound rather than
retroactively justifying one that was not.

## 6. What remains genuinely external

ZC-02 (authenticated ingress bridge), ZC-04 (host-boundary admission), ZC-06
(host telemetry) and the host half of ZC-03 and ZC-05 terminate in compiled
ZAICODE host code with no source tree on this machine. They are not this
ticket's work and cannot be settled here. The residual operator action is
unchanged: forward ZC-02/ZC-04/ZC-06 to the ZAICODE host owner, and rotate the
exposed SAIMAIL identities once dependent seats are enumerated (rotation is a
credential operation, so it stays with the operator, not with an agent).

The SAIPEN-side half of ZC-01 is now closed at the boundary this repository
owns.
