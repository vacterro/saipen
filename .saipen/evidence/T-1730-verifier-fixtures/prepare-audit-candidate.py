"""Refactor only the owned isolated audit candidate's fresh fixture setup."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
target = ROOT / ".saipen/evidence/T-1726-closed-contracts/cache-candidate/tools/audit_checks.py"
text = target.read_text(encoding="utf-8")
phase_begin = text.index("    # A protocol rename is tested on a fresh native project")
phase_end = text.index("    milestone_root =", phase_begin)
block = text[phase_begin:phase_end]
helper = "def fresh_protocol_fixture(tree: Path, destination: Path, label: str) -> str | None:\n"
helper += '    """Initialize a real protocol fixture without borrowing unrelated closure proof."""\n'
helper += block.replace('history = destination / "phase-rename-history"',
                        'history = destination / (label + "-history")')
helper += "    return None\n\n\n"
text = text[:phase_begin] + '''    fresh_error = fresh_protocol_fixture(tree, destination, "phase-rename")
    if fresh_error:
        return fresh_error
''' + text[phase_end:]
begin = text.index("def phase_rename_probe(")
text = text[:begin] + helper + text[begin:]
begin = text.index("def tag_query_probe(")
end = text.index("\ndef ", begin + 1)
section = text[begin:end]
section = section.replace("    pristine = context.pristine\n", '''    pristine = context.sandbox / "runtime-query"
    shutil.copytree(context.pristine, pristine)
    fresh_error = fresh_protocol_fixture(pristine, context.sandbox, "runtime-query")
    if fresh_error:
        return fresh_error
''', 1)
text = text[:begin] + section + text[end:]
begin = text.index("def phase_rename_probe(")
end = text.index("\ndef ", begin + 1)
section = text[begin:end].replace("SCOUTX", "TRACE").replace("scoutx", "trace")
text = text[:begin] + section + text[end:]
text = text.replace('replace("That order is cheapest-first", "That order is a suggestion")',
                    'replace("cheapest-first", "arbitrary order")')
text = text.replace('replace("ends the PASS claim for this pass", "is worth noting")',
                    'replace("this pass cannot claim PASS", "this pass may claim PASS later")')
target.write_text(text, encoding="utf-8")

validator = target.with_name("validate.py")
text = validator.read_text(encoding="utf-8")
text = text.replace('"That order is cheapest-first",', '"cheapest-first",')
text = text.replace('"ends the PASS claim for this pass",', '"this pass cannot claim PASS",')
validator.write_text(text, encoding="utf-8")
print("prepared isolated fresh protocol fixtures and current borrowed-rule anchors")
