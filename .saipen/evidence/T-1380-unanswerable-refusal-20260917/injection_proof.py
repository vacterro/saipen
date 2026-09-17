"""Read-only proof that every installed agent home runs the CURRENT source generation.

Prints the facts SRC-055 section 4 asks for, from `autoinject.distribution_report`
(the one owner of the verdict), never from a stamp or a log line:

    installed homes, stale, unknown, surface_unknown,
    expected (source) generation vs each home's runtime generation.

Exit 0 only when every installed home is current: stale = 0, unknown = 0,
surface_unknown = 0, and each runtime generation equals the source generation.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

import autoinject  # noqa: E402


def main() -> int:
    report = autoinject.distribution_report()
    expected = report["expected_generation"]
    print(f"source head         : {report['source_head']}")
    print(f"source generation   : {expected}")
    print(
        f"installed={report['installed']} stale={report['stale']} "
        f"unknown={report['unknown']} surface_unknown={report['surface_unknown']}"
    )
    mismatched = 0
    for home in report["homes"]:
        same = home["runtime_generation"] == expected
        mismatched += 0 if same else 1
        print(
            f"  {home['home']:<11} runtime={home['runtime_generation']} "
            f"current={home['generation_current']} stale={home['stale']} "
            f"launcher_problems={len(home['launcher_problems'])} "
            f"surface_problems={len(home['surface_problems'])}"
        )
    ok = (
        report["installed"] > 0
        and report["stale"] == 0
        and report["unknown"] == 0
        and report["surface_unknown"] == 0
        and mismatched == 0
    )
    print(f"verdict             : {'CURRENT' if ok else 'NOT CURRENT'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
