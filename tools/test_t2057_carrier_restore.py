"""T-2057: a COMMITTED regression receipt whose evidence carrier is gone must
refuse with the restore route named.

Before this Work a missing carrier leaked FileNotFoundError (WinError 2) out of
``_records``: the instrument carried no subject and no permitted next move, so
every anchored ``work regression`` pair in the project died on two lost
carriers. The refusal is now typed and names the carrier and the op.

The verifier is hermetic: it drives ``_records`` against a disposable fixture
root and a stubbed journal reader, so it proves the branch itself and never
depends on the host project's memory.
"""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.saipen_engine import regression_execution as re_mod  # noqa: E402

OP_ID = "regression-execution-t2057fixture"
CARRIER = ".saipen/evidence/regression/regression-execution-t2057fixture.json"


def _carrier_bytes():
    body = {"op_id": OP_ID, "evidence_class": re_mod.PROFILE}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _receipt(sha256):
    return {
        "op_id": OP_ID,
        "status": "COMMITTED",
        "receipt_metadata": {
            "regression_record": CARRIER,
            "regression_sha256": sha256,
        },
    }


class CarrierRefusalTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="t2057-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.raw = _carrier_bytes()
        self.sha = hashlib.sha256(self.raw).hexdigest()
        real = re_mod.semantic_receipts_for_operation_safe

        def fake_journal(root, operation):
            return [self._receipt], ()

        re_mod.semantic_receipts_for_operation_safe = fake_journal
        self.addCleanup(setattr, re_mod, "semantic_receipts_for_operation_safe", real)

    def _records(self):
        return re_mod._records(self.root)

    def test_present_carrier_authenticates(self):
        target = self.root / CARRIER
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.raw)
        self._receipt = _receipt(self.sha)
        records = self._records()
        self.assertEqual(len(records), 1)
        receipt, value, relative = records[0]
        self.assertEqual(receipt["op_id"], OP_ID)
        self.assertEqual(relative, CARRIER)
        self.assertEqual(value["op_id"], OP_ID)
        self.assertEqual(value["evidence_class"], re_mod.PROFILE)

    def test_absent_carrier_refuses_with_the_restore_route_named(self):
        self._receipt = _receipt(self.sha)
        with self.assertRaises(ValueError) as caught:
            self._records()
        message = str(caught.exception)
        self.assertIn("carrier is absent", message)
        self.assertIn(CARRIER, message)
        self.assertIn(OP_ID, message)
        self.assertIn("restore the exact committed bytes", message)


if __name__ == "__main__":
    unittest.main()