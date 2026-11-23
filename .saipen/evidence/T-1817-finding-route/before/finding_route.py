"""The pre-fix engine had no finding-level resolver at all.

This is the exact absence SRC-276 F-01 measured: `CONFORMANCE_UNHEALTHY` with
`ENGINEERING_REQUIRED, action: null` gave a continuation no mechanical way to
name the Work already owning the subject, so `saipen start` was the only
visible move. The module did not exist; importing it raised ImportError.
"""
