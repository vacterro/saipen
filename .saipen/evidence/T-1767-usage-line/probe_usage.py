"""T-1767 SCOUT: which top-level alternatives of the usage line are not commands.

    python -B probe_usage.py <tools-dir>

Splits the usage line `saipen help --json` prints into its top-level
alternatives (depth 0 of the outer parenthesis), then asks the dispatcher
about each distinct first word with `--dry-run --json` in a throwaway project
and prints the words it answers `unknown command` for.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

TOOLS = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(TOOLS))
os.environ["SAIPEN_USER_CONFIG_HOME"] = tempfile.mkdtemp(prefix="t1767-config-")

import saipen as CLI  # noqa: E402
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402


def call(*argv: str) -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        CLI.main(list(argv))
    raw = out.getvalue().strip()
    try:
        return json.loads(raw)
    except ValueError:
        return {"_raw": raw[:200]}


def alternatives(usage: str) -> list[str]:
    body = usage[usage.index("(") + 1 :]
    depth, cur, alts = 0, "", []
    for ch in body:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            if depth == 0:
                break
            depth -= 1
        if ch == "|" and depth == 0:
            alts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    alts.append(cur.strip())
    return alts


def project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="t1767-")) / "p"
    (root / ".saipen").mkdir(parents=True)
    (root / ".saipen" / "STATE.md").write_text(
        "---\nphase: DONE\ntask: none\nnext_action: saipen continue\nblocker: none\n"
        "transition_from: SHIP\nsaipen_version: 8\nschema_version: 3\nlast_event: 1\n"
        f"style_contract: {CURRENT_STYLE_CONTRACT}\nagent: tester\nmode: full\n"
        "updated: 2026-10-14T00:00:00Z\n---\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n## TODO\n## DONE\n- [x] T-000 fixture | verify: PASS -- fixture\n"
        "## BLOCKED\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "LOG.md").write_text(
        "# Log\n- 01.01.20 00:00 [E-001] [agent: tester] DEC: fixture\n", encoding="utf-8"
    )
    return root


def main() -> int:
    usage = call("help", "--json")["usage"]
    words = []
    for alt in alternatives(usage):
        word = alt.split()[0] if alt.split() else ""
        if word and word not in words:
            words.append(word)
    root = project()
    unknown = []
    for word in words:
        if word in {"init", "launch", "push", "ship"}:
            continue  # known top-level commands with effects beyond the fixture
        answer = call(word, "--dry-run", "--json", "--project-root", str(root))
        if f"unknown command: {word}" in str(answer.get("detail", "")):
            unknown.append(word)
    print(f"top-level words: {len(words)}")
    print("unknown: " + " ".join(unknown))
    shutil.rmtree(root.parent, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
