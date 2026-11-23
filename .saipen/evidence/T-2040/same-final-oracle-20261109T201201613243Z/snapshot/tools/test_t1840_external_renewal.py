"""Owned current external proof can supersede an immutable legacy receipt."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import external, operations  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from test_external_revalidation import EXT_LINEAGE, _make_external_repo, _make_local_repo  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402


def setUpModule():
    isolate_host_session()


def digest(root):
    result = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return result.hexdigest()


class ExternalRenewalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="saipen-external-renewal-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.upstream, self.old_commit = _make_external_repo(self.base)
        self.root = _make_local_repo(self.base, self.old_commit)
        initial = operations.resolve_external_ticket(
            self.root,
            "T-100",
            "tester",
            authority=EXT_LINEAGE,
            implementation=f"T-289@{self.old_commit}",
            resolution_reason="UPSTREAM_FIX_VERIFIED",
            runs=["echo original-operator-check"],
        )
        self.assertTrue(initial.ok, initial.to_dict())
        self.old = external.load_receipt(self.root, initial.data["receipt_id"])
        self.old_path = self.root / external.EXTERNAL_DIR / (self.old["receipt_id"] + ".json")
        self.old_bytes = self.old_path.read_bytes()
        (self.upstream / "implementation.txt").write_text("new implementation\n", encoding="utf-8")
        self.git("add", "--", "implementation.txt")
        self.git("-c", "user.name=T", "-c", "user.email=t@e", "commit", "-m", "next implementation")
        self.new_commit = self.git("rev-parse", "HEAD").stdout.strip()
        self.contract = ".saipen/evidence/current-external.json"
        self.write_check()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.upstream), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def write_check(self, kind="pass"):
        body = (
            "import pathlib,unittest\n"
            "class Current(unittest.TestCase):\n"
            " def test_current(self):\n"
            "  p=pathlib.Path('.saipen/cache/executed'); p.parent.mkdir(exist_ok=True); "
            "p.write_text('executed')\n"
            + (
                "  self.fail('real negative control')\n"
                if kind == "fail"
                else "  self.assertTrue(True)\n"
            )
            + "unittest.main()\n"
        )
        if kind == "zero":
            body = "import unittest\nunittest.main()\n"
        if kind == "skip":
            body = body.replace(
                " def test_current", " @unittest.skip('not executed')\n def test_current"
            )
        (self.root / "current_check.py").write_text(body, encoding="utf-8")
        contract = {
            "schema": 1,
            "command": ["{python}", "-B", "current_check.py"],
            "format": "unittest",
            "context": ["current_check.py"],
            "oracle_files": ["current_check.py"],
            "subject_files": [],
            "timeout": 60,
        }
        (self.root / self.contract).write_text(json.dumps(contract), encoding="utf-8")

    def renew(self, **changes):
        method = getattr(operations, "renew_external_ticket", None)
        self.assertTrue(callable(method), "authenticated current external proof renewal is missing")
        return method(
            self.root,
            "T-100",
            changes.pop("agent", "tester"),
            implementation=changes.pop("implementation", f"T-289@{self.new_commit}"),
            verification_contract=changes.pop("verification_contract", self.contract),
            implementation_paths=changes.pop("implementation_paths", ["implementation.txt"]),
            external_root=changes.pop("external_root", self.upstream),
            **changes,
        )

    def refused_unchanged(self, **changes):
        before = digest(self.root)
        result = self.renew(**changes)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(digest(self.root), before)
        self.assertFalse((self.root / ".saipen/cache/executed").exists())
        return result

    def test_current_proof_preserves_original_receipt_and_defect_contract(self):
        result = self.renew()
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(self.old_path.read_bytes(), self.old_bytes)
        current = external.load_receipt(self.root, result.data["receipt_id"])
        self.assertEqual(current["defect_contract_digest"], self.old["defect_contract_digest"])
        self.assertEqual(current["predecessor"]["receipt_id"], self.old["receipt_id"])
        self.assertEqual(current["external_authority"], self.old["external_authority"])
        self.assertEqual(current["external_implementation"], f"T-289@{self.new_commit}")
        self.assertEqual(
            current["verification"][0]["summary"], {"ran": 1, "failed": 0, "skipped": 0}
        )
        self.assertTrue(current["verification"][0]["contract_sha256"])
        self.assertTrue(current["verification"][0]["context_sha256"])
        board = parse_board((self.root / ".saipen/BOARD.md").read_text(encoding="utf-8"))
        self.assertEqual(board["tickets"]["T-100"]["section"], "## DONE")
        self.assertEqual(
            external.resolution_problems(self.root, "T-100", board["tickets"]["T-100"]), []
        )

    def test_dry_run_does_not_execute_or_write(self):
        before = digest(self.root)
        result = self.renew(dry_run=True)
        self.assertTrue(result.ok, result.to_dict())
        self.assertFalse(result.data["verification_executed"])
        self.assertEqual(digest(self.root), before)

    def test_renewal_from_foreign_git_hook_preserves_predecessor_and_ancestry(self):
        caller = self.base / "hook-caller"
        caller.mkdir()
        clean = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        for arguments in (("init",), ("-c", "user.name=T", "-c", "user.email=t@e",
                                     "commit", "--allow-empty", "-m", "caller")):
            subprocess.run(["git", "-C", str(caller), *arguments], env=clean,
                           check=True, capture_output=True, timeout=30)
        with mock.patch.dict(os.environ, {
            "GIT_DIR": str(caller / ".git"), "GIT_COMMON_DIR": str(caller / ".git"),
            "GIT_WORK_TREE": str(caller), "GIT_INDEX_FILE": str(caller / ".git/index"),
        }):
            result = self.renew()
            self.assertTrue(result.ok, result.to_dict())
            current = external.load_receipt(self.root, result.data["receipt_id"])
            self.assertEqual(current["predecessor"]["receipt_id"], self.old["receipt_id"])
            self.assertEqual(self.old_path.read_bytes(), self.old_bytes)
            board = parse_board((self.root / ".saipen/BOARD.md").read_text(encoding="utf-8"))
            self.assertEqual(external.resolution_problems(
                self.root, "T-100", board["tickets"]["T-100"],
            ), [])

    def test_exact_repeat_reuses_the_current_immutable_receipt(self):
        first = self.renew()
        self.assertTrue(first.ok, first.to_dict())
        before = digest(self.root)
        second = self.renew()
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual(second.code, "ALREADY_APPLIED")
        self.assertEqual(digest(self.root), before)

    @unittest.skipUnless(os.name == "nt", "Windows executable path spelling")
    def test_receipt_and_repeat_accept_same_executable_with_different_case(self):
        first = self.renew()
        self.assertTrue(first.ok, first.to_dict())
        entry = external.load_receipt(self.root, first.data["receipt_id"])["verification"][0]
        executable = Path(sys.executable)
        alternate = str(executable.with_name(executable.name.swapcase()))
        self.assertNotEqual(alternate, str(executable))
        self.assertTrue(os.path.samefile(alternate, executable))
        before = digest(self.root)
        with mock.patch.object(sys, "executable", alternate):
            self.assertIsNone(external.receipt_plan(entry, root=self.root)[1])
            board = parse_board((self.root / ".saipen/BOARD.md").read_text(encoding="utf-8"))
            self.assertEqual(
                external.resolution_problems(self.root, "T-100", board["tickets"]["T-100"]), []
            )
            second = self.renew()
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual(second.code, "ALREADY_APPLIED")
        self.assertEqual(digest(self.root), before)

    def test_runtime_bytes_arguments_and_separate_copy_remain_bound(self):
        result = self.renew()
        self.assertTrue(result.ok, result.to_dict())
        entry = external.load_receipt(self.root, result.data["receipt_id"])["verification"][0]
        copied = self.base / Path(sys.executable).name
        shutil.copyfile(sys.executable, copied)
        changed_entries = (
            {**entry, "runtime": {**entry["runtime"], "sha256": "0" * 64}},
            {**entry, "argv": [*entry["argv"][:-1], "substituted.py"]},
            {
                **entry,
                "argv": [str(copied), *entry["argv"][1:]],
                "runtime": {**entry["runtime"], "path": str(copied)},
            },
        )
        for changed in changed_entries:
            with self.subTest(entry=changed):
                self.assertIsNotNone(external.receipt_plan(changed, root=self.root)[1])

    def test_changed_environment_requires_new_execution(self):
        first = self.renew()
        self.assertTrue(first.ok, first.to_dict())
        with mock.patch.dict(os.environ, {"EXTERNAL_RENEWAL_ENV_CONTROL": "changed"}):
            second = self.renew()
        self.assertTrue(second.ok, second.to_dict())
        self.assertNotEqual(second.code, "ALREADY_APPLIED")
        self.assertNotEqual(second.data["receipt_id"], first.data["receipt_id"])

    def test_diagnostic_carriers_leave_child_and_verifier_unchanged(self):
        check = self.root / "current_check.py"
        body = check.read_text(encoding="utf-8").replace(
            "import pathlib,unittest", "import os,pathlib,unittest"
        )
        check.write_text(
            body.replace(
                "  self.assertTrue(True)\n",
                "  self.assertNotIn('CODEX_TOOL_CALL_ID', os.environ)\n"
                "  self.assertNotIn('PROMPT', os.environ)\n",
            ),
            encoding="utf-8",
        )
        with mock.patch.dict(os.environ, {"CODEX_TOOL_CALL_ID": "first", "PROMPT": "first>"}):
            first = self.renew()
        self.assertTrue(first.ok, first.to_dict())
        before = digest(self.root)
        with mock.patch.dict(os.environ, {"CODEX_TOOL_CALL_ID": "second", "PROMPT": "second>"}):
            second = self.renew()
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual(second.code, "ALREADY_APPLIED")
        self.assertEqual(digest(self.root), before)

    def test_failed_receipt_commit_refusal_wins(self):
        from saipen_engine.result import Result

        self.write_check("zero")
        with mock.patch.object(operations, "apply_plan", return_value=Result(False, "STALE_STATE")):
            result = self.renew()
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "STALE_STATE")
        self.assertEqual(external.existing_receipts(self.root), [self.old_path])

    def test_foreign_owner_work_authority_or_changed_contract_refuses(self):
        self.refused_unchanged(agent="another-owner")
        self.refused_unchanged(implementation=f"T-999@{self.new_commit}")
        board = self.root / ".saipen/BOARD.md"
        text = board.read_text(encoding="utf-8")
        board.write_text(text.replace("verify: python", "verify: changed python"), encoding="utf-8")
        self.refused_unchanged()
        board.write_text(text.replace(EXT_LINEAGE, "lineage-" + "f" * 32), encoding="utf-8")
        self.refused_unchanged()

    def test_missing_unowned_or_uncommitted_predecessor_refuses(self):
        self.old_path.write_text("{}", encoding="utf-8")
        self.refused_unchanged()

    def test_unrelated_or_missing_external_generation_refuses(self):
        self.refused_unchanged(implementation="T-289@deadbeef")
        self.git("checkout", "--orphan", "unrelated")
        self.git(
            "-c",
            "user.name=T",
            "-c",
            "user.email=t@e",
            "commit",
            "--allow-empty",
            "-m",
            "unrelated",
        )
        other = self.git("rev-parse", "HEAD").stdout.strip()
        self.refused_unchanged(implementation=f"T-289@{other}")

    def test_source_and_operator_gates_still_refuse(self):
        with mock.patch(
            "saipen_engine.intake.work_closure_gate",
            return_value={"ok": False, "code": "SOURCE_UNRESOLVED"},
        ):
            self.refused_unchanged()
        with mock.patch.object(
            external, "operator_gate_problem", return_value="WAIT_USER_DECISION"
        ):
            self.refused_unchanged()

    def test_zero_skipped_and_failed_checks_never_renew_done_proof(self):
        for kind in ("zero", "skip", "fail"):
            with self.subTest(kind=kind):
                self.write_check(kind)
                board_before = (self.root / ".saipen/BOARD.md").read_bytes()
                state_before = (self.root / ".saipen/STATE.md").read_bytes()
                result = self.renew()
                self.assertFalse(result.ok, result.to_dict())
                self.assertEqual(result.code, "EXTERNAL_VERIFICATION_FAILED")
                self.assertEqual((self.root / ".saipen/BOARD.md").read_bytes(), board_before)
                self.assertEqual((self.root / ".saipen/STATE.md").read_bytes(), state_before)
                self.assertEqual(self.old_path.read_bytes(), self.old_bytes)

    def test_tampered_current_contract_cannot_be_replayed(self):
        result = self.renew()
        self.assertTrue(result.ok, result.to_dict())
        record = external.load_receipt(self.root, result.data["receipt_id"])
        entry = record["verification"][0]
        plan, error = external.receipt_plan(entry, root=self.root)
        self.assertIsNone(error)
        self.assertEqual(plan["argv"], entry["argv"])
        (self.root / "current_check.py").write_text(
            "raise RuntimeError('substituted')\n", encoding="utf-8"
        )
        self.assertIsNotNone(external.receipt_plan(entry, root=self.root)[1])
        (self.root / self.contract).write_text("{}", encoding="utf-8")
        self.assertIsNotNone(external.receipt_plan(entry, root=self.root)[1])

    def test_active_work_is_preserved(self):
        added = operations.ticket_add(self.root, "tester", "P2", "independent", [], "proof")
        self.assertTrue(added.ok, added.to_dict())
        self.assertTrue(
            operations.apply_claim(self.root, added.data["ticket"], "tester", explicit=True).ok
        )
        before = operations.parse_state(
            (self.root / ".saipen/STATE.md").read_text(encoding="utf-8")
        )
        result = self.renew()
        self.assertTrue(result.ok, result.to_dict())
        after = operations.parse_state((self.root / ".saipen/STATE.md").read_text(encoding="utf-8"))
        for key in ("phase", "task", "next_action", "agent", "goal_tickets", "execution_intent"):
            self.assertEqual(before.get(key), after.get(key), key)

    def test_readonly_cli_refuses_before_execution(self):
        import saipen

        before = digest(self.root)
        with mock.patch.object(
            saipen, "_negotiate_capability", return_value="read-only"
        ), mock.patch.object(saipen, "_emit"):
            code = saipen.main(
                [
                    "--project-root",
                    str(self.root),
                    "--agent",
                    "tester",
                    "ticket",
                    "renew-external",
                    "T-100",
                    "--implementation",
                    f"T-289@{self.new_commit}",
                    "--verification-contract",
                    self.contract,
                    "--paths",
                    "implementation.txt",
                    "--json",
                ]
            )
        self.assertNotEqual(code, 0)
        self.assertEqual(digest(self.root), before)

    def test_external_and_native_bytes_cannot_move_under_current_proof(self):
        native = self.base / "native-input.bin"
        native.write_bytes(b"native-runtime")
        result = self.renew(native_inputs=[str(native)])
        self.assertTrue(result.ok, result.to_dict())
        board = parse_board((self.root / ".saipen/BOARD.md").read_text(encoding="utf-8"))
        native.write_bytes(b"changed-runtime")
        self.assertTrue(external.resolution_problems(self.root, "T-100", board["tickets"]["T-100"]))
        (self.upstream / "implementation.txt").write_text("unreviewed", encoding="utf-8")
        self.assertTrue(external.resolution_problems(self.root, "T-100", board["tickets"]["T-100"]))

    def test_public_cli_uses_sealed_contract(self):
        command = [
            sys.executable,
            "-B",
            str(TOOLS / "saipen.py"),
            "--project-root",
            str(self.root),
            "--agent",
            "tester",
            "ticket",
            "renew-external",
            "T-100",
            "--implementation",
            f"T-289@{self.new_commit}",
            "--verification-contract",
            self.contract,
            "--external-root",
            str(self.upstream),
            "--paths",
            "implementation.txt",
            "--json",
        ]
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=hermetic_env(),
            timeout=90,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(json.loads(process.stdout)["code"], "EXTERNAL_RESOLVED")


if __name__ == "__main__":
    unittest.main()
