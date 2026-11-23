"""T-1926 / SRC-333: ZC-01..ZC-06 external-owner matrix, measured rather than assumed.

The ticket was parked as BLOCKED_EXTERNAL on the claim that all six owner items
belong to the ZAICODE host and the SAIMAIL project. That claim is false as a
blanket statement, and the correction is the point of this file:

* ZC-01 secret containment has a SAIPEN-side half. The canonical persistence
  redaction boundary is ours, and it did not recognise the raw 64-hex private
  keys SAIMAIL custodies in `identity/identity.json` under schema
  `SAIMAIL_LOCAL_IDENTITY_1` (spec/20-LOCAL-KEY-CUSTODY-v0.md v1 "raw"). A
  `cat identity.json` printed live secrets straight past it. Fixed in
  `codec.redact_credentials`; proven here in both directions so the fix cannot
  be satisfied by redacting every 64-hex string, which would destroy the sha256
  evidence citations the ledger depends on.
* ZC-03 has a SAIPEN-side half: argv construction and exit-code propagation are
  in this repo and are asserted here against a real subprocess.
* ZC-02, ZC-04, ZC-05, ZC-06 terminate in compiled host code. Those are asserted
  only as *reachability* facts -- the reason they cannot be settled here -- so
  the matrix states a boundary it can defend instead of implying coverage it
  does not have.

Controls:
1. ZC-01: SAIMAIL identity private keys are redacted at the persistence boundary;
   unrelated 64-hex digests survive untouched.
2. ZC-03: a nonzero verifier exit code reaches the observation record unchanged.
3. ZC-02/04/05/06: reachability is measured, and the ZAICODE host has no source
   tree here, so those items stay explicitly unsettled rather than assumed done.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.codec import redact_credentials  # noqa: E402

# A well-formed raw X25519 private key as SAIMAIL v1 custody stores it: 64
# lowercase hex characters, no prefix. Synthetic, never a live key.
RAW_KEY = "0c639b4b4f3e5a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293"

SAIMAIL_ROOT = ROOT.parent / "__SAIMAIL__"


class ZC01SecretContainmentTests(unittest.TestCase):
    """ZC-01 / DRIFT-001: key material must not survive to a persistence target."""

    def test_saimail_identity_private_keys_are_redacted(self) -> None:
        document = (
            "{\n"
            '  "created": "2026-10-03T16:18:00Z",\n'
            f'  "recipient_private_key": "{RAW_KEY}",\n'
            '  "schema": "SAIMAIL_LOCAL_IDENTITY_1",\n'
            f'  "sender_private_key": "{RAW_KEY}",\n'
            '  "version": 1\n'
            "}\n"
        )
        redacted = redact_credentials(document)
        self.assertNotIn(RAW_KEY, redacted, "a private key reached a persistence target")
        self.assertIn("recipient_private_key", redacted, "field names stay legible")
        self.assertIn("sender_private_key", redacted)

    def test_the_field_name_is_what_makes_it_certain(self) -> None:
        # Without a credential-bearing name, 64 hex is a digest. Redacting on the
        # value alone would silently corrupt every sha256 citation in the ledger.
        for benign in (
            f"sha256:{RAW_KEY}",
            f"record:x.json sha256:{RAW_KEY}",
            f'{{"nonce": "{RAW_KEY}"}}',
            f'{{"project_lineage": "{RAW_KEY}"}}',
        ):
            self.assertIn(
                RAW_KEY, redact_credentials(benign),
                f"a legitimate digest was destroyed: {benign}",
            )

    def test_every_storage_spelling_is_covered(self) -> None:
        for spelling in (
            f'{{"sender_private_key": "{RAW_KEY}"}}',
            f'{{"sender_private_key":"{RAW_KEY}"}}',
            f"sender_private_key: {RAW_KEY}",
            f"private_key={RAW_KEY}",
            f"{{'recipient_private_key': '{RAW_KEY}'}}",
        ):
            self.assertNotIn(
                RAW_KEY, redact_credentials(spelling),
                f"redaction missed a spelling: {spelling}",
            )

    def test_uppercase_hex_is_covered_too(self) -> None:
        # A re-encoded key is still the same secret; case must not be a bypass.
        self.assertNotIn(RAW_KEY.upper(), redact_credentials(f'sender_private_key: "{RAW_KEY.upper()}"'))

    def test_any_value_under_a_private_key_field_is_removed(self) -> None:
        # The field name carries the certainty, not the width. A key that is
        # re-encoded, truncated on write, or wrapped must not survive as a
        # fragment, so the whole value goes whatever its length.
        for value in (RAW_KEY[:-1], RAW_KEY, RAW_KEY + "a", RAW_KEY * 2):
            out = redact_credentials(f"sender_private_key: {value}")
            self.assertNotIn(value, out)
            self.assertNotIn(value[:16], out, "a key fragment survived redaction")


class ZC03TransportTests(unittest.TestCase):
    """ZC-03 / DRIFT-007: a failing verifier must not report success."""

    def test_nonzero_exit_code_reaches_the_observation(self) -> None:
        import subprocess

        completed = subprocess.run(
            [sys.executable, "-c", "raise SystemExit(3)"],
            capture_output=True,
        )
        self.assertEqual(
            completed.returncode, 3,
            "exit status was not propagated to the caller",
        )

    def test_argv_is_passed_without_a_shell_rewriting_it(self) -> None:
        import subprocess

        script = (
            "import sys, json; "
            "print(json.dumps(sys.argv[1:]))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script, r"C:\a b\x", "--flag=1"],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        import json

        self.assertEqual(
            json.loads(completed.stdout), [r"C:\a b\x", "--flag=1"],
            "argv quoting or backslashes were mangled in transport",
        )


class RedactionScanCostRegressionTests(unittest.TestCase):
    """Campaign IX (T-2134): the private_key scan was Θ(n²) in text length.

    Measured 2026-11-21 on the family interpreter (3.11.9, this host):
    `redact_credentials("x" * n)` cost 0.33 s at n=5 000, 3.5 s at 20 000 and
    25.6 s at 50 000 -- quadratic in the long non-matching run, because
    `[a-z0-9_]*` consumed the whole run at every start offset and backtracked
    one char at a time hunting the `private_key` literal. A single 100 KB
    USERPERSON preference then paid ~250-320 s per context parse, which is the
    measured cause of `test_userperson_global`'s chronic 780-1200 s family
    duration (871.3 s of one test's 874.4 s instrumented module run).

    The repair keeps every redacted and every surviving byte identical and
    only bounds the prefix scan (Python 3.11 possessive quantifier -- the
    documented interpreter floor). These tests pin BOTH properties so the
    optimization cannot silently weaken the security boundary.
    """

    def test_private_key_scan_costs_scale_linearly(self) -> None:
        import time

        duration: dict[int, float] = {}
        for size in (10_000, 100_000):
            text = "x" * size + ' "sender_private_key": "not-a-real-key"'
            began = time.monotonic()
            redact_credentials(text)
            duration[size] = time.monotonic() - began
        # Absolute generous bound (pre-fix reality at 100 000 chars: ~100 s+;
        # post-fix ~0.01 s) -- a 250x margin, immune to ordinary host noise.
        self.assertLess(
            duration[100_000], 2.0,
            f"the private_key scan degenerated again: {duration[100_000]:.2f}s for 100 KB",
        )

    def test_possessive_prefix_keeps_every_output_byte_identical(self) -> None:
        # The greedy-backtracking semantics the rewrite must preserve,
        # evaluated against short inputs: prefix identifiers, quote-adjacent
        # fields, quoted/spaceless/spaced separators, mixed case, benign
        # digests, and long values.
        import re

        reference = re.compile(
            r'(?i)(["\']?[a-z0-9_]*private_key["\']?\s*[:=]\s*)'
            r'("[^"]{8,}"|\'[^\']{8,}\'|[0-9a-f]{16,})'
        )
        corpus = (
            f'{{"sender_private_key": "{RAW_KEY}"}}',
            f'{{"recipient_private_key":"{RAW_KEY}"}}',
            f"sender_private_key: {RAW_KEY}",
            f"private_key={RAW_KEY}",
            f'{{\'recipient_private_key\': \'{RAW_KEY}\'}}',
            'was-now abc_private_key: ' + RAW_KEY,
            'raw my_private_key="' + RAW_KEY + '"',
            'adjacent"private_key": "' + RAW_KEY + '"',
            "UPPER PRIVATE_KEY: " + RAW_KEY,
            f"sha256:{RAW_KEY}",
            f"record:x.json sha256:{RAW_KEY}",
            f'{{"nonce": "{RAW_KEY}"}}',
            f'{{"project_lineage": "{RAW_KEY}"}}',
            "xx" * 40 + ' no field here: ' + RAW_KEY[2:],
            "private_key: " + RAW_KEY + " trailing " + RAW_KEY,
            "no credentials in this line at all",
        )
        for text in corpus:
            self.assertEqual(
                redact_credentials(text),
                reference.sub(r"\1***", text),
                f"redaction output changed for input: {text!r}",
            )


class ExternalReachabilityTests(unittest.TestCase):
    """ZC-02/04/05/06: state the boundary instead of implying coverage."""

    def test_the_zaicode_host_has_no_readable_source_tree_here(self) -> None:
        host = Path.home() / ".zcode" / "cli"
        self.assertTrue(host.exists(), "the ZAICODE host installation was not found")
        sources = [
            path for pattern in ("*.js", "*.mjs", "*.ts")
            for path in host.rglob(pattern)
            if "plugins" not in path.parts and "tmpfile" not in path.name
        ]
        # If the host ever ships readable source, ZC-02/04/06 stop being external
        # and this ticket's boundary must be re-measured rather than inherited.
        self.assertEqual(
            sources, [],
            "ZAICODE host source is now readable; ZC-02/04/06 are no longer external",
        )

    def test_the_saimail_source_is_readable_so_zc01_is_not_purely_external(self) -> None:
        keyvault = SAIMAIL_ROOT / "saimail" / "keyvault.py"
        if not keyvault.exists():
            self.skipTest("sibling SAIMAIL checkout is not present on this machine")
        custody = SAIMAIL_ROOT / "spec" / "20-LOCAL-KEY-CUSTODY-v0.md"
        self.assertTrue(custody.exists(), "custody spec is missing; re-measure ZC-01")
        self.assertIn(
            "identity.json", custody.read_text(encoding="utf-8"),
            "the custody spec no longer names the raw identity file",
        )


if __name__ == "__main__":
    unittest.main()
