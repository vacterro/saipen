"""T-1868/SRC-297: the ZAICODE hook must read the event ZAICODE actually sends.

MEASURED defect. ZCODE's `UserPromptSubmit` hook input carries `prompt`,
`hook_event_name`, `session_id`, `cwd` and `turnId`
(`createCompatibleHookStdin`, apps/zcode-cli/packages/core/src/hooks/
configured-runner-input.ts). It never carries `host_ingress`. The shipped hook
read only `event["host_ingress"]` and returned `{"ingress_id": null}` for
everything else, so on the one host that actually delivers operator prompts the
hook answered green, minted nothing, and the engine recorded the operator's own
words as `witness: model_supplied`. A bounded goal run then sat on
`hard_wait` demanding reauthorization the operator had already given.

These cases pin the transport contract, not the broker: what the hook does with
an event is this artifact's whole job, and it must not depend on a key the host
does not send.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.pending_ingress import ingress_digest  # noqa: E402

HOOK = REPO / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"

#: The bootstrap the operator's config.json installs, verbatim. Running the
#: hook any other way would test a shape the host never uses.
BOOTSTRAP = (
    "import os,runpy,sys;a=sys.argv[1];sys.argv=sys.argv[1:];"
    "os.path.isfile(a) and runpy.run_path(a,run_name=__name__)"
)


def project_root():
    """A throwaway SAIPEN project for one test.

    The hook writes the admitted envelope into `<root>/.saipen/cache/ingress/`,
    and an unconsumed `start` record is a routing input. Running these cases
    against this repository would leave probe ingresses behind that a later
    `continue` could act on -- so the subject is a project that exists for the
    test and is deleted with it.
    """
    import tempfile

    holder = tempfile.TemporaryDirectory(prefix="t1868-project-")
    root = Path(holder.name)
    (root / ".saipen").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "STATE.md").write_text("# STATE\n", encoding="utf-8")
    return holder, root


def run_hook(payload: dict, root: Path = REPO) -> dict:
    """Invoke the hook exactly as ZAICODE's config.json invokes it."""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            BOOTSTRAP,
            str(HOOK),
            "--host",
            "zaicode",
            "--saipen-root",
            str(root),
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    for line in reversed(proc.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"hook printed no JSON frame: {proc.stdout!r} {proc.stderr!r}")


def host_event(text: str, *, root: Path = REPO, session: str = "sess-t1868",
               turn: str = "turn-t1868") -> dict:
    """One ZCODE UserPromptSubmit event, in the host's own field names."""
    return {
        "hookEventName": "UserPromptSubmit",
        "hook_event_name": "UserPromptSubmit",
        "prompt": text,
        "cwd": str(root),
        "sessionId": session,
        "session_id": session,
        "turnId": turn,
        "timestamp": "2026-10-23T00:00:00Z",
    }


class HostPayloadContract(unittest.TestCase):
    """The event ZAICODE sends is enough to deliver an operator ingress."""

    def setUp(self):
        holder, self.root = project_root()
        self.addCleanup(holder.cleanup)

    def test_a_real_host_event_admits_an_ingress(self):
        reply = run_hook(host_event("reauthorize", root=self.root, session="sess-a"))
        self.assertTrue(reply.get("ok"), reply)
        self.assertIsNotNone(reply.get("ingress_id"), reply)
        self.assertEqual(reply.get("destination_op"), "start")
        self.assertTrue(reply["ingress_id"].startswith("ing-"))

    def test_the_admitted_envelope_carries_the_engine_digest_of_the_prompt(self):
        # The admission path recomputes the digest from the text and refuses a
        # mismatch, so a hook that invented its own format would be refused on
        # every event and look exactly like the defect this fixes.
        from saipen_engine import operator_task

        text = "reauthorize bounded run"
        reply = run_hook(host_event(text, root=self.root, session="sess-b", turn="turn-b"))
        self.assertTrue(reply.get("ok"), reply)
        record = None
        for item in operator_task.active_host_ingress(
            self.root, session_id="sess-b", include_consumed=True
        ):
            if item.get("ingress_id") == reply["ingress_id"]:
                record = item
                break
        self.assertIsNotNone(record, reply)
        self.assertEqual(record["request_digest"], ingress_digest(text))
        self.assertEqual(record["request_text"], text)
        self.assertEqual(record["session_id"], "sess-b")

    def test_a_continuation_prompt_stays_a_continuation(self):
        reply = run_hook(host_event("cc", root=self.root, session="sess-c", turn="turn-c"))
        self.assertEqual(reply.get("destination_op"), "continue", reply)

    def test_an_event_with_no_prompt_delivers_nothing(self):
        # Not every hook event is a prompt. A Stop event must not be recorded
        # as operator ingress, and must not fail either.
        event = host_event("ignored", root=self.root, session="sess-d")
        event["hook_event_name"] = event["hookEventName"] = "Stop"
        event.pop("prompt")
        reply = run_hook(event)
        self.assertTrue(reply.get("ok"), reply)
        self.assertIsNone(reply.get("ingress_id"), reply)

    def test_an_empty_prompt_delivers_nothing(self):
        reply = run_hook(host_event("   ", root=self.root, session="sess-e", turn="turn-e"))
        self.assertTrue(reply.get("ok"), reply)
        self.assertIsNone(reply.get("ingress_id"), reply)

    def test_a_declared_envelope_still_wins(self):
        # The agent-to-agent path already speaks `host_ingress`; honouring it
        # first keeps that contract intact rather than re-deriving it.
        event = host_event("the prompt field", root=self.root, session="sess-f")
        event["host_ingress"] = {
            "request_text": "the declared text",
            "request_digest": ingress_digest("the declared text"),
            "session_id": "sess-f",
            "message_id": "m-declared",
        }
        reply = run_hook(event)
        self.assertTrue(reply.get("ok"), reply)
        self.assertIsNotNone(reply.get("ingress_id"), reply)

    def test_the_pre_fix_hook_fails_this_suite(self):
        """Red control: run the PRE-FIX reader against the same host event.

        The defect was a reader, so the honest control restores that reader and
        runs it -- a claim that "the old code was broken" proves nothing. The
        pre-fix body is the exact early return that shipped; everything above it
        (argument parsing, project binding) is unchanged, so the control isolates
        the one decision under test.
        """
        source = HOOK.read_text(encoding="utf-8")
        marker = "    ingress = _declared_ingress(event)\n"
        self.assertIn(marker, source)
        pre_fix = (
            '    ingress = event.get("host_ingress")\n'
            "    if not isinstance(ingress, dict):\n"
            '        print(json.dumps({"ok": True, "ingress_id": None, "sealed": False}))\n'
            "        return 0\n"
        )
        patched = source.replace(marker, pre_fix)
        self.assertNotEqual(patched, source)

        import tempfile

        with tempfile.TemporaryDirectory(prefix="t1868-red-") as tmp:
            red = Path(tmp) / "saipen-guard-pre-fix.py"
            red.write_text(patched, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-c", BOOTSTRAP, str(red),
                 "--host", "zaicode", "--saipen-root", str(self.root)],
                input=json.dumps(host_event("reauthorize", root=self.root, session="sess-red")),
                capture_output=True, text=True, timeout=180,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        reply = json.loads(proc.stdout.strip().splitlines()[-1])
        # The pre-fix hook drops the operator's prompt: green, and empty.
        self.assertTrue(reply.get("ok"), reply)
        self.assertIsNone(reply.get("ingress_id"), reply)
        # And the case above, which requires an ingress, therefore fails on it.
        with self.assertRaises(AssertionError):
            self.assertIsNotNone(reply.get("ingress_id"), reply)


class HookSourceContract(unittest.TestCase):
    """The hook's own source keeps the host key it must read."""

    def test_the_hook_reads_the_host_prompt_and_computes_the_engine_digest(self):
        source = HOOK.read_text(encoding="utf-8")
        self.assertIn('event.get("prompt")', source)
        self.assertIn("ingress_digest", source)
        # The old shape returned before looking at any host field.
        self.assertNotIn('ingress = event.get("host_ingress")\n    if not isinstance(ingress, dict):', source)


if __name__ == "__main__":
    unittest.main()
