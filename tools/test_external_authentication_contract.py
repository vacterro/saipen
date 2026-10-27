"""External trust boundary: sealed-contract authentication (security RED/GREEN).

The autonomous external revalidation path may never execute BOARD prose. An
executable check is authenticated only by the sealed regression-execution
contract (schema 1 under .saipen/evidence/, argv-bound, executable-proven and
hash-bound by regression_execution._runtime), never by a command prefix or a
blacklist. A repository without verifiable Git evidence never passes
commit-ancestry. Operator-only gates (WAIT_USER_DECISION) are never lifted by
an external implementation. Dry run predicts without resolving.

Run standalone:
    python tools/test_external_authentication_contract.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_external_revalidation import (  # noqa: E402
    EXT_LINEAGE,
    _make_external_repo,
    _make_local_repo,
)
from saipen_engine import external as ext_mod  # noqa: E402


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            h.update(path.relative_to(root).as_posix().encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def _write_contract(loc_repo: Path, work: str, *, fail: bool = False) -> str:
    """One sealed regression-execution contract under project evidence."""
    evidence = loc_repo / ".saipen" / "evidence" / "ext-contracts"
    evidence.mkdir(parents=True, exist_ok=True)
    expression = "import sys; sys.exit(1)" if fail else "import sys; sys.exit(0)"
    contract = {
        "schema": 1,
        "command": ["{python}", "-c", expression],
        "format": "pytest",
        "context": ["README.md"],
        "oracle_files": ["README.md"],
        "subject_files": [],
        "timeout": 120,
    }
    relative = f".saipen/evidence/ext-contracts/{work}.json"
    (loc_repo / relative).write_text(json.dumps(contract), encoding="utf-8")
    return relative


def _board_row(
    tid, *, verify, commit, authority=True, contract=None, contract_digest=None, blocker=None
):
    fields = [f"verify: {verify}"]
    if authority:
        fields.append(f"external_authority: {EXT_LINEAGE}")
    return (
        f"- [ ] {tid} [P1] external fix | {' | '.join(fields)} | "
        f"external_implementation: T-289@{commit}"
        + (
            f" | verification_contract: {contract}@{contract_digest}"
            if (contract and contract_digest)
            else f" | verification_contract: {contract}"
            if contract
            else ""
        )
        + (f" | blocker: {blocker}" if blocker else " | blocker: BLOCKED_EXTERNAL")
    )


def _board_with(*rows):
    return "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n" + "\n".join(rows) + "\n"


class ExternalAuthenticationContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_dir.name).resolve()

    def tearDown(self):
        self.tmp_dir.cleanup()

    # ── prose is never executable ────────────────────────────────────────────

    def test_prose_command_never_executes_even_with_a_trusted_prefix(self):
        """A safe-prefix command on BOARD prose is not executed evidence."""
        _ext_repo, commit = _make_external_repo(self.tmp)
        marker = self.tmp / "must-not-exist.txt"
        loc_repo = _make_local_repo(
            self.tmp,
            commit,
            board_content=_board_with(
                _board_row(
                    "T-201",
                    commit=commit,
                    verify=f'python -B -c "import pathlib; '
                    f'pathlib.Path(r{chr(39)}{marker}{chr(39)}).write_text({chr(39)}x{chr(39)})"',
                )
            ),
        )
        outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=False)
        self.assertEqual(outcome["revalidated"], 0)
        self.assertEqual(outcome["resolved"], [])
        self.assertFalse(marker.exists(), "BOARD prose was executed")
        self.assertEqual(len(outcome["still_blocked"]), 1)
        self.assertEqual(outcome["still_blocked"][0]["ticket"], "T-201")
        self.assertEqual(outcome["still_blocked"][0]["code"], "EXTERNAL_VERIFICATION_REQUIRED")
        board = (loc_repo / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] T-201", board)
        self.assertEqual(list((loc_repo / ".saipen").rglob("EX-*.json")), [])

    def test_injection_prose_refused_without_shell_parsing(self):
        _ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo = _make_local_repo(
            self.tmp,
            commit,
            board_content=_board_with(
                _board_row(
                    "T-202", commit=commit, verify='python -B -c "import sys" ; rm -rf /tmp/x'
                ),
            ),
        )
        outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=False)
        self.assertEqual(outcome["revalidated"], 0)
        self.assertEqual(outcome["still_blocked"][0]["code"], "EXTERNAL_VERIFICATION_REQUIRED")

    def test_audit_description_prose_never_executes(self):
        _ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo = _make_local_repo(
            self.tmp,
            commit,
            board_content=_board_with(
                _board_row(
                    "T-203",
                    commit=commit,
                    verify="every actionable clause of SRC-236 is terminal with "
                    "evidence; linked work DONE",
                )
            ),
        )
        outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=False)
        self.assertEqual(outcome["revalidated"], 0)
        self.assertEqual(outcome["still_blocked"][0]["code"], "EXTERNAL_VERIFICATION_REQUIRED")

    # ── the sealed contract is the only executable authority ─────────────────

    def test_sealed_contract_resolves_and_the_receipt_is_arg_authenticated(self):
        _ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo = _make_local_repo(self.tmp, commit)
        (loc_repo / "README.md").write_text("probe\n", encoding="utf-8")
        contract = _write_contract(loc_repo, "T-210")
        board = _board_with(
            _board_row(
                "T-210",
                commit=commit,
                verify="the installed implementation satisfies the contract",
                contract=contract,
            )
        )
        (loc_repo / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")
        outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=False)
        self.assertEqual(outcome["revalidated"], 1, outcome.get("still_blocked"))
        self.assertEqual(outcome["resolved"], ["T-210"])
        receipts = list((loc_repo / ".saipen").rglob("EX-*.json"))
        self.assertEqual(len(receipts), 1)
        record = json.loads(receipts[0].read_text(encoding="utf-8"))
        entry = record["verification"][0]
        self.assertTrue(entry["executed"])
        self.assertEqual(entry["result"], "PASS")
        self.assertEqual(entry["argv"][-1], "import sys; sys.exit(0)")
        self.assertTrue(entry["runtime"]["sha256"])
        self.assertIn("verifier", entry)
        board_after = (loc_repo / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertIn("- [x] T-210", board_after)
        self.assertIn("closure_mode: external_implementation", board_after)

    def test_failing_contract_never_terminalizes(self):
        _ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo = _make_local_repo(self.tmp, commit)
        (loc_repo / "README.md").write_text("probe\n", encoding="utf-8")
        contract = _write_contract(loc_repo, "T-211", fail=True)
        board = _board_with(
            _board_row(
                "T-211",
                commit=commit,
                verify="the installed implementation satisfies the contract",
                contract=contract,
            )
        )
        (loc_repo / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")
        outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=False)
        self.assertEqual(outcome["revalidated"], 0)
        self.assertEqual(len(outcome["still_blocked"]), 1)
        self.assertEqual(outcome["still_blocked"][0]["code"], "EXTERNAL_VERIFICATION_FAILED")
        self.assertIn(
            "- [ ] T-211", (loc_repo / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        )

    def test_contract_outside_evidence_is_not_an_executable_authority(self):
        _ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo = _make_local_repo(self.tmp, commit)
        (loc_repo / "README.md").write_text("probe\n", encoding="utf-8")
        contract = _write_contract(loc_repo, "T-212")
        outside = "ext-intruder.json"
        (loc_repo / outside).write_text(
            (loc_repo / contract).read_text(encoding="utf-8"), encoding="utf-8"
        )
        board = _board_with(
            _board_row(
                "T-212",
                commit=commit,
                verify="the installed implementation satisfies the contract",
                contract=outside,
            )
        )
        (loc_repo / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")
        outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=False)
        self.assertEqual(outcome["revalidated"], 0)
        self.assertEqual(
            outcome["still_blocked"][0]["code"], "EXTERNAL_VERIFICATION_CONTRACT_INVALID"
        )

    def test_tampered_contract_content_fails_digest_verification(self):
        """Content tampering or substitution of a contract is strictly refused."""
        _ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo = _make_local_repo(self.tmp, commit)
        (loc_repo / "README.md").write_text("probe\n", encoding="utf-8")
        contract = _write_contract(loc_repo, "T-213")
        original_digest = "sha256:" + hashlib.sha256((loc_repo / contract).read_bytes()).hexdigest()
        tampered_data = json.loads((loc_repo / contract).read_text(encoding="utf-8"))
        tampered_data["command"] = ["{python}", "-c", "import sys; sys.exit(0)  # modified"]
        (loc_repo / contract).write_text(json.dumps(tampered_data), encoding="utf-8")
        board = _board_with(
            _board_row(
                "T-213",
                commit=commit,
                verify="the installed implementation satisfies the contract",
                contract=contract,
                contract_digest=original_digest,
            )
        )
        (loc_repo / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")
        outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=False)
        self.assertEqual(outcome["revalidated"], 0)
        self.assertEqual(len(outcome["still_blocked"]), 1)
        self.assertEqual(
            outcome["still_blocked"][0]["code"], "EXTERNAL_VERIFICATION_CONTRACT_INVALID"
        )
        self.assertIn("content tampered or substituted", outcome["still_blocked"][0]["detail"])

    def test_matching_contract_digest_verifies_and_resolves(self):
        """A contract matching its registered digest resolves cleanly."""
        _ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo = _make_local_repo(self.tmp, commit)
        (loc_repo / "README.md").write_text("probe\n", encoding="utf-8")
        contract = _write_contract(loc_repo, "T-214")
        digest = "sha256:" + hashlib.sha256((loc_repo / contract).read_bytes()).hexdigest()
        board = _board_with(
            _board_row(
                "T-214",
                commit=commit,
                verify="the installed implementation satisfies the contract",
                contract=contract,
                contract_digest=digest,
            )
        )
        (loc_repo / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")
        outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=False)
        self.assertEqual(outcome["revalidated"], 1)
        self.assertEqual(outcome["resolved"], ["T-214"])

    # ── Git evidence is mandatory for commit ancestry ────────────────────────

    def test_repository_without_git_never_passes_ancestry(self):
        ext_repo, commit = _make_external_repo(self.tmp)
        (ext_repo / ".git").rename(self.tmp / "hidden-git")
        loc_repo = _make_local_repo(self.tmp, commit)
        result = ext_mod.inspect_external_dependency(
            loc_repo, EXT_LINEAGE, f"T-289@{commit}", project_root=ext_repo
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "EXTERNAL_GIT_EVIDENCE_MISSING")

    def test_done_ticket_and_matching_lineage_alone_are_insufficient(self):
        ext_repo, commit = _make_external_repo(self.tmp)
        (ext_repo / ".git").rename(self.tmp / "hidden-git-2")
        loc_repo = _make_local_repo(self.tmp, commit)
        outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=False)
        self.assertEqual(outcome["revalidated"], 0)
        self.assertEqual(outcome["still_blocked"][0]["code"], "EXTERNAL_GIT_EVIDENCE_MISSING")

    # ── operator gates are never lifted by an external implementation ────────

    def test_wait_user_decision_row_never_resolves_externally(self):
        _ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo = _make_local_repo(self.tmp, commit)
        (loc_repo / "README.md").write_text("probe\n", encoding="utf-8")
        contract = _write_contract(loc_repo, "T-220")
        board = _board_with(
            _board_row(
                "T-220",
                commit=commit,
                verify="the installed implementation satisfies the contract",
                contract=contract,
                blocker="WAIT_USER_DECISION -- pick the rule: A|B|C; Operator reply: T-220 A|B|C",
            )
        )
        (loc_repo / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")
        outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=False)
        self.assertEqual(outcome["revalidated"], 0)
        self.assertEqual(outcome["resolved"], [])
        self.assertEqual(outcome["still_blocked"][0]["code"], "OPERATOR_DECISION_REQUIRED")
        self.assertIn(
            "- [ ] T-220", (loc_repo / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        )
        self.assertEqual(list((loc_repo / ".saipen").rglob("EX-*.json")), [])

    # ── legacy receipts carry no executable authority ────────────────────────

    def test_legacy_receipt_verification_is_never_re_shelled_after_a_generation_move(self):
        _ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo = _make_local_repo(self.tmp, commit)
        (loc_repo / "README.md").write_text("probe\n", encoding="utf-8")
        contract = _write_contract(loc_repo, "T-230")
        board = _board_with(
            _board_row(
                "T-230",
                commit=commit,
                verify="the installed implementation satisfies the contract",
                contract=contract,
            )
        )
        (loc_repo / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")
        from saipen_engine.operations import resolve_external_ticket

        resolved = resolve_external_ticket(
            loc_repo,
            "T-230",
            "tester",
            authority=EXT_LINEAGE,
            implementation=f"T-289@{commit}",
            resolution_reason="UPSTREAM_FIX_VERIFIED",
            runs=["echo legacy-operator-command"],
        )
        self.assertTrue(resolved.ok, resolved.message)
        receipt_files = list((loc_repo / ".saipen").rglob("EX-*.json"))
        self.assertEqual(receipt_files[0].name, "EX-000001.json")
        moved = dict(ext_mod.engine_identity())
        moved["engine_digest"] = "sha256:" + "f" * 64
        with patch.object(ext_mod, "engine_identity", return_value=moved):
            outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=False)
        self.assertEqual(outcome["revalidated"], 0)
        self.assertEqual(len(outcome["still_blocked"]), 1)
        self.assertEqual(
            outcome["still_blocked"][0]["code"], "EXTERNAL_VERIFICATION_UNAUTHENTICATED"
        )

    # ── dry run predicts, it does not resolve ────────────────────────────────

    def test_dry_run_predicts_eligible_without_resolving_or_writing(self):
        _ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo = _make_local_repo(self.tmp, commit)
        (loc_repo / "README.md").write_text("probe\n", encoding="utf-8")
        contract = _write_contract(loc_repo, "T-240")
        board = _board_with(
            _board_row(
                "T-240",
                commit=commit,
                verify="the installed implementation satisfies the contract",
                contract=contract,
            ),
            _board_row("T-241", commit=commit, verify="chain", contract=contract),
        )
        (loc_repo / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")
        before = _tree_hash(loc_repo / ".saipen")
        outcome = ext_mod.revalidate_external_dependencies(loc_repo, "tester", dry_run=True)
        self.assertEqual(outcome["revalidated"], 0)
        self.assertEqual(outcome["resolved"], [])
        self.assertEqual(sorted(outcome["predicted_eligible"]), ["T-240", "T-241"])
        self.assertEqual(_tree_hash(loc_repo / ".saipen"), before)
        self.assertEqual(list((loc_repo / ".saipen").rglob("EX-*.json")), [])


if __name__ == "__main__":
    unittest.main()
