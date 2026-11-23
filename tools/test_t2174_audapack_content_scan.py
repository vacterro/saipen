"""HANDOFF 2026-11-23: AUDAPACK must be safe by CONTENT, not only by path.

The four untracked research-kitchen files (bg.env, fg.env, bgfamily.json,
fgfamily.json) carried a plaintext EXA_API_KEY and were packaged into the
handoff archive. Path denial closes the known shapes; the byte scan closes the
general case. Both are proven here with synthetic values only.
"""

from __future__ import annotations

import unittest

from saipen_engine.distribution import is_non_exportable_path
from saipen_engine.export_security import scan_bytes


class AudapackContentGateTests(unittest.TestCase):
    # Synthetic values. No real credential is read or emitted by this test.
    LIVE_BODIES = (
        ("leak.env", b"EXA_API_KEY=exa-FaKeL1v3Value0123456789abcdefXYZ\n"),
        ("openai.json", b'{"api_key": "sk-REALSHAPEabcdefghijklmnopqrstuvwxyz"}\n'),
        ("github.txt", b"token = ghp_aBcDeF1234567890gHjKlMnOpQrStUvWxYz01\n"),
        ("aws.json", b"AWS_ACCESS_KEY_ID=AKIAIOSFODNN7SYNTHETIC\n"),
        ("pem", b"-----BEGIN PRIVATE KEY-----\nMIIE\n"),
    )

    # Fixture/sentinel shapes used by the project's own tests must stay allowed.
    SAFE_BODIES = (
        b'body = "api_key = sk-live-SECRET-VALUE-FOR-TEST"\n',
        b'cred_objective = "fix the ghp_abcdefghijklmnopqrstuvwxyz012345 leak"\n',
        b'SECRET = "sk-ant-SENTINEL-NOT-A-REAL-KEY"\n',
        b'sk-123456789012345678901234567890\n',
    )

    KITCHEN_EXPORTS = (
        ".saipen/kitchen/bg.env",
        ".saipen/kitchen/fg.env",
        ".saipen/kitchen/bgfamily.json",
        ".saipen/kitchen/fgfamily.json",
    )

    def test_path_denial_covers_kitchen_secret_exports(self):
        for path in self.KITCHEN_EXPORTS:
            with self.subTest(path=path):
                self.assertTrue(is_non_exportable_path(path))

    def test_live_credential_shapes_are_detected_by_content(self):
        for path, body in self.LIVE_BODIES:
            with self.subTest(path=path):
                findings = scan_bytes(path, body)
                self.assertTrue(findings, f"live credential in {path} not detected")
                for finding in findings:
                    self.assertEqual(finding.path, path)
                    self.assertEqual(len(finding.blob_sha256), 64)
                    self.assertNotIn(b"exa-SYNTHETIC", str(finding).encode())

    def test_fixture_shapes_stay_exportable(self):
        for body in self.SAFE_BODIES:
            with self.subTest(body=body[:24]):
                self.assertEqual(scan_bytes("fixture.py", body), [])

    def test_findings_never_contain_the_secret_value(self):
        secret = b"EXA_API_KEY=exa-SUPERSECRETVALUE0123456789abcdef\n"
        findings = scan_bytes("leak.env", secret)
        self.assertTrue(findings)
        for finding in findings:
            self.assertNotIn("SUPERSECRETVALUE", finding.diagnostic())


if __name__ == "__main__":
    unittest.main()
