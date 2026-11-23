"""Apply the T-1687 change over exact inherited bytes.

    python apply_fix.py --subject <root> [--check]

Each anchor must match exactly once in the file's own line endings; otherwise
nothing is written anywhere. `--check` reports without writing.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--subject", required=True)
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
root = Path(args.subject).resolve()

BROKER_TESTS = "tools/test_host_authority_broker.py"
CORE_UNIT = "tools/saipen_engine/core_unit.py"
GATE_TESTS = "tools/test_core_unit_gate.py"

EDITS = {
    BROKER_TESTS: [
        (
            "from test_protocol_admission import World  # noqa: E402\n",
            "from test_protocol_admission import World  # noqa: E402\n"
            "\n"
            "#: What the shipped proof may say about THIS interpreter, which is never a\n"
            "#: host's hook (T-1687). Which one depends on where the suite was started\n"
            "#: and on what the operating system has done to its ancestry since: no host\n"
            "#: above it, a host above it with no hook between, or a parent whose pid a\n"
            "#: newer process took over while the suite ran. The third is the one a long\n"
            "#: family meets on a busy machine, and leaving it out made two tests red\n"
            "#: for one run in a way no rerun of the module reproduced.\n"
            "NOT_A_HOOK = (\n"
            "    HI.REASON_NOT_HOST_DESCENDANT,\n"
            "    HI.REASON_HOOK_NOT_FOUND,\n"
            "    HI.REASON_PARENT_REUSED,\n"
            ")\n",
        ),
        (
            "        # WHICH part of the hook invocation is missing depends on where the\n"
            "        # suite runs: outside any host, or inside one as an ordinary tool call.\n"
            "        # Both are refusals with a named reason, never a generic \"no\".\n"
            "        self.assertIn(\n"
            "            reply[\"identity\"][\"reason\"],\n"
            "            (HI.REASON_NOT_HOST_DESCENDANT, HI.REASON_HOOK_NOT_FOUND),\n"
            "        )\n",
            "        # WHICH part of the hook invocation is missing depends on where the\n"
            "        # suite runs (`NOT_A_HOOK`). Each is a refusal with a named reason,\n"
            "        # never a generic \"no\". A platform that reports no identity at all\n"
            "        # is a different wire code and is not accepted here.\n"
            "        self.assertIn(reply[\"identity\"][\"reason\"], NOT_A_HOOK)\n",
        ),
        (
            "        self.assertIn(\n"
            "            shape[\"reason\"],\n"
            "            (\n"
            "                HI.REASON_NOT_HOST_DESCENDANT,\n"
            "                HI.REASON_HOOK_NOT_FOUND,\n"
            "                HI.REASON_IDENTITY_UNAVAILABLE,\n"
            "            ),\n"
            "        )\n",
            "        # The same set the service answers with, plus the one answer only\n"
            "        # the caller's own look at itself can give: nothing observable.\n"
            "        self.assertIn(shape[\"reason\"], (*NOT_A_HOOK, HI.REASON_IDENTITY_UNAVAILABLE))\n",
        ),
    ],
    CORE_UNIT: [
        (
            "def _sha256_file(path: Path) -> str:\n",
            "#: One decisive line is cut to this many characters, and this many tests\n"
            "#: are quoted: the command's answer stays a summary, the file is the text.\n"
            "RED_REASON_CHARS = 300\n"
            "RED_REASONS_SHOWN = 20\n"
            "\n"
            "\n"
            "def decisive_lines(sections: dict) -> dict:\n"
            "    \"\"\"``{test id: the last line of its red section}`` (T-1687).\n"
            "\n"
            "    Defect class: a red family named its tests and nothing else, so the\n"
            "    seat that read the answer explained the red by hypothesis while the\n"
            "    traceback sat in a cache file the answer never mentioned. The last\n"
            "    line of a unittest section is the exception; quoting it beside the\n"
            "    names is what turns the hypothesis into a reading.\n"
            "    \"\"\"\n"
            "    shown: dict = {}\n"
            "    for test_id in sorted(sections or {})[:RED_REASONS_SHOWN]:\n"
            "        lines = [line for line in str(sections[test_id]).splitlines() if line.strip()]\n"
            "        shown[test_id] = lines[-1].strip()[:RED_REASON_CHARS] if lines else \"\"\n"
            "    return shown\n"
            "\n"
            "\n"
            "def _sha256_file(path: Path) -> str:\n",
        ),
        (
            "    reused = written is not None\n"
            "    leaked: list[str] = []\n",
            "    reused = written is not None\n"
            "    leaked: list[str] = []\n"
            "    red_sections_path: str | None = None\n"
            "    red_reasons: dict = {}\n",
        ),
        (
            "                keep_red_sections(root, written[\"path\"], run.get(\"sections\") or {})\n",
            "                red_sections_path = keep_red_sections(\n"
            "                    root, written[\"path\"], run.get(\"sections\") or {}\n"
            "                )\n"
            "                red_reasons = decisive_lines(run.get(\"sections\") or {})\n",
        ),
        (
            "            # T-1505: a sandbox a process still held; a later run sweeps it.\n"
            "            \"sandboxes_leaked\": leaked,\n",
            "            # T-1505: a sandbox a process still held; a later run sweeps it.\n"
            "            \"sandboxes_leaked\": leaked,\n"
            "            # T-1687: where this run's tracebacks are, and what each ends on.\n"
            "            \"red_sections\": red_sections_path,\n"
            "            \"red_reasons\": red_reasons,\n",
        ),
    ],
    GATE_TESTS: [
        (
            "        run.assert_called_once()\n"
            "        self.assertEqual(code, 1)\n"
            "        self.assertFalse(self.to(\"SHIP\").ok)\n",
            "        run.assert_called_once()\n"
            "        self.assertEqual(code, 1)\n"
            "        self.assertFalse(self.to(\"SHIP\").ok)\n"
            "\n"
            "    def test_a_red_run_names_its_tracebacks_and_what_each_ends_on(self):\n"
            "        # T-1687: names alone invite a hypothesis about the red.\n"
            "        self.reach_review()\n"
            "        core_unit.write_record(self.project, _run(INHERITED), self.fingerprint())\n"
            "        new_red = \"test_new.N.test_x\"\n"
            "        decisive = \"AssertionError: 'PARENT_REUSED' not found in ('HOOK_NOT_FOUND',)\"\n"
            "        section = (\n"
            "            f\"FAIL: test_x ({new_red})\\n\" + \"-\" * 70 + \"\\n\"\n"
            "            \"Traceback (most recent call last):\\n\"\n"
            "            '  File \"test_new.py\", line 3, in test_x\\n'\n"
            "            f\"{decisive}\\n\"\n"
            "        )\n"
            "        red_run = {**_run([*INHERITED, new_red]), \"sections\": {new_red: section}}\n"
            "        out = io.StringIO()\n"
            "        with mock.patch.object(core_unit, \"run_family\", return_value=red_run), \\\n"
            "                contextlib.redirect_stdout(out):\n"
            "            code = core_unit.main(\n"
            "                [\"evidence\", \"T-7\", \"--project-root\", str(self.project), \"--fresh\"]\n"
            "            )\n"
            "        self.assertEqual(code, 1)\n"
            "        payload = json.loads(out.getvalue())\n"
            "        self.assertEqual(payload[\"red_reasons\"], {new_red: decisive})\n"
            "        kept = json.loads((self.project / payload[\"red_sections\"]).read_text(\"utf-8\"))\n"
            "        self.assertEqual(kept[\"record\"], payload[\"record\"])\n"
            "        self.assertEqual(kept[\"sections\"], {new_red: section})\n"
            "\n"
            "    def test_a_green_or_reused_run_names_no_tracebacks(self):\n"
            "        self.reach_review()\n"
            "        core_unit.write_record(self.project, _run(INHERITED), self.fingerprint())\n"
            "        out = io.StringIO()\n"
            "        with mock.patch.object(core_unit, \"run_family\") as run, \\\n"
            "                contextlib.redirect_stdout(out):\n"
            "            code = core_unit.main([\"evidence\", \"T-7\", \"--project-root\", str(self.project)])\n"
            "        run.assert_not_called()\n"
            "        self.assertEqual(code, 0)\n"
            "        payload = json.loads(out.getvalue())\n"
            "        self.assertIsNone(payload[\"red_sections\"])\n"
            "        self.assertEqual(payload[\"red_reasons\"], {})\n"
            "\n"
            "    def test_the_quoted_lines_are_bounded(self):\n"
            "        sections = {\n"
            "            f\"test_m.C.test_{index:02d}\": \"FAIL: x\\n\" + \"e\" * 900 + \"\\n\\n\"\n"
            "            for index in range(core_unit.RED_REASONS_SHOWN + 5)\n"
            "        }\n"
            "        shown = core_unit.decisive_lines(sections)\n"
            "        self.assertEqual(len(shown), core_unit.RED_REASONS_SHOWN)\n"
            "        self.assertEqual(sorted(shown), sorted(sections)[: core_unit.RED_REASONS_SHOWN])\n"
            "        self.assertEqual(set(map(len, shown.values())), {core_unit.RED_REASON_CHARS})\n"
            "        self.assertEqual(core_unit.decisive_lines({}), {})\n"
            "        self.assertEqual(core_unit.decisive_lines({\"t\": \"\\n \\n\"}), {\"t\": \"\"})\n",
        ),
    ],
}

planned = {}
for relative, edits in EDITS.items():
    path = root / relative
    data = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    for old, new in edits:
        old_bytes = old.encode("utf-8").replace(b"\n", newline)
        new_bytes = new.encode("utf-8").replace(b"\n", newline)
        count = data.count(old_bytes)
        if count != 1:
            raise SystemExit(f"{relative}: anchor matched {count} times; nothing written")
        data = data.replace(old_bytes, new_bytes)
    planned[relative] = data

for relative, data in planned.items():
    if not args.check:
        (root / relative).write_bytes(data)
    print(relative, hashlib.sha256(data).hexdigest())
