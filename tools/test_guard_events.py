"""Host-event translation tests for the guard CLI (SRC-030 Part 6)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import guard_events  # noqa: E402


def _event(**overrides) -> dict:
    base = {
        "event": "before_tool",
        "host": "opencode",
        "cwd": str(Path.cwd()),
        "tool_name": "read",
        "tool_input": {"file_path": "src/app.py"},
    }
    base.update(overrides)
    return base


class LoadEventTests(unittest.TestCase):
    def test_a_valid_event_loads(self):
        event = guard_events.load_event(
            '{"event":"before_tool","host":"opencode","cwd":"x","tool_name":"bash",'
            '"tool_input":{"command":"saipen status"},"actor":"astra2"}'
        )
        self.assertEqual(event["tool_name"], "bash")
        self.assertEqual(event["actor"], "astra2")

    def test_oversized_events_are_refused(self):
        payload = '{"event":"x","host":"y","cwd":"z","tool_name":"t","pad":"'
        with self.assertRaises(guard_events.EventError):
            guard_events.load_event(payload + "a" * (guard_events.MAX_EVENT_BYTES + 10) + '"}')

    def test_invalid_json_is_refused(self):
        with self.assertRaises(guard_events.EventError):
            guard_events.load_event("{not json")

    def test_non_object_is_refused(self):
        with self.assertRaises(guard_events.EventError):
            guard_events.load_event("[1,2,3]")

    def test_missing_required_fields_are_refused(self):
        for field in ("event", "host", "cwd", "tool_name"):
            event = _event()
            event.pop(field)
            with self.assertRaises(guard_events.EventError, msg=field):
                guard_events.load_event(__import__("json").dumps(event))

    def test_non_dict_tool_input_is_refused(self):
        with self.assertRaises(guard_events.EventError):
            guard_events.load_event(
                __import__("json").dumps(_event(tool_input="rm -rf"))
            )


class MapEventTests(unittest.TestCase):
    def test_read_tools_map_to_read(self):
        mapped = guard_events.map_event(_event(tool_name="Read"))
        self.assertEqual(mapped["action"], "read")
        self.assertEqual(mapped["target_path"], "src/app.py")

    def test_a_namespaced_tool_is_never_resolved_to_its_last_segment(self):
        # T-1317 P0-8: a friendly suffix is not evidence of effect safety. A
        # namespaced/MCP/third-party tool is classified conservatively and
        # sent to the guard, never fast-pathed by its last name segment.
        for tool in (
            "mcp__server__edit", "mcp__server__read",
            "mcp__server__question", "plugin.read", "vendor__view",
        ):
            mapped = guard_events.map_event(_event(tool_name=tool))
            self.assertEqual(mapped["action"], "unknown", tool)

    def test_read_trust_is_never_granted_by_a_friendly_name(self):
        # Only a verified exact built-in read-only identity earns the read
        # class; `view`/`find`/`search`/`cat` style names do not.
        for tool in ("read", "glob", "grep", "list", "webfetch", "question"):
            self.assertEqual(guard_events.map_event(_event(tool_name=tool))["action"], "read", tool)
        for tool in ("view", "find", "search", "cat", "ls", "fetch"):
            self.assertNotEqual(
                guard_events.map_event(_event(tool_name=tool))["action"], "read", tool
            )

    def test_write_tools_map_to_write(self):
        for tool in ("write", "edit", "multiedit", "apply_patch"):
            mapped = guard_events.map_event(_event(tool_name=tool))
            self.assertEqual(mapped["action"], "write", tool)

    def test_delete_and_move_tools_map(self):
        self.assertEqual(guard_events.map_event(_event(tool_name="rm"))["action"], "delete")
        self.assertEqual(guard_events.map_event(_event(tool_name="mv"))["action"], "move")

    def test_shell_tools_map_to_shell(self):
        mapped = guard_events.map_event(_event(tool_name="bash", tool_input={"command": "ls -la"}))
        self.assertEqual(mapped["action"], "shell")
        self.assertIsNone(mapped["target_path"])

    def test_a_direct_saipen_command_is_a_canonical_operation(self):
        mapped = guard_events.map_event(
            _event(tool_name="bash", tool_input={"command": "saipen recover"})
        )
        self.assertEqual(mapped["action"], "saipen_op")
        self.assertEqual(mapped["saipen_verb"], "recover")

    def test_a_routed_saipen_command_is_not_the_canonical_class(self):
        # Exact-token recognition only: bash -lc, eval, subshells and paths
        # are ordinary SHELL effects. Never pattern inference over free text.
        for command in (
            "bash -lc 'saipen recover'",
            "eval saipen recover",
            "cd /tmp && saipen recover",
            "sudo saipen recover",
            "./saipen recover",
        ):
            mapped = guard_events.map_event(
                _event(tool_name="bash", tool_input={"command": command})
            )
            self.assertEqual(mapped["action"], "shell", command)
            self.assertIsNone(mapped["saipen_verb"])

    def test_a_compound_saipen_command_is_an_ordinary_shell_effect(self):
        # T-1317 P0-1: the canonical exemption is all-or-nothing. Only the
        # ENTIRE command line being one bounded SAIPEN invocation qualifies.
        for command in (
            "saipen recover && rm -f .saipen/STATE.md",
            "saipen status && echo hacked > x.txt",
            "saipen recover ; rm -f x",
            "saipen recover || rm -f x",
            "saipen recover | tee x",
            "saipen recover > x",
            "saipen recover >> x",
            "saipen recover < x",
            "saipen recover $(touch x)",
            "saipen recover `touch x`",
            "saipen recover (touch x)",
            "saipen recover & touch x",
            "saipen recover\necho hacked",
            "SAIPEN_AGENT=x saipen recover",
            "bash -lc 'saipen recover'",
            "saipen recover --json && rm -f x",
        ):
            mapped = guard_events.map_event(
                _event(tool_name="bash", tool_input={"command": command})
            )
            self.assertEqual(mapped["action"], "shell", command)
            self.assertIsNone(mapped["saipen_verb"], command)

    def test_the_bounded_canonical_grammar_still_classifies(self):
        for command, verb in (
            ("saipen recover", "recover"),
            ("saipen recover --json", "recover"),
            ("saipen status", "status"),
            ("  saipen   status  ", "status"),
            ("saipen guard --event-json - --json", "guard"),
        ):
            mapped = guard_events.map_event(
                _event(tool_name="bash", tool_input={"command": command})
            )
            self.assertEqual(mapped["action"], "saipen_op", command)
            self.assertEqual(mapped["saipen_verb"], verb, command)

    def test_a_multi_file_patch_carries_every_target(self):
        # T-1317 P0-5: apply_patch supplies patchText, never filePath.
        patch = (
            "*** Begin Patch\n"
            "*** Update File: src/app.py\n"
            "*** Move to: src/app2.py\n"
            "@@\n-a\n+b\n"
            "*** Add File: docs/new.md\n"
            "*** Delete File: src/old.py\n"
            "*** End Patch\n"
        )
        mapped = guard_events.map_event(
            _event(tool_name="apply_patch", tool_input={"patchText": patch})
        )
        self.assertEqual(mapped["action"], "write")
        self.assertEqual(
            mapped["target_paths"],
            ["src/app.py", "src/app2.py", "docs/new.md", "src/old.py"],
        )
        self.assertFalse(mapped["targets_unresolved"])

    def test_patch_text_without_a_bounded_target_marker_is_unresolved(self):
        for patch in ("*** Begin Patch\n*** End Patch\n", "--- a/x\n+++ b/x\n"):
            mapped = guard_events.map_event(
                _event(tool_name="apply_patch", tool_input={"patchText": patch})
            )
            self.assertEqual(mapped["target_paths"], [], patch)
            self.assertTrue(mapped["targets_unresolved"], patch)

    def test_a_move_carries_both_endpoints(self):
        mapped = guard_events.map_event(
            _event(
                tool_name="move",
                tool_input={"source_path": "src/a.py", "destination_path": ".saipen/STATE.md"},
            )
        )
        self.assertEqual(mapped["action"], "move")
        self.assertEqual(mapped["target_paths"], ["src/a.py", ".saipen/STATE.md"])
        self.assertFalse(mapped["targets_unresolved"])

    def test_a_move_or_write_without_a_trustworthy_target_set_is_unresolved(self):
        for tool, tool_input in (
            ("write", {}),
            ("apply_patch", {}),
            ("delete", {}),
            # A move naming only one endpoint cannot be classified from the
            # other side's shape: the destination could be protected state.
            ("move", {"source_path": "src/a.py"}),
        ):
            mapped = guard_events.map_event(_event(tool_name=tool, tool_input=tool_input))
            self.assertTrue(mapped["targets_unresolved"], tool)
        for tool, tool_input in (("write", {}), ("apply_patch", {}), ("delete", {}), ("move", {})):
            mapped = guard_events.map_event(_event(tool_name=tool, tool_input=tool_input))
            self.assertEqual(mapped["target_paths"], [], tool)
            self.assertIsNone(mapped["target_path"], tool)

    def test_an_unknown_tool_is_potentially_mutating(self):
        mapped = guard_events.map_event(
            _event(tool_name="mystery_tool", tool_input={"path": "src/app.py"})
        )
        self.assertEqual(mapped["action"], "unknown")
        self.assertEqual(mapped["target_path"], "src/app.py")

    def test_a_process_control_tool_is_an_unresolved_consequential_effect(self):
        # T-1317 Target A: reviewed Kiro translation. `control_bash_process`
        # (and its translated identity `process_control`) carries a process id
        # and arbitrary stdin -- never an inspectable command line or a
        # filesystem target -- so it maps onto an unresolved consequential
        # mutation and is never an admitted targetless unknown.
        for tool in ("control_bash_process", "process_control"):
            for tool_input in (
                {"processId": "123", "input": "rm -rf src"},
                {"processId": "123", "input": "rm -rf src", "path": "src/app.py"},
            ):
                mapped = guard_events.map_event(
                    _event(tool_name=tool, tool_input=tool_input)
                )
                self.assertEqual(mapped["action"], "unknown", tool)
                self.assertTrue(mapped["targets_unresolved"], tool)
                self.assertIsNone(mapped["saipen_verb"], tool)

    def test_fallback_path_keys(self):
        for key in ("path", "file", "notebook_path", "absolute_path"):
            mapped = guard_events.map_event(_event(tool_name="write", tool_input={key: "a.py"}))
            self.assertEqual(mapped["target_path"], "a.py", key)


if __name__ == "__main__":
    unittest.main()
