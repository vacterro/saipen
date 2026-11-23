"""Bind the preserved ingress through canonical intake APIs, not file edits.

The final acceptance section is copied verbatim from the actual captured
mission. Supplemental behavioral pressures remain in the mission artifact.
No provenance, operator capability, priority, or execution intent is changed.
"""

from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import intake


def require(result):
    print(json.dumps(result, ensure_ascii=False))
    if not result.get("ok"):
        raise SystemExit(1)


require(intake.link_work_to(ROOT, "SRC-165", "T-1600"))
body = intake.read_body(ROOT, "SRC-165")
require({"ok": body.get("ok"), "operation": "read SRC-165"})
section = body["body"].split("PART R — FINAL ACCEPTANCE", 1)[1].split("PART S —", 1)[0]
clauses = re.findall(r"(?m)^(\d+)\.\s+(.*?)(?=\n\d+\.\s|\n[A-Z][A-Z ]+\n|\n={5,}|\Z)", section, re.S)
if [int(number) for number, _ in clauses] != list(range(1, 37)):
    raise SystemExit("acceptance extraction must recover all 36 numbered clauses")
require(intake.add_requirements(ROOT, "SRC-165", [
    {"rid": f"R{int(number):03d}", "text": text.strip(), "class": "requirement"}
    for number, text in clauses
]))

# The original CLARIFICATION projection classified its three lead-in sentences
# as context. Preserve that immutable interpretation revision; add the actual
# explicit acceptance and complete repeated-turn sequence as actionable clauses.
steering = intake.read_body(ROOT, "SRC-166")
require({"ok": steering.get("ok"), "operation": "read SRC-166"})
turns = re.search(r"The regression suite must include repeated-turn testing:\s*(.*?)\nNo credit for:", steering["body"], re.S)
acceptance = re.search(r"Acceptance requires the invalid response.*", steering["body"], re.S)
if not turns or not acceptance:
    raise SystemExit("actual steering acceptance was not found")
require(intake.add_requirements(ROOT, "SRC-166", [
    {"rid": "R004", "text": "The regression suite must include repeated-turn testing:\n" + turns[1].strip(), "class": "requirement"},
    {"rid": "R005", "text": acceptance[0].strip(), "class": "requirement"},
]))
