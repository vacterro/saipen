# T-1821 / SRC-279 source recovery

The receipt on disk holds one line:

    SAIHANDOFF T-301 live input acceptance and readable reporting

That is not the operator's message. It is a title a model supplied to the
intake (`request_provenance.witness: model_supplied`, meta.json), and the
projection preserved only it. The operator's actual handoff was delivered to
this session (`sess_987a3358-f5f7-4b4c-95b8-9825ad9966db`) and is still in the
host's `session_input` store.

## Where the bytes are

Host database: `C:\Users\vac34\.zcode\cli\db\db.sqlite`
Table: `session_input`
Row id: `queue_01a1526e-bcf3-7d65-ae34-929f67ce178e`
Session: `sess_987a3358-f5f7-4b4c-95b8-9825ad9966db` (this one)
Kind / delivery / status: `sendText` / `startNow` / `promoted`
`time_created`: 1792384351483 (2026-10-19, same window as SRC-279's
`received_at` 2026-10-19T04:32:37Z)

The recovered text is stored beside this file as `operator-message.txt`
(8 539 bytes, sha256
`ebc5c44d765cd50fa1d4a4869aa93ad65a33e758082b2524e83e30b28f11fdd9`).

## Why the receipt is short

The intake path recorded the message the *session* supplied, and the session
supplied a heading. Nothing compared it with the operator's bytes, which is
exactly what `witness: model_supplied` states. The handoff itself was never
truncated on the operator's side: the host row carries the full 8 539 bytes
with 356 newlines, ending in `/goal cc all`.

## What the full body says

The message addresses `EXECUTOR: SAITULS agent` and splits into eight sections:

* 1-4 (current evidence, interactive desktop root cause, real input acceptance,
  staged vs installed binary) are SAITULS work, and the same instruction says
  `Do not patch foreign repositories from SAITULS`. They belong to `__SAITULS`
  T-301 (sources SRC-110, SRC-111, SRC-112), not to this repository.
* 5 (root cause - unreadable report presentation) explicitly names a
  **SAIPEN-owned corrective** when SAIPEN's response construction or renderer
  is the owner.
* 6 (required report format) says to honor the existing SAIPEN
  operational-response schema and its canonical renderer/checker, and prefers
  `deterministic readable rendering from existing structured result data`.
* 7 A/B/C/D and L are the regression set for this repository: raw multiline
  stays multiline, structured fields are not concatenated, canonical response
  checks still pass, invalid input acceptance cannot become PASS, technical
  details stay in evidence without flooding the operator response.

So this ticket is not blocked on a missing description. It is scoped to the
SAIPEN-owned half, with the SAITULS half left where it belongs.
