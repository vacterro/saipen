"""The real OpenCode hook must measure ordinary bound chat as well as Work."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import unittest

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from saipen_engine import chat_style as CS  # noqa: E402
from test_guard_hostile_matrix import active_project, fresh_project  # noqa: E402

LONG = "\n".join("Kontroll tehtud." for _ in range(CS.running_style_contract().line_budget + 4))


class HostTurnContext(unittest.TestCase):
    def classify(self, project, text, context, *extra):
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "response", "check", "--stdin",
             "--classify", "--project-root", str(project), "--turn-context", context,
             "--json", *extra],
            input=text, encoding="utf-8", capture_output=True, timeout=60,
        )
        return proc.returncode, json.loads(proc.stdout)

    def test_host_ordinary_context_keeps_active_project_chat_measured(self):
        project = active_project()
        rc, result = self.classify(project, "Kontroll tehtud.", "ordinary")
        self.assertEqual((rc, result.get("class")), (0, "ORDINARY_CHAT"), result)
        rc, result = self.classify(project, LONG, "ordinary")
        self.assertEqual((rc, result.get("class")), (1, "CHAT_STYLE_DRIFT"), result)
        self.assertEqual(result["layers"]["admission"], "NOT_CONSULTED")

    def test_host_operational_context_requires_surface_and_preserves_autonomy(self):
        project = active_project()
        rc, result = self.classify(project, "Kontroll tehtud.", "operational")
        self.assertEqual((rc, result.get("class")), (1, "INVALID_OPERATIONAL_PROSE"), result)
        rc, result = self.classify(project, "Kontroll tehtud.", "operational", "--auto-eligibility")
        self.assertEqual((rc, result.get("class")), (1, "AUTONOMOUS_HANDBACK"), result)

    def test_invalid_host_context_fails_without_touching_canonical_bytes(self):
        project = fresh_project()
        before = {p: p.read_bytes() for p in (project / ".saipen").rglob("*") if p.is_file()}
        rc, result = self.classify(project, "Kontroll tehtud.", "ordinary_typo")
        self.assertNotEqual(rc, 0, result)
        self.assertFalse(result["ok"])
        after = {p: p.read_bytes() for p in (project / ".saipen").rglob("*") if p.is_file()}
        self.assertEqual(after, before)


@unittest.skipUnless(shutil.which("node"), "Node runtime unavailable")
class OpenCodeChatHook(unittest.TestCase):
    def test_split_parts_share_message_budget_without_double_counting_reentry(self):
        project = fresh_project()
        script = """
import { pathToFileURL } from 'node:url';
const [pluginPath, project, longText] = process.argv.slice(1);
const factory = (await import(pathToFileURL(pluginPath).href)).default;
const hooks = await factory({worktree: project, directory: project});
await hooks['chat.message']({sessionID: 'split', messageID: 'user'},
  {message: {id: 'user'}, parts: [{type: 'text', text: 'Explain briefly'}]});
const lines = longText.split('\\n');
const half = Math.ceil(lines.length / 2);
const first = lines.slice(0, half).join('\\n');
const second = lines.slice(half).join('\\n');
const results = [];
for (const [messageID, partID, text] of [
  ['assistant', 'first', first],
  ['assistant', 'first', first],
  ['assistant', 'second', second],
  ['assistant', 'first', ''],
  ['assistant', 'second', second],
  ['next-assistant', 'first', 'Kontroll tehtud.'],
  ['', 'missing-message', 'Kontroll tehtud.'],
]) {
  try {
    await hooks['experimental.text.complete']({sessionID: 'split', messageID, partID}, {text});
    results.push({accepted: true});
  } catch (error) {
    results.push({accepted: false, error: String(error.message)});
  }
}
process.stdout.write(JSON.stringify(results));
"""
        env = {**os.environ, "SAIPEN_SKILL_ROOT": str(ROOT), "SAIPEN_PYTHON": sys.executable}
        proc = subprocess.run(
            [shutil.which("node") or "node", "--input-type=module", "-e", script,
             str(ROOT / "extensions/adapters/opencode/saipen-guard.js"), str(project), LONG],
            encoding="utf-8", capture_output=True, env=env, timeout=90, cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        rows = json.loads(proc.stdout)
        for index in (0, 1, 3, 4, 5):
            self.assertTrue(rows[index]["accepted"], rows[index])
        self.assertFalse(rows[2]["accepted"], rows[2])
        self.assertIn("CHAT_STYLE_DRIFT", rows[2]["error"])
        self.assertFalse(rows[6]["accepted"], rows[6])
        self.assertIn("EXEC_RESPONSE_INVALID", rows[6]["error"])

    def test_real_hook_rejects_essay_and_accepts_compact_chat(self):
        project = fresh_project()
        before = {p: p.read_bytes() for p in (project / ".saipen").rglob("*") if p.is_file()}
        script = """
import { pathToFileURL } from 'node:url';
const [pluginPath, project, longText] = process.argv.slice(1);
const factory = (await import(pathToFileURL(pluginPath).href)).default;
const hooks = await factory({worktree: project, directory: project});
const replies = [];
for (const [id, request, text] of [
  ['short', 'Explain the concept', 'Kontroll tehtud.'],
  ['long', 'Explain the concept', longText],
  ['incidental', 'Fix audit logging', longText],
  ['negated', 'Do not write a detailed report; explain briefly', longText],
  ['truncated', 'Please write a detailed report on ' + 'topic '.repeat(20000)
    + '; Do not write a detailed report, explain briefly', longText],
  ['explicit', 'Please write a detailed report', longText],
]) {
  await hooks['chat.message']({sessionID: 'chat-gate', messageID: id},
    {message: {id}, parts: [{type: 'text', text: request}]});
  try {
    await hooks['experimental.text.complete'](
      {sessionID: 'chat-gate', messageID: `assistant-${id}`, partID: `text-${id}`}, {text});
    replies.push({id, accepted: true});
  } catch (error) {
    replies.push({id, accepted: false, error: String(error.message)});
  }
}
process.stdout.write(JSON.stringify(replies));
"""
        env = {**os.environ, "SAIPEN_SKILL_ROOT": str(ROOT), "SAIPEN_PYTHON": sys.executable}
        proc = subprocess.run(
            [shutil.which("node") or "node", "--input-type=module", "-e", script,
             str(ROOT / "extensions/adapters/opencode/saipen-guard.js"), str(project), LONG],
            encoding="utf-8", capture_output=True, env=env, timeout=90, cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        rows = {row["id"]: row for row in json.loads(proc.stdout)}
        for good in ("short", "explicit"):
            self.assertTrue(rows[good]["accepted"], rows[good])
        for bad in ("long", "incidental", "negated", "truncated"):
            self.assertFalse(rows[bad]["accepted"], rows[bad])
            self.assertIn("CHAT_STYLE_DRIFT", rows[bad]["error"])
        after = {p: p.read_bytes() for p in (project / ".saipen").rglob("*") if p.is_file()}
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
