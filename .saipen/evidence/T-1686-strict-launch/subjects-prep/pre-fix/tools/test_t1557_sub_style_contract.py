"""Fresh worker creation and adoption must agree with strict health reads."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import subs as S  # noqa: E402
from saipen_engine.state import parse_state_or_error, patch_state  # noqa: E402
from test_crew_applicability import FULL_ROSTER, REPO, _seed  # noqa: E402
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class WorkerStyleContractTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="t1557-worker-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        _seed(self.root, roles=())

    def _state_path(self, name: str = "saihunt") -> Path:
        return self.root / S.SUBS_REL / name / "STATE.md"

    def _files(self) -> dict[str, bytes]:
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }

    def _assert_current(self, name: str) -> None:
        fields, error = parse_state_or_error(self._state_path(name).read_text(encoding="utf-8"))
        self.assertIsNone(error, error)
        self.assertEqual(fields["style_contract"], CURRENT_STYLE_CONTRACT)
        result = S.sub_list(self.root)
        self.assertTrue(result.ok, result.to_json())
        health = next(item for item in result.data["subs"] if item["name"] == name)
        self.assertEqual(health["role_revision_state"], "CURRENT", health)
        self.assertNotEqual(health["health"], "INVALID", health)

    def test_fresh_builtin_and_generic_workers_are_readable_and_current(self) -> None:
        for name in (*FULL_ROSTER, "saicustom"):
            with self.subTest(name=name):
                result = S.sub_spawn(self.root, name, REPO.as_posix())
                self.assertTrue(result.ok, result.to_json())
                self._assert_current(name)

    def test_adoption_repairs_stale_style_without_changing_work(self) -> None:
        _seed(self.root, roles=("saihunt",))
        path = self._state_path()
        path.write_text(
            patch_state(path.read_text(encoding="utf-8"), {"style_contract": "ded-deadbeef"}),
            encoding="utf-8",
        )
        before = self._files()
        preview = S.sub_adopt(self.root, "saihunt", REPO.as_posix(), dry_run=True)
        self.assertTrue(preview.ok, preview.to_json())
        self.assertEqual(self._files(), before)
        applied = S.sub_adopt(self.root, "saihunt", REPO.as_posix())
        self.assertTrue(applied.ok, applied.to_json())
        self._assert_current("saihunt")
        for relative, raw in before.items():
            if relative.endswith(("BOARD.md", "LOG.md")):
                self.assertEqual((self.root / relative).read_bytes(), raw, relative)

    def test_missing_style_authority_refuses_spawn_without_writes(self) -> None:
        before = self._files()
        with mock.patch.object(S, "running_style_token", return_value=None, create=True):
            for dry_run in (True, False):
                with self.subTest(dry_run=dry_run):
                    result = S.sub_spawn(self.root, "saihunt", REPO.as_posix(), dry_run=dry_run)
                    self.assertFalse(result.ok, result.to_json())
                    self.assertEqual(result.code, "VALIDATION_FAILED")
                    self.assertEqual(self._files(), before)

    def test_missing_style_authority_refuses_adoption_without_writes(self) -> None:
        _seed(self.root, roles=("saihunt",))
        before = self._files()
        with mock.patch.object(S, "running_style_token", return_value=None, create=True):
            for dry_run in (True, False):
                with self.subTest(dry_run=dry_run):
                    result = S.sub_adopt(self.root, "saihunt", REPO.as_posix(), dry_run=dry_run)
                    self.assertFalse(result.ok, result.to_json())
                    self.assertEqual(result.code, "VALIDATION_FAILED")
                    self.assertEqual(self._files(), before)

    def test_adoption_does_not_hide_unrelated_invalid_state(self) -> None:
        _seed(self.root, roles=("saihunt",))
        path = self._state_path()
        path.write_text(
            patch_state(path.read_text(encoding="utf-8"), {"mode": "invalid-mode"}),
            encoding="utf-8",
        )
        before = self._files()
        for dry_run in (True, False):
            with self.subTest(dry_run=dry_run):
                result = S.sub_adopt(self.root, "saihunt", REPO.as_posix(), dry_run=dry_run)
                self.assertFalse(result.ok, result.to_json())
                self.assertEqual(result.code, "VALIDATION_FAILED")
                self.assertEqual(self._files(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
