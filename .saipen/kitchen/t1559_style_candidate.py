"""Prepare a budget-neutral restoration of STYLE's two canonical contracts."""
from __future__ import annotations

import hashlib
import json
import re
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.chat_style import compile_style_contract
from saipen_engine.state import style_contract_token

source = ROOT / "saipen/STYLE.md"
raw = source.read_bytes()
text = raw.decode("utf-8").replace("\r\n", "\n")
old_language = "Precedence: explicit current user prose (EE/EN/RU)"
new_language = "Reply-language precedence: explicit current user prose (Estonian/English/Russian)"
old_voice = '''ACTIVE EVERY RESPONSE, first to last. No revert after many turns. No drift back
to corporate prose or polite consultant explanations. Still active when unsure,
mid-debug, or answering Q&A. Off ONLY on explicit "stop caveman" / "normal mode".'''
new_voice = '''Voice persistence: caveman-дед applies to every response until explicit "stop caveman" or "normal mode".
ACTIVE EVERY RESPONSE, first to last. No revert during long sessions, debugging or Q&A.'''
if text.count(old_language) != 1 or text.count(old_voice) != 1:
    raise RuntimeError("canonical STYLE anchors changed")
updated = text.replace(old_language, new_language, 1).replace(old_voice, new_voice, 1)
updated = re.sub(r"ded-[0-9a-f]{8}", style_contract_token(updated), updated, count=1)
before, after = compile_style_contract(text), compile_style_contract(updated)
for field in ("reply_language", "reply_language_setting", "line_budget", "openers", "closers", "apologies"):
    if getattr(before, field) != getattr(after, field):
        raise RuntimeError(f"measurable style drift: {field}")
language = ("Reply-language precedence: explicit current user prose "
            "(Estonian/English/Russian) > clearly Russian primary repository for "
            "bare/ambiguous input > Estonian default; another detected language uses English.")
voice = ('Voice persistence: caveman-дед applies to every response until explicit '
         '"stop caveman" or "normal mode".')
assert language in updated and voice in updated
assert language not in text and voice not in text
draft = ROOT / ".saipen/evidence/T-1559-style-candidate"
draft.mkdir(parents=True, exist_ok=True)
(draft / "STYLE.md").write_text(updated, encoding="utf-8", newline="")
report = {"path": "saipen/STYLE.md", "before_sha256": hashlib.sha256(raw).hexdigest(),
          "after_sha256": hashlib.sha256(updated.encode("utf-8")).hexdigest(),
          "normalized_byte_delta": len(updated.encode("utf-8")) - len(text.encode("utf-8")),
          "style_marker_before": before.source_token, "style_marker_candidate": after.source_token,
          "measurable_contract_unchanged": True,
          "required_before_integration": "same-oracle validator and mutation controls; canonical marker rederivation for owned live STATE"}
(draft / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report))

if "--live-check" in sys.argv:
    from test_validator_layout_parity import _build_home, _neutral_project

    def run_validator(home, project, label):
        finding_file = home.parent / (label + "-findings.json")
        run = subprocess.run([sys.executable, "-B", str(home / "tools/validate.py"),
                              "--gate", "core", "--project-root", str(project),
                              "--findings-json", str(finding_file), "--no-receipt"],
                             cwd=home, capture_output=True, text=True, encoding="utf-8", timeout=180,
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        findings = json.loads(finding_file.read_text(encoding="utf-8"))
        details = [item.get("detail", "") for item in findings["problems"] + findings["warnings"]]
        matches = [line for line in details
                   if "cross-doc drift" in line and
                   any(name in line for name in ("STYLE.md", "SKILL.md")) and
                   any(tag in line for tag in ("[reply-language]", "[chat-voice]"))]
        return {"label": label, "target_findings": matches, "overall_exit": run.returncode,
                "scope": "STYLE/SKILL reply-language and chat-voice findings only"}

    with tempfile.TemporaryDirectory(prefix="saipen-style-owner-") as directory:
        home = Path(directory) / "home"
        _build_home(home, flatten=False)
        project = _neutral_project(Path(directory) / "project")
        records = [run_validator(home, project, "original")]
        (home / "saipen/STYLE.md").write_text(updated, encoding="utf-8", newline="")
        state = project / ".saipen/STATE.md"
        state.write_text(state.read_text(encoding="utf-8").replace(before.source_token, after.source_token),
                         encoding="utf-8", newline="")
        records.append(run_validator(home, project, "candidate"))
        (home / "saipen/STYLE.md").write_text(updated.replace("Voice persistence:", "Voice remains:", 1),
                                             encoding="utf-8", newline="")
        records.append(run_validator(home, project, "voice-red"))
        (home / "saipen/STYLE.md").write_text(updated, encoding="utf-8", newline="")
        skill = home / "saipen/SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8").replace("Reply-language precedence:",
                                                                  "Reply language precedence:", 1),
                         encoding="utf-8", newline="")
        records.append(run_validator(home, project, "language-red"))
    assert len(records[0]["target_findings"]) == 2, records
    assert not records[1]["target_findings"], records
    assert any("[chat-voice]" in line and "STYLE.md" in line for line in records[2]["target_findings"]), records
    assert any("[reply-language]" in line and "SKILL.md" in line for line in records[3]["target_findings"]), records
    (draft / "validator-controls.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"same_oracle": "PASS", "controls": records}))
