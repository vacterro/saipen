# AUDIT CORE — _AUDAPACK (run id `98985be3-570a-450f-b740-ad646699c8dd`)

## What this is

The audit itself is **already done** — 18 findings, each verified by direct source read and exhaustive `grep` call-site enumeration. No code was modified; this was a read-only pass.

## The single action requiring approval

Write the finished report to the mandated path:

`C:\Users\vac34\.zaicode\v2\zaicode-audits\fb373f36-338a-4b32-9d6a-c1ce4b7e1d79\_AUDAPACK__01_AUDIT_CORE.md`

That is one `Write` call to a file outside the project. It touches no source, no config, no project metadata.

## Findings (18, each with EVIDENCE / DEFECT / REPAIR / VERIFY)

Highest blast radius first:

- **CORE-1 / 7 / 8 / 9** — `config.py`: a `null` section, a non-numeric int, a string `window_size`, or an out-of-range `port` each brick config load for GUI *and* Bridge. The Settings UI enforces the port range the file format does not.
- **CORE-2** — `bridge/server.py:3078`: `run_id` is interpolated into a regex *replacement template*. A backslash raises `re.error` out of an unhandled path; `\g<0>` silently corrupts a committed wave body.
- **CORE-3** — `inaudit_capture.py:710,735`: crash recovery calls `.unlink()` on a path read verbatim from an on-disk journal, with no containment check.
- **CORE-4** — `browser_dispatch.py:2068`: `campaign_run_id` is the only wire identifier without the charset regex its two siblings have, and it is concatenated into a filesystem path.
- **CORE-5** — `audit_run_service.py:206`: `OpenProcess` returns NULL for both "dead" and "access denied"; both map to `False`, so a live elevated writer's claim gets stolen — contradicting the function's own docstring four lines above.
- **CORE-6 / 11 / 18** — three atomic-write sites with no `fsync`; `packing.py` has **zero** fsync calls while its sibling `inaudit_commit.py` has 16.
- **CORE-10** — the artifact-ownership guard fails *open* when the project registry is empty, a state a user reaches by never registering a project.
- **CORE-13** — the PERF-001 digest cache is fully implemented and completely dead: its only hit in the whole tree is its own definition.
- **CORE-12** — an ingest repair `re.sub` missing `re.MULTILINE`, so it is a no-op in exactly the case it exists to fix.

## Honest verification limits

Plan mode blocked process execution, so **no finding was reproduced by me running Python.** Every finding is static-verified by read plus `grep` call-site counts — the strongest evidence available without execution. The report labels individually which micro-behaviours a subagent did execute. I also corrected one subagent claim rather than carrying it: the *earlier* sub at `ingest.py:332` is **not** a bug, because `split_multi_wave_text` puts `PROJECT_NAME:` at offset 0.

## After approval

One `Write`, then a summary of the top findings. No other tool call is needed.