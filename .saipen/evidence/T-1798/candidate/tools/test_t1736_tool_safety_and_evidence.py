"""T-1736 / SRC-234: Tool Safety Patterns and Validation Evidence Handling.

Audit Inbox Layer: audit/SAIPEN_20261011_1841.md

Verifies:
1. Schema Correction and Bounded Retry:
   - One invalid schema call followed by a corrected call succeeds.
   - Two equivalent schema failures with unchanged parameters/state stop before
     a blind third repeat.
2. File Safety Protections:
   - Read-before-write: unread file modification is rejected; read-then-edit succeeds.
   - Optimistic concurrency: stale writes are rejected; rereading permits a valid edit.
3. Task Lifecycle Idempotence:
   - Completed task stop distinguishes an idempotent terminal state from a real failure;
     it does not manufacture false blockers.
4. Validation Evidence and Exit Status Preservation:
   - Piping a failing validator (e.g. to tail) masks non-zero exit codes under a standard shell;
     protocol runners must preserve actual process exit codes and unclipped output.
5. Installation Identity:
   - Version-string equality alone does not prove installation identity;
     the resolved root path and digest are required.
6. Authority Boundary:
   - The ZAICODE host owns tool schemas and file-edit guards;
     SAIPEN owns protocol evidence and recovery contracts.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule():
    isolate_host_session()


class ToolSafetyAndEvidenceTests(unittest.TestCase):
    def test_schema_invalid_then_corrected(self):
        """Invalid argument types fail schema validation; corrected types succeed."""
        def validate_read_call(args: dict) -> tuple[bool, str | None]:
            file_path = args.get("file_path")
            offset = args.get("offset")
            limit = args.get("limit")
            if not file_path or not isinstance(file_path, str):
                return False, "invalid file_path"
            if offset is not None and not isinstance(offset, int):
                return False, "offset must be integer"
            if limit is not None and not isinstance(limit, int):
                return False, "limit must be integer"
            return True, None

        # Call 1: invalid string-valued offset and limit
        valid1, err1 = validate_read_call({"file_path": "a.txt", "offset": "100", "limit": "20"})
        self.assertFalse(valid1)
        self.assertIn("offset must be integer", err1)

        # Call 2: corrected types
        valid2, err2 = validate_read_call({"file_path": "a.txt", "offset": 100, "limit": 20})
        self.assertTrue(valid2)
        self.assertIsNone(err2)

    def test_schema_blind_repeats_bounded(self):
        """Equivalent schema failures stop at the cap instead of blindly repeating."""
        max_repeats = 2
        failures = 0
        calls = []

        def attempt_call(args: dict):
            nonlocal failures
            # Fails if string offset
            if isinstance(args.get("offset"), str):
                failures += 1
                return {"ok": False, "error": "offset must be integer"}
            return {"ok": True}

        repeated_args = {"file_path": "a.txt", "offset": "10"}
        # Loop simulating agent retry policy
        for _ in range(5):
            if failures >= max_repeats:
                calls.append("STOP_AND_REPORT")
                break
            res = attempt_call(repeated_args)
            calls.append("FAILED" if not res["ok"] else "OK")

        self.assertEqual(failures, 2)
        self.assertEqual(calls, ["FAILED", "FAILED", "STOP_AND_REPORT"])

    def test_read_before_edit_contract(self):
        """File modification requires prior read of exact target file; unread edit is rejected."""
        class MockFileEditor:
            def __init__(self):
                self.read_files = set()
                self.contents = {"/test/file.txt": "initial line\n"}

            def read(self, path: str) -> str:
                self.read_files.add(path)
                return self.contents[path]

            def edit(self, path: str, old: str, new: str) -> tuple[bool, str]:
                if path not in self.read_files:
                    return False, "file has not been read in conversation"
                cur = self.contents.get(path, "")
                if old not in cur:
                    return False, "old string not found"
                self.contents[path] = cur.replace(old, new, 1)
                return True, "edited"

        editor = MockFileEditor()
        # Attempt edit without read -> rejected
        ok, err = editor.edit("/test/file.txt", "initial", "updated")
        self.assertFalse(ok)
        self.assertIn("has not been read", err)

        # Read file -> then edit succeeds
        content = editor.read("/test/file.txt")
        self.assertIn("initial line", content)
        ok, _msg = editor.edit("/test/file.txt", "initial", "updated")
        self.assertTrue(ok)
        self.assertEqual(editor.contents["/test/file.txt"], "updated line\n")

    def test_stale_write_reconcile_contract(self):
        """Reject a stale edit; rereading permits an edit under optimistic concurrency."""
        class ConcurrencyEditor:
            def __init__(self):
                self.file_state = "version 1"
                self.read_versions = {}

            def read(self, path: str) -> str:
                self.read_versions[path] = self.file_state
                return self.file_state

            def edit(self, path: str, expected_old: str, new: str) -> tuple[bool, str]:
                read_ver = self.read_versions.get(path)
                if read_ver != self.file_state:
                    return False, "file changed since last read (stale edit)"
                self.file_state = new
                return True, "saved"

        ce = ConcurrencyEditor()
        v = ce.read("foo.txt")
        self.assertEqual(v, "version 1")

        # Simulate concurrent change behind the scenes
        ce.file_state = "version 2 (modified by background job)"

        # Attempt edit using stale read state -> rejected
        ok, err = ce.edit("foo.txt", "version 1", "version 3")
        self.assertFalse(ok)
        self.assertIn("stale edit", err)

        # Re-read establishes current version
        v_fresh = ce.read("foo.txt")
        self.assertEqual(v_fresh, "version 2 (modified by background job)")

        # Reapplied edit against fresh version succeeds
        ok, _msg = ce.edit("foo.txt", "version 2 (modified by background job)", "version 3")
        self.assertTrue(ok)
        self.assertEqual(ce.file_state, "version 3")

    def test_idempotent_task_stop_terminal_state(self):
        """Stopping a completed task produces an idempotent response without a false blocker."""
        class TaskManager:
            def __init__(self):
                self.tasks = {"task_1": "COMPLETED"}

            def stop(self, task_id: str) -> dict:
                status = self.tasks.get(task_id)
                if status == "COMPLETED" or status == "STOPPED":
                    return {"ok": True, "status": status,
                            "message": "task is not running (already terminal)"}
                if status == "RUNNING":
                    self.tasks[task_id] = "STOPPED"
                    return {"ok": True, "status": "STOPPED", "message": "stopped"}
                return {"ok": False, "error": "task not found"}

        tm = TaskManager()
        res = tm.stop("task_1")
        # Harmless idempotent stop response must not be treated as fatal failure
        self.assertTrue(res["ok"])
        self.assertIn("already terminal", res["message"])

    def test_pipelined_validator_exit_status_preservation(self):
        """A pipe masks failure without pipefail; the runner preserves the exit status."""
        import shutil
        bash_bin = shutil.which("bash")
        if bash_bin:
            try:
                startup = subprocess.run(
                    [bash_bin, "-c", "exit 0"], capture_output=True, timeout=30,
                    stdin=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except (OSError, subprocess.TimeoutExpired):
                bash_bin = None
            else:
                if startup.returncode != 0:
                    bash_bin = None
        if bash_bin:
            cmd_piped = [bash_bin, "-c", "exit 2 | tail -n 5"]
            p_piped = subprocess.run(cmd_piped, capture_output=True)
            # Demonstrates that standard shell piping masks upstream non-zero exit code
            self.assertEqual(p_piped.returncode, 0)

            # Canonical direct execution preserves exit status:
            cmd_direct = [bash_bin, "-c", "exit 2"]
            p_direct = subprocess.run(cmd_direct, capture_output=True)
            self.assertEqual(p_direct.returncode, 2)
        else:
            # Fallback assertion if no bash is available
            p1 = subprocess.Popen(
                [sys.executable, "-c", "import sys; sys.exit(2)"], stdout=subprocess.PIPE
            )
            p2 = subprocess.Popen(
                [sys.executable, "-c", "import sys; sys.stdin.read(); sys.exit(0)"], stdin=p1.stdout
            )
            p1.stdout.close()
            p2.communicate()
            p1.wait()
            # Pipelined tail process returned 0, hiding upstream failure
            self.assertEqual(p2.returncode, 0)
            self.assertEqual(p1.returncode, 2)

    def test_installation_identity_beyond_version_string(self):
        """Matching version strings do not prove identity; require the path and digest."""
        inst_a = {
            "version": "8.1.0",
            "path": Path("V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN"),
            "fingerprint": "a1b2c3d4",
        }
        inst_b = {
            "version": "8.1.0",
            "path": Path("C:/Users/vac34/AppData/Roaming/ZAICODE/saipen"),
            "fingerprint": "e5f6g7h8",
        }

        # Identical version strings
        self.assertEqual(inst_a["version"], inst_b["version"])

        # Distinct instances verified by path and fingerprint
        self.assertNotEqual(inst_a["path"].resolve(), inst_b["path"].resolve())
        self.assertNotEqual(inst_a["fingerprint"], inst_b["fingerprint"])

    def test_authority_boundary_host_vs_protocol(self):
        """Host owns tool adapters and file guards; SAIPEN owns protocol evidence contracts."""
        # Host scope
        host_responsibilities = {
            "tool_schemas": True,
            "read_before_write_enforcement": True,
            "stale_write_rejection": True,
            "background_task_process_lifecycle": True,
        }
        # Protocol scope
        protocol_responsibilities = {
            "governing_contracts": ["EXEC-HUSH-01", "EXEC-RESPONSE-01", "CORE-001"],
            "preserve_raw_validator_exit_codes": True,
            "provenance_and_receipts": True,
            "forbid_inventing_rules": True,
        }
        self.assertTrue(host_responsibilities["read_before_write_enforcement"])
        self.assertIn("EXEC-HUSH-01", protocol_responsibilities["governing_contracts"])


if __name__ == "__main__":
    unittest.main()
