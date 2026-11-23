"""Read-only: resolve two real closed-archive findings on their real boards."""
import json
import sys
from pathlib import Path

HOME = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import board, finding_route as R


def probe(root, label, finding):
    parsed = board.parse_board((Path(root) / ".saipen/BOARD.md").read_text(encoding="utf-8-sig"))
    result = R.resolve(Path(root), finding, parsed["tickets"])
    print(f"== {label}")
    print(json.dumps({**result, "route": R.route_command(result)}, indent=1, ensure_ascii=False))
    print()


probe(
    "V:/___VAC/__K/__CODE/_PY/_SMART_VAC_MEDIA_COMPRESSOR",
    "target SMART_VAC_MEDIA_COMPRESSOR: SRC-003 closed archive invalid",
    {"rule_id": "source_receipt_closed_archive_invalid", "subject_kind": "source",
     "subject_id": "SRC-003"},
)
probe(
    ".",
    "this project: SRC-276 closed archive invalid",
    {"rule_id": "source_receipt_closed_archive_invalid", "subject_kind": "source",
     "subject_id": "SRC-276"},
)
