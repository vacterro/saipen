# T-288 live acceptance — one real ZAICODE archive from a freshly loaded runtime

Not unit objects: a new process (`python accept.py`, `runtime_mode=cli`,
`stale_packing_subsystem() is None`, loaded digest `c70a580315e9fa30…`) ran the
real `PackingService.ensure_fresh_archive("zaicode")` against the registered
project (`v:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE`, output
`…\__TO_AUDIT`, profile `standard`).

## The pack

| | |
|---|---|
| result | `success=True`, `reused=False`, `packed=True`, `status=PACKED` |
| wall clock | 27.6 s (`freshness_probe_ms` 89.7, `archive_pack_ms` 27493.0) |
| archive | `_ZAICODE_06.10.26-T20-17-55.zip` → **44,943,573 bytes**, 12,286 members |
| integrity | `zipfile.testzip() is None` (opens cleanly) |
| previous archive | `_ZAICODE_06.10.26-T18-50-47.zip` removed by the configured `delete_old=True` (single archive per project) |

## Identity — producer present in BOTH manifests

```json
{
 "audapack_version": "0.3.1",
 "source_revision": {"kind": "git", "head": "d66d9f63ef2fee4a5a5701136bf26169c7511d8c", "dirty": true},
 "packing_implementation_sha256": "c70a580315e9fa30b210b42e71d641ef005dfd069fc924fc41ec47dc627d59f7",
 "process_start_utc": "2026-10-06T17:17:55Z",
 "pack_started_utc": "2026-10-06T17:17:55Z",
 "runtime_entrypoint": "accept.py",
 "runtime_mode": "cli",
 "packing_policy_fingerprint": "f3bf6bf8bd184294fa5b148fe7ffadf9",
 "inventory_schema_version": 1
}
```

`packing_implementation_sha256` equals `runtime_identity.LOADED_PACKING_DIGEST`.
No absolute path, user name or drive letter appears in the block.

## Source review — the application source is really inside

```json
{"source_review_ready": true, "included_files": 12284, "included_bytes": 159377505,
 "archive_members": 12284, "issues": [],
 "components": [{"path": "zcode", "origin": "github.com/vacterro/zaicode",
                 "included": true, "reason": "nested_git_component",
                 "source_files": 8290, "source_bytes": 78618102, "archive_members": 8290}]}
```

`nested_git_components[0] = {path: zcode, origin: github.com/vacterro/zaicode,
root_branch: zaicode, head: 1cbb0921…, included: true,
reason: nested_git_component, files: 8290, bytes: 78618102}` — same product by
origin identity, never by folder name. 8,290 real `zcode/…` members are in the
ZIP (sample: `zcode/.agents/skills/agent-browser/SKILL.md`,
`zcode/packages/ui/src/i18n/locales/…`). `included=false` with `reason=""` does
not occur.

## Reconciliation and worktree truth

* `12,286 members == 12,284 included + 2 control manifests`.
* All 12,284 inventory members are real ZIP members with byte-exact sizes —
  0 missing, 0 size mismatched.
* Counts: `tracked 25242, untracked 8711, included 12284, excluded 21669,
  tracked_deleted 0`; `git_dirty=True`.
* All 10 root-level dirty worktree entries are members and inventory rows
  (`ZAICODE.ps1`, `.zcodeignore`, `_p.txt`, `_r009_ascii.txt`,
  `_receipt_view.txt`, `_t188probe.txt`, `asciirender-t220.py`, `r006a.txt`,
  `r006b.txt`, `reconcile_req001.py`).

## Storage composition (compressed / uncompressed / members)

| category | compressed | raw | members |
|---|---|---|---|
| `zcode` (canonical source) | 22,245,338 | 78,618,102 | 8,290 |
| `.saipen` (declared state + declared evidence) | 18,376,575 | 78,048,758 | 3,787 |
| `docs` | 913,122 | 1,844,066 | 124 |
| `.audapack` (this manifest) | 638,527 | 2,715,540 | 1 |
| everything else | < 400 KB total | | |

`largest_omitted` is discretionary history, not source:
`.saipen/kitchen/T-218-release-assets/ZAICODE-3.14.0-win-x64.exe` 198,553,478 B,
two 24,090,684 B `saitranslate` sha256 records, `.saipen/recovery/settled/.receipt-index.json`
6,273,193 B. `budget_met=false` against the 31,457,280 soft target, with
`budget_feasible=true` and `budget_floor_bytes == mandatory_bytes == 152,600,961`:
the target is unreachable without deleting mandatory source, which policy
forbids, so the flag is surfaced instead of chased.

## The reuse hole, on real archives

`archive_policy_mismatch(new_archive, source, current_fingerprint)` returns
**None** — the archive is reusable by identity.

Before this change the gate never read the producer block, so every archive in
`__TO_AUDIT` written by the superseded implementation was reusable whenever the
policy fingerprint matched and the timestamps were fresh. Measured read-only over
the real files:

| archive | producer | recorded impl | fingerprint match | source match | pre-T-288 verdict | now |
|---|---|---|---|---|---|---|
| `_AUDAPACK_06.10.26-T18-50-47.zip` | yes | `de22a4df27be` | yes | yes | **reusable** | refused: packing implementation changed |
| `FastPrompter_06.10.26-T18-50-47.zip` | yes | `de22a4df27be` | yes | yes | **reusable** | refused: packing implementation changed |
| `Wintage_06.10.26-T18-50-47.zip` | yes | `de22a4df27be` | yes | yes | **reusable** | refused: packing implementation changed |
| 21 older archives (e.g. `_PROBLIP_21.09.26-T05-42-58.zip`) | no | — | n/a | — | — | refused: archive predates producer identity |

A successful pack refuses to ship an archive whose source review is not ready, so
an archive whose own `source_review_ready` is not `true` cannot have been written
by the implementation that keeps that promise, and is never reused.
