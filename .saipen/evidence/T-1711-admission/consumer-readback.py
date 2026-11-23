"""Read only the explicitly matched consumer's canonical incident surfaces."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
output = HERE / "consumer-readback.json"
if output.exists():
    raise SystemExit("Consumer readback evidence already exists")
root = Path("V:/___VAC/__K/__CODE/_HTML/_SAI_WEBSITE")
paths = {name: root / ".saipen" / name for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")}
before = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
state = paths["STATE.md"].read_text(encoding="utf-8-sig")
board = paths["BOARD.md"].read_text(encoding="utf-8-sig")
log = paths["LOG.md"].read_text(encoding="utf-8-sig")
result = {
    "matched_root": str(root), "root_source": "exact SAI account-manager workdir match",
    "state": state,
    "T31_board_rows": [line for line in board.splitlines() if " T-31 " in line],
    "incident_events": [line for line in log.splitlines() if any(
        f"[E-{number}]" in line for number in range(345, 355))],
    "latest_log_rows": log.splitlines()[-16:],
    "identity": paths["IDENTITY.md"].read_text(encoding="utf-8-sig"),
    "before": before,
    "limit": "Current four-file readback only; no product-code edits, CLI continuation or claim mutation",
}
result["after"] = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
result["canonical_bytes_unchanged"] = result["before"] == result["after"]
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"state": state, "T31": result["T31_board_rows"],
                  "incident_events": result["incident_events"],
                  "unchanged": result["canonical_bytes_unchanged"]}, indent=2))
