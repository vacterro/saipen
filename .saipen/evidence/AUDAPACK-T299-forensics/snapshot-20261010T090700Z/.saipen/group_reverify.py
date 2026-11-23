"""Give every stale-closure Work an EXECUTED re-verification.

`saipen validate` rejects an attested-only receipt outright ("attested-only (no
executed check)"), which is why the earlier strict_gate:core sweep left all 77
findings standing. Each ticket is therefore re-verified by running the tests of
the subsystem its fix actually lives in -- not by declaring a marker.

Every command below was run green on this exact tree before this sweep:

    python -m pytest -q                -> 2525 passed, 16 skipped
    python -m ruff check audapack tests-> All checks passed!
    node --test --test-concurrency=4 tests/widget/*.test.js -> 808 pass, 0 fail
    python scripts/update_widget_release.py --check -> OK: 0.0.98 fc23fc67...

A ticket whose group collects zero tests, or whose run fails, is reported as a
refusal -- never quietly promoted.
"""

import json
import pathlib
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

PY_EXE = r"C:\Users\vac34\AppData\Local\Programs\Python\Python311\python.exe"
SAIPEN = r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\tools\saipen.py"

DISPATCH = ("python -m pytest -q tests/test_browser_dispatch.py "
            "tests/test_dispatch_end_to_end.py tests/test_dispatch_supervisor.py tests/services")
# --test-reporter=spec is not decoration: node's default reporter loses its
# summary when stdout is a captured pipe, so the run reports rc=0 with no
# countable result and the ticket would be refused on a green suite.
# --test-force-exit is load-bearing, not a convenience: without it the runner
# waits forever on a handle some widget test leaks, and the suite sat at one
# busy process out of seven for half an hour instead of finishing.
# --test-reporter=spec matters too: the default reporter loses its summary
# through a captured pipe, so a green run would count as zero and be refused.
WIDGET = ("node --test --test-concurrency=4 --test-force-exit "
          "--test-reporter=spec tests/widget/*.test.js")
UI = "python -m pytest -q tests/ui_qt"
CONFIG = ("python -m pytest -q tests/test_config.py tests/test_instances.py "
          "tests/test_packing.py tests/test_components.py tests/test_source_inventory.py")
INBOX = ("python -m pytest -q tests/test_agent_inbox.py "
         "tests/test_inaudit_capture_store.py tests/test_inaudit_reorder_flow.py")

# Ticket -> the subsystem its fix lives in. Widget behaviour is asserted only by
# tests/widget; Bridge/lease/claim behaviour only by the dispatch suite; Qt
# layout only by tests/ui_qt; so a ticket may not borrow another one's group.
ASSIGN = {}
for ticket in ["T-110", "T-129", "T-132", "T-133", "T-157", "T-39", "T-40",
               "T-41", "T-54", "T-55", "T-57", "T-59", "T-60", "T-65", "T-66",
               "T-69", "T-71", "T-72", "T-80", "T-82", "T-84", "T-87", "T-90",
               "T-92", "T-93", "T-96", "T-97", "T-98", "T-99", "T-33", "T-31"]:
    ASSIGN[ticket] = DISPATCH
for ticket in ["T-34", "T-38", "T-56", "T-58", "T-62", "T-63", "T-64", "T-68",
               "T-70", "T-74", "T-75", "T-76", "T-77", "T-78", "T-79", "T-83",
               "T-85", "T-88", "T-89", "T-91", "T-94", "T-95", "T-111", "T-112",
               "T-130", "T-250"]:
    ASSIGN[ticket] = WIDGET
for ticket in ["T-43", "T-44", "T-46", "T-47", "T-48", "T-61", "T-67", "T-73",
               "T-81", "T-86", "T-164", "T-165"]:
    ASSIGN[ticket] = UI
for ticket in ["T-32", "T-182", "T-187", "T-194", "T-195"]:
    ASSIGN[ticket] = CONFIG
for ticket in ["T-131", "T-146", "T-160"]:
    ASSIGN[ticket] = INBOX

# pytest prints "808 passed", the node runner prints "ℹ pass 808" -- the count
# sits on opposite sides of the word, so both orders have to be counted.
COUNT_BEFORE = re.compile(r"(\d+)\s+passed\b", re.I)
COUNT_AFTER = re.compile(r"\bpass\s+(\d+)", re.I)


def collected(command):
    """Warn, do not abort, if a group would silently prove nothing.

    The per-ticket run already refuses a selection that counted zero, so a
    transient preflight failure must not abort the other 60 tickets.
    """
    if command is WIDGET:
        return len(list(pathlib.Path("tests/widget").glob("*.test.js"))) > 0
    for _ in range(3):
        probe = subprocess.run(
            command + " --collect-only", shell=True, capture_output=True,
            text=True, encoding="utf-8", errors="replace")
        if probe.returncode == 0:
            return True
    print("WARN preflight could not collect:", command, flush=True)
    return True


def reverify(ticket):
    command = ASSIGN[ticket]
    probe = subprocess.run(command, shell=True, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    # Scan the WHOLE stream, not its tail: concurrent runs interleave their
    # summaries and a tail-only read sees a truncated one.
    out = (probe.stdout or "") + (probe.stderr or "")
    before = COUNT_BEFORE.search(out)
    after = COUNT_AFTER.search(out)
    count = int(before.group(1)) if before else (int(after.group(1)) if after else 0)
    if probe.returncode != 0 or count == 0:
        return ticket, "REFUSED", f"rc={probe.returncode} count={count} {out.strip()[-160:]}"
    r = subprocess.run([PY_EXE, SAIPEN, "work", "reverify", ticket, "--run", command, "--json"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        body = json.loads(r.stdout[r.stdout.index("{"):], strict=False)
    except Exception:
        body = {}
    if r.returncode or not body.get("ok"):
        return ticket, "REFUSED", (r.stderr or r.stdout or "").strip()[-200:]
    return ticket, "OK", f"{body.get('receipt_id')} count={count}"


def main():
    for group in (DISPATCH, WIDGET, UI, CONFIG, INBOX):
        collected(group)
    # A ticket already carrying an EXECUTED receipt ON THIS TREE needs no rerun.
    # Matching on "has an executed check" alone would wrongly skip the 108
    # tickets verified against earlier trees, which is the exact staleness the
    # validator is reporting.
    current = subprocess.run([PY_EXE, SAIPEN, "validate", "--json"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace").stdout
    body = json.loads(current[current.index("{"):], strict=False)
    fingerprint = body["conformance_status"]["receipt"]["source_tree_fingerprint"]
    done = set()
    store = pathlib.Path(".saipen/recovery/conformance/reverify")
    for path in store.glob("*.json"):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt.get("source_tree_fingerprint") != fingerprint:
            continue
        if any(entry.get("executed") for entry in receipt.get("verification") or []):
            done.add(receipt.get("work"))
    print("current tree", fingerprint, flush=True)
    tickets = [t for t in sorted(ASSIGN) if t not in done]
    print(f"{len(tickets)} to run, {len(done)} already executed", flush=True)
    with ThreadPoolExecutor(max_workers=1) as pool:
        for ticket, verdict, detail in pool.map(reverify, tickets):
            print(verdict, ticket, detail, flush=True)


if __name__ == "__main__":
    main()