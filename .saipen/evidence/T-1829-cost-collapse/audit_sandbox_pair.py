"""Bind preserved measurements without rerunning copies or fabricating acceptance."""
import json
from pathlib import Path

directory = Path(__file__).resolve().parent
win = json.loads((directory / "sandbox-paired-corrected-20261020.json").read_text(encoding="utf-8"))
linux = json.loads((directory / "sandbox-paired-corrected-20261020-linux.json").read_text(encoding="utf-8"))
order = json.loads((directory / "sandbox-portable-inventory-20261020.json").read_text(encoding="utf-8"))
keys = ("files_or_links", "bytes", "sha256")


def same(left, right):
    return all(left[key] == right[key] for key in keys)


assert same(order["legacy_windows_inventory"], win["input_inventory"])
assert order["same_frozen_windows_bytes_proved"] is True
assert same(order["portable_posix_parts_inventory"], linux["input_inventory"])
assert win["private_clone_exact"] is True
assert same(win["input_inventory"], win["private_worker_inventory"])
assert all(row["removed"] for row in win["cleanup"] + linux["cleanup"])
assert win["executed_suite"] is False and linux["executed_suite"] is False
report = {"scope": "preserved exact byte inventory and copy observations only",
          "executed_suite": False, "same_frozen_windows_linux_bytes_proved": True,
          "portable_inventory": order["portable_posix_parts_inventory"],
          "windows_private_clone_exact": True, "all_owned_roots_removed": True,
          "windows_stages": win["stages"], "linux_stages": linux["stages"],
          "linux_measurement_completed": False,
          "linux_limitation": "Legacy host-dependent inventory order refused before Linux worker clone/discovery. Independently computed portable digest proves the completed first copy's bytes; it does not turn the unfinished experiment into PASS.",
          "source_copy_errors": [win.get("experiment_error"), linux.get("experiment_error")],
          "evidence": ["sandbox-paired-corrected-20261020.json",
                       "sandbox-paired-corrected-20261020-linux.json",
                       "sandbox-portable-inventory-20261020.json"]}
(directory / "sandbox-pair-audit-20261020.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: report[key] for key in ("scope", "same_frozen_windows_linux_bytes_proved",
      "all_owned_roots_removed", "linux_measurement_completed")}))
