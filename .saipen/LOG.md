# Log

- 05.08.26 11:14 [E-2046] [parent: E-2045] RUN: seal LOG.md -> LOG-008.md (66963 bytes, 199 lines, cap ~64 KB/300 lines crossed). Prefix check first so a re-attempt cannot mint a second segment, segment written and read back before the active log was replaced, both via temp file plus rename. Sealing is the fix for `log-soft-cap`, not a ticket to carry it -- which is why that slug reached 90 consecutive releases unowned and FAILed the ownership check.
