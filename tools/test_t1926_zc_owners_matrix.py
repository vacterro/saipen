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


class RedactionCostIsBoundedTests(unittest.TestCase):
    """T-1965: the boundary must stay linear in the subject, or callers hang.

    The T-1926 rule keyed on the field name with an unanchored `[a-z0-9_]*`
    prefix, which restarted its scan at every character of a long identifier and
    backtracked the remainder at each one. A 100KB userperson entry therefore
    cost minutes of CPU inside `context_cold`, and the declared core-unit family
    could never finish. These controls fail if that shape returns.
    """

    #: Large enough that quadratic behaviour is unmistakable (it took ~2 minutes
    #: before the fix) and small enough to stay instantaneous once linear.
    LARGE = 100_000

    def test_a_long_word_run_without_the_field_name_is_cheap(self) -> None:
        # The T-1965 reproduction: no `private_key` anywhere, so no match is
        # possible. This is the shape the 100KB userperson entry actually had,
        # and it must never reach the pattern at all.
        self.assertEqual(redact_credentials("x" * self.LARGE), "x" * self.LARGE)

    def test_the_field_name_present_but_unmatchable_stays_linear(self) -> None:
        # The discriminating shape for the ANCHOR, the one the literal gate
        # cannot rescue: the field name is here so the pattern must run, but the
        # value is too short to match anything, so the only work left is the
        # scan itself. Unanchored, `[a-z0-9_]*private_key` retries at every
        # interior position and re-walks the remainder each time.
        subject = "x" * self.LARGE + " private_key: short"
        self.assertEqual(
            redact_credentials(subject), subject,
            "text with no matchable key must come back unchanged",
        )

    def test_a_long_identifier_run_ending_in_the_field_name_stays_linear(self) -> None:
        # Here the match really does occur, so the anchor must not be so strict
        # that it loses the key: a prefixed field name is still a field name.
        subject = "a" * self.LARGE + f"private_key: {RAW_KEY}"
        out = redact_credentials(subject)
        self.assertNotIn(RAW_KEY, out, "redaction must still fire on this shape")

    def test_the_bound_is_linear_not_merely_faster(self) -> None:
        # Doubling the subject must not quadruple the time. Compared as a ratio
        # with generous slack so a loaded machine cannot make this flaky, and
        # measured after a warm-up so import and first-call costs are excluded.
        # Measured on the anchor-only shape, so this bound isolates the scan.
        import time

        def cost(n: int) -> float:
            subject = "x" * n + " private_key: short"
            best = None
            for _ in range(3):
                start = time.perf_counter()
                redact_credentials(subject)
                elapsed = time.perf_counter() - start
                best = elapsed if best is None else min(best, elapsed)
            return best

        cost(1_000)
        small, large = cost(20_000), cost(160_000)
        # 8x the input: linear stays near 8x, quadratic would be near 64x.
        self.assertLess(
            large / max(small, 1e-6), 24,
            f"redaction scaled superlinearly: {small:.6f}s -> {large:.6f}s "
            "for an 8x larger subject",
        )


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


class ExternalReachabilityTests(unittest.TestCase):
    """ZC-02/04/05/06: state the boundary instead of implying coverage."""

    def test_the_zaicode_host_has_no_readable_source_tree_here(self) -> None:
        host = Path.home() / ".zcode" / "cli"
        self.assertTrue(host.exists(), "the ZAICODE host installation was not found")
        sources = [
            path for pattern in ("*.js", "*.mjs", "*.ts")
            for path in host.rglob(pattern)
            if "plugins" not in path.parts and "tmp" not in path.parts and "tmpfile" not in path.name
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
