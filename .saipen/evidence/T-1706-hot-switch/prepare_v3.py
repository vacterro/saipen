"""Prepare an additional repeated prevention control without editing the old one."""

from pathlib import Path

here = Path(__file__).resolve().parent
target = here / "regression_control_v3.py"
assert not target.exists()
source = (here / "regression_control.py").read_text(encoding="utf-8")
source = source.replace("regression-control-v2.json", "regression-control-v3.json")
source = source.replace("regression-v2-", "regression-v3-")
start = source.index("        for kind, repeat in ")
end = source.index("            for name, backup in SUBJECTS.items():", start)
source = source[:start] + '''        for kind, repeat in (("good", 1), ("bad", 1), ("restored", 1),
                             ("bad", 2), ("restored", 2), ("bad", 3), ("restored", 3)):
''' + source[end:]
source = source.replace("len(runs) == 5 and len(bad) == 2", "len(runs) == 7 and len(bad) == 3")
source = source.replace('bad[0]["failures"] == bad[1]["failures"]',
                        'all(run["failures"] == bad[0]["failures"] for run in bad)')
source = source.replace("len(bad) == 2 and", "len(bad) == 3 and")
assert "regression-control-v2.json" not in source
compile(source, str(target), "exec")
target.write_text(source, encoding="utf-8")
print("Prepared seven fixed-oracle runs: current and three old/restored pairs")
