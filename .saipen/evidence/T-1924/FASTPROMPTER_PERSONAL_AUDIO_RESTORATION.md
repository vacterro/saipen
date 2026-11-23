# FastPrompter personal audio restoration — current evidence and open work

Observed 2026-10-25. This corrects the unsupported completion of T-1921. The
immutable original mission is `.saipen/archive/source/SRC-330.md`, SHA-256
`eee73aad905e76b0adef553fcef4938029393f7614606acb35b06e504d8ea41e`.

## Required report fields

| Field | Current evidence |
| --- | --- |
| STATUS | INCOMPLETE. A remaining resolver defect is reproduced. |
| CURRENT_REVISION | Checkout HEAD `e1f0cadcc64d17b7420c293be3b0cf815f06771e`, with unrelated working changes. The running process's loaded module bytes were not independently measured. |
| LOCAL_DATA_ROOT | Source launcher and the inspected `get_data_dir()` contract select `V:/___VAC/__K/__CODE/_PY/_FastPrompter/data` when the existing portable directory is writable. That directory contains the active, changing primary database; the selected profile has not been read. |
| PERSONAL_SOUND_ROOTS | `data/addon/sounds` exists with 1,286 audio files. `data/sound_library` does not exist. `data/personal_audio.json` enables personal overrides with an empty override table. |
| ORIGINAL_FILES_VERIFIED | NOT VERIFIED. File presence and counts do not establish original hashes. The compliance private manifest exists and identifies historical source and backup trees. |
| ORIGINAL_BYTES_ACTIVE | NOT VERIFIED for the running application's selected events. A disposable probe of the actual resolver reproduces a reconnect failure. |
| EVENT_MAPPINGS_PRESERVED | NOT VERIFIED against a historical configuration. No live configuration was changed by this investigation. |
| AMBIENCE_PRESERVED | NOT VERIFIED against the operator's active rule, original `computalk1.wav` hash, enabled state, gain, loop and fade settings. |
| SETTINGS_MIGRATION_FIXED | Current source preserves safe unresolved refs, but the requested idempotence, per-profile and historical restoration evidence has not been collected. |
| SOURCE_CHANGES | No FastPrompter source change in this investigation. Existing personal-mode and migration changes predate it. |
| TEST_RESULTS | `reconnect_probe.py` uses the actual resolver with disposable roots: the bundled fallback remains selected after a matching personal file appears. Subject SHA-256 `222ab67f2a6275c101ca451e9b60cae3183d5b2a01602eb9a1a62ae343a15f63`. |
| PUBLIC_AUDIO_GATE | NOT RUN for this investigation; current manifest includes `ambient_loop.wav`. |
| ARCHIVE_SCAN_RESULT | NOT VERIFIED for the actual proposed Git/publication set, nested recovery ZIP and historical public tags. |
| RELEASE_STATUS | No public artifact built, accepted or published by this investigation. |
| NEED_USER | The target engine refused projection with `WAIT_OPERATOR`: one project operator decision is open. Exact original mission is durable there as `SRC-134`. |
| NEXT_EXACT_ACTION | Resolve the target project's canonical open operator decision, then execute the queued exact mission through its own ingress. T-1924 retains the correction obligation. |

## Independent outcome states

| Outcome | Verdict |
| --- | --- |
| LOCAL_AUDIO_RESTORED | NOT PROVEN; resolver reconnect defect remains. |
| PUBLIC_SOURCE_CLEAN | NOT PROVEN by this investigation. |
| PUBLIC_BUILD_CLEAN | NOT PROVEN; no current artifact inspection. |
| RELEASE_ACCEPTED | NOT PROVEN. |
| GITHUB_PUBLISHED | NOT PERFORMED. |

## Regression requirements R1–R20

| Original control | Current verdict |
| --- | --- |
| R1 personal original versus same-name fallback | Open: verify exact original hashes and personal-mode resolution. |
| R2 absent original uses public fallback | Probe observes fallback, but no audible playback acceptance. |
| R3 explicit user namespace | Open. |
| R4 explicit addon namespace | Open. |
| R5 explicit builtin namespace | Open. |
| R6 prior legacy IDs preserve intent | Open: historical selections not reconstructed. |
| R7 disconnection preserves stored preference | Open: no migration/control test executed. |
| R8 reconnect restores personal playback | FAIL: cached bundled path survives appearance of the personal file. |
| R9 migration idempotence | Open. |
| R10 custom ambience names/volumes | Open. |
| R11 original computalk1 locally audible | Open. |
| R12 clean ambient_loop public fallback | Open. |
| R13 preview/event identical content | Open. |
| R14 public source permitted audio only | Open. |
| R15 actual EXE permitted audio only | Open. |
| R16 restricted audio inside tracked ZIP rejected | Open. |
| R17 ignored private ZIP classified by actual publication scope | Open. |
| R18 rebuild preserves preferences | Open. |
| R19 disposable acceptance leaves active DB unchanged | The probe never opens the live DB; all future acceptance tests still owe this invariant. |
| R20 fixtures never enter shipped sound directory | The probe writes fixtures only under a disposable temporary directory. |

## Full mission remains in scope

The required eleven representative playback records remain open: UI click,
sidebar navigation, save/restore, error, success, timer, preview, imported sound,
ambience, Problip and a selected preset. Each still needs EVENT, STORED_REF,
RESOLVED_PATH, expected/actual original SHA-256, PLAYBACK_STATUS and
CONFIGURATION_PRESERVED. Fixture path resolution is not audible host acceptance.

The P0 terminal checklist remains unproven for original-byte inventory, historical
selection recovery, active ambience, preview/event agreement, unchanged local
functionality, rebuild/restart behavior and user-data preservation. The P1
checklist remains unproven for public source, packaging, nested publication
archives, exact EXE inspection, artifact-bound acceptance and publication gates.

All original constraints remain applicable: preserve later integration and
ambient_loop, back up before changing configuration, respect the live writer
lock, keep original audio outside public source, do not delete originals or
rewrite Git history, and retain a single bounded canonical resolver. The current
source already has a resolver cache; its cache hit checks only the previously
chosen path's size/mtime, so an unchanged public fallback hides a newly available
higher-priority personal candidate.

## Why T-1921's closure is insufficient

Its analysis confirms requirements in prose but supplies no direct audio,
configuration, artifact or historical-hash evidence. LOG E-18305/E-18306 reuse
the seven-test T-1912 ingress receipt from 13:44. That receipt verifies SAIPEN
origin reconciliation; it does not cover FastPrompter audio or SRC-330's R1–R20.
T-1924 records this contradiction without changing the immutable source or
claiming the original mission has been completed.
