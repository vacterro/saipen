# T-1515 current verification

Commit 423dfed4 carries the launcher implementation. E-9317 already records the
intentional Win32 argv_prefix contract; the criterion was canonically corrected
at E-12206 to distinguish command_form, argv_prefix and exec_prefix. The
continuation strengthens only the native shell regression and its verifier
controls. Its original file is preserved in before/.

The old test selected C:/Windows/System32/bash.exe (WSL) and ignored startup
failure. With the actual installed Git Bash the unchanged original production
subject created injected.txt --json. The final test proves a native MSYS/Cygwin
shell, requires successful engine JSON and checks the exact query bytes; failed
execution and changed query are explicit negative controls. No launcher or
metacharacter acceptance was weakened.

The FINAL paired oracle is
6f40117e693ec19c08914e75b47d1af3d41209fb953ee8e149ca80404e83ca1f.
Original production f392c922ba8344bcbfa52c6d6778e25f2f84bf57f438212b14c88fc1654a3b36
FAILs the six-case oracle: three failures and two errors, including the actual
side-file injection; the verifier's failed-execution control passes.
Current production 9b500b2be67cdc63fbdf02d123ad276cdf71959e64e25b848d11032d7233a1a2
passes all six cases with zero skips. The comparison copies are disposable and
the live entry_resolver.py was never replaced.

VERIFY-neighbors.stderr independently records 53 native tests PASS, zero skips,
51.684 seconds. The earlier BUILD run overlapped source edits and its injector
identity check failed; that record remains BUILD-neighbors.stderr. The final
frozen BUILD retry and this VERIFY run both pass. No source change occurs during
the accepted runs.

Fresh canonical declared family:
897f117d9995d092-20261003T213728Z.json, fingerprint
897f117d9995d092f3932b00bfa43a581686d8b2b53cacc857cbfd644dffd0a8.
4897 ran: 4839 PASS, zero FAIL/ERROR, 58 SKIPPED, no expected failures or
unexpected successes. Actual raw six-shard transcripts and counts are retained
in shards/ and family-counts.json. All six T-1515 controls also PASS in the full
family. Compared with the prior family, the extra skip is the existing
test_today_is_not_an_empty_window: no commits today in this clone. It is not a
T-1515 transport skip and is not counted as PASS.

Ruff 0.16.0 over tools/ and tests/ and whitespace check PASS. Canonical core
validate minted CURRENT_PASS receipt-5e8f5141564d, zero blocking findings and
31 warnings. The baseline and family discovery/configuration are unchanged.

Confidence: high for the scoped security transport and native regression.
Publication remains excluded; pending C-004 will bind the reviewed two paths.
