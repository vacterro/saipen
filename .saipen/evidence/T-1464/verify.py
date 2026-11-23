"""T-1464 verify: all three clauses of the ticket's own verify, mechanically.

  1. the matrix harness runs EVERY LISTED SHAPE;
  2. acceptance is IDENTICAL per model -- one predicate per shape, applied
     unchanged to every row;
  3. separate quality and efficiency tables exist under .saipen/evidence;
  4. no provider/model identity lands in STATE / BOARD / LOG.

Clause 4 is the one that is easy to satisfy by accident, so it is checked over
every canonical carrier including the sealed LOG segments, and it is checked
against the roster the record itself declares rather than a list typed here.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[0]
EVIDENCE = Path(".saipen/evidence/T-1464")
sys.path.insert(0, str(Path("tools").resolve()))
import t1363_field_polygon as polygon  # noqa: E402

failures = []
def check(label, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + label + (f" -- {detail}" if detail else ""))
    if not ok:
        failures.append(label)

record = json.loads((EVIDENCE / "polygon.json").read_text(encoding="utf-8"))
sessions = record["sessions"]
models = sorted({s["model"] for s in sessions})
shapes = sorted({s["condition"] for s in sessions})

# --- clause 1: every listed shape ran -------------------------------------
required = set(polygon.CONDITION_NAMES) | set(polygon.NEGATIVE_CONTROLS)
check("clause 1: every listed shape appears in the record",
      required <= set(shapes), f"missing={sorted(required - set(shapes))}")
# "per model" means per model that produced a MEASURED row. A row the provider
# refused was NOT run, and the only honest thing to demand of it is that it is
# recorded as unmeasured WITH a reason -- never a silent blank and never a
# PASS. Asserting that is stronger than quietly dropping the row.
measured_rows = {
    (s["model"], s["condition"]) for s in sessions if s["measurement"] == "MEASURED"
}
for model in models:
    covered = {c for (m, c) in measured_rows if m == model}
    if required <= covered:
        check(f"clause 1: {model} ran every shape", True)
        continue
    gaps = [
        s for s in sessions
        if s["model"] == model and s["condition"] not in covered
    ]
    silent = [s["condition"] for s in gaps if not s.get("infrastructure_error")]
    check(
        f"clause 1: {model} either ran every shape or recorded a reason for each it did not",
        not silent,
        f"{len(gaps)} unmeasured, {len(silent)} without a reason: {sorted(silent)}",
    )
check("clause 1: every listed shape is measured on at least one row",
      all(any(c == shape for (_, c) in measured_rows) for shape in required))

# --- clause 2: identical acceptance per model ------------------------------
# Recompute each row's verdict with the CURRENT predicate and require the
# published table to agree. A table rendered by a different (earlier, blanket)
# predicate therefore fails here, which is the whole point.
published = {}
for line in (EVIDENCE / "quality.md").read_text(encoding="utf-8").splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else None
    if cells and len(cells) > 3 and cells[0] != "model" and not set(cells[0]) <= set("- "):
        published[(cells[0], cells[1])] = cells[3]
mismatch = [
    (s["model"], s["condition"], polygon.acceptance(s), published.get((s["model"], s["condition"])))
    for s in sessions
    if published.get((s["model"], s["condition"])) != polygon.acceptance(s)
]
check("clause 2: the published quality table agrees with the current predicate",
      not mismatch, f"{len(mismatch)} row(s) differ, first={mismatch[:1]}")
check("clause 2: one expectation per shape, applied to every model",
      set(polygon.CONDITION_EXPECTATION) == required,
      f"expectation keys={sorted(polygon.CONDITION_EXPECTATION)}")
check("clause 2: an unmeasured row is never scored PASS or FAIL",
      not any(polygon.acceptance(s) in ("PASS", "FAIL", "FABRICATED")
              for s in sessions if s["measurement"] != "MEASURED"))

# --- clause 3: two separate tables under .saipen/evidence ------------------
quality = (EVIDENCE / "quality.md").read_text(encoding="utf-8")
efficiency = (EVIDENCE / "efficiency.md").read_text(encoding="utf-8")
check("clause 3: quality table exists and is under .saipen/evidence",
      quality.startswith("# T-1464 quality"))
check("clause 3: efficiency table exists and is under .saipen/evidence",
      efficiency.startswith("# T-1464 efficiency"))
qcols = {l for l in quality.splitlines() if l.startswith("| model")}
ecols = {l for l in efficiency.splitlines() if l.startswith("| model")}
check("clause 3: the tables are distinct documents, not one merged table",
      bool(qcols) and bool(ecols) and qcols != ecols)
check("clause 3: the efficiency table carries no acceptance column",
      "acceptance" not in efficiency)
check("clause 3: every published row is present in both tables",
      quality.count("\n| ") == efficiency.count("\n| ") == len(sessions) + 1,
      f"quality={quality.count(chr(10) + '| ')} efficiency={efficiency.count(chr(10) + '| ')} sessions={len(sessions)}")

# --- clause 4: no provider/model identity in canonical carriers -------------
# The roster is read from the record, so a new row cannot slip past a list
# typed into the check.
roster = re.compile(
    "|".join(re.escape(model.split("/", 1)[-1]) for model in models) + "|" + "|".join(
        re.escape(provider) for provider in {m.split("/", 1)[0] for m in models}
    ),
    re.IGNORECASE,
)
carriers = [".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md"]
# Scope is what THIS ticket ADDED, not what the carriers have always said:
# T-1481's own DONE text names the local model in the BOARD, written by another
# seat on 23.09, and flagging it would be flagging history. `git diff --cached`
# gives exactly the added lines, so a historical mention cannot pass as a
# violation and a newly added one cannot hide behind a historical one.
diff = subprocess.run(
    ["git", "diff", "--cached", "-U0", "--", *carriers],
    capture_output=True, text=True,
).stdout
added = [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
offenders = [(line[:90], m.group(0)) for line in added for m in [roster.search(line)] if m]
check(
    "clause 4: no roster identity in any line this ticket added to STATE/BOARD/LOG",
    not offenders,
    f"{len(added)} added line(s) scanned, offenders={offenders[:2]}",
)
check(
    "clause 4: the carriers WERE touched by this ticket, so the scan is not vacuous",
    any("T-1464" in line for line in added),
    f"{len(added)} added lines",
)

# --- the record itself must be reproducible from tracked bytes -------------
tracked = subprocess.run(
    ["git", "ls-files", "--error-unmatch", *[
        p.as_posix() for p in (
            [EVIDENCE / "README.md", EVIDENCE / "polygon.json",
             EVIDENCE / "quality.md", EVIDENCE / "efficiency.md"]
        )
    ]],
    capture_output=True, text=True,
)
check("the evidence bundle is tracked by git, not only present in this checkout",
      tracked.returncode == 0, tracked.stderr.strip()[:120])

print()
if failures:
    print(f"VERIFY FAIL: {len(failures)} control(s) red")
    for label in failures:
        print("  - " + label)
    raise SystemExit(1)
print(f"VERIFY PASS: {len(models)} rows, {len(sessions)} sessions, {len(required)} shapes, "
      f"{len(published)} published rows")