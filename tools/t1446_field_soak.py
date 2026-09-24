"""T-1446 field soak: unattended execution with a REAL agent host and model.

The deterministic chaos family (`test_t1446_supervise`) proves the execution
owner against a scripted agent. This drives the same owner against the
installed OpenCode runtime and a real routed model on a disposable git
worktree project, for real wall-clock time, with deliberate worker deaths.

Every generation is a fresh `opencode run cc` process: a cold successor with
zero private memory that must recover the execution from canonical state and
the per-request AUTO_RECALL seam. Nothing here types a second `cc`.

    python tools/t1446_field_soak.py --model sairoute/SAIFREN \
        --wall-seconds 3600 --kill-at 900 --kill-at 2100 --out DIR

Quality and efficiency are reported separately (SRC-106 section 13); nothing
is folded into a score, and a result is evidence, never routing truth.

The fixture's `saipen_home` is this checkout, so every generation imports the
engine from its working tree as it is at that moment. The report therefore
binds the source it tested (`source`, T-1511): the Git identity at launch, at
every interim sample and at the end, and `integrity` STABLE / DRIFTED /
UNMEASURED. An edit made and reverted between two samples is not observable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1363_zero_manual_entry as fixtures  # noqa: E402
from freshness import FreshnessError, compute_source_identity  # noqa: E402
from t1363_field_polygon import _git_worktree  # noqa: E402

from saipen_engine import worker  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.operations import ticket_add  # noqa: E402

OPENCODE = shutil.which("opencode")
#: The checkout every generation imports the engine from (T-1511).
SOURCE_ROOT = TOOLS.parent
_SAIPEN_MEMORY = ".saipen/"

#: Small bounded Work with executable acceptance. The same shapes and the
#: same acceptance serve every model the soak is pointed at.
TASKS = (
    ("add a one-line module docstring at the top of src/app.py",
     "src/app.py begins with a docstring line"),
    ("create src/mathx.py defining add(a, b) that returns a + b, and "
     "tests/test_mathx.py with a unittest asserting add(2, 3) == 5",
     "python -m unittest discover -s tests -t . passes"),
    ("create README.md containing exactly one sentence describing this project",
     "README.md exists and holds one sentence"),
)


def build_project() -> Path:
    root = fixtures.project(None)
    # The shared fixture writes saipen_home as an unescaped double-quoted
    # scalar, which the validator FAILs; a field agent would spend its first
    # slices on that fixture defect instead of the Work.
    state = root / ".saipen" / "STATE.md"
    lines = []
    escaped = 'saipen_home: "' + str(fixtures.REPO).replace("\\", "\\\\") + '"'
    for line in state.read_text(encoding="utf-8").splitlines():
        lines.append(escaped if line.startswith("saipen_home: ") else line)
    state.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for description, verify in TASKS:
        added = ticket_add(root, "test-agent", "P1", description, [], verify)
        if not added.ok:
            raise RuntimeError(added.to_dict())
    return _git_worktree(root)


def _open_tickets(root: Path) -> int:
    board = parse_board((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
    return sum(
        1
        for ticket in board.get("tickets", {}).values()
        if ticket.get("section") in ("## TODO", "## DOING")
    )


def _git_paths(root: Path, *args: str) -> list[str]:
    done = subprocess.run(["git", "-C", os.fspath(root), *args], capture_output=True, check=True)
    return [
        path
        for path in done.stdout.decode("utf-8", "surrogateescape").split("\0")
        if path and not path.startswith(_SAIPEN_MEMORY)
    ]


def _delta_digests(root: Path) -> dict[str, str]:
    """Working-tree delta from HEAD outside project memory: path -> sha256 of
    the bytes a generation would import now, or "deleted"."""
    paths = _git_paths(root, "diff", "--name-only", "-z", "--no-renames", "HEAD", "--")
    paths += _git_paths(root, "ls-files", "-z", "--others", "--exclude-standard", "--")
    digests: dict[str, str] = {}
    for rel in sorted(set(paths)):
        try:
            digests[rel] = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        except FileNotFoundError:
            digests[rel] = "deleted"
    return digests


def source_identity(root: Path) -> dict:
    """The source a generation imports at this moment, or why it has no name.

    `dirty` maps each changed path to its bytes' digest under the Git model;
    the no-Git model fingerprints the whole tree and cannot name paths."""
    try:
        identity = compute_source_identity(root)
        dirty = _delta_digests(root) if identity.discovery_model == "git-delta-v1" else None
    except (FreshnessError, OSError, subprocess.SubprocessError) as exc:
        return {"measured": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
    return {
        "measured": True,
        "source_head": identity.source_head,
        "source_tree_fingerprint": identity.source_tree_fingerprint,
        "dirty": dirty,
    }


def source_drift(root: Path, launch: dict, now: dict) -> dict:
    """Compare two identities. `changed_paths` is None when drift is certain
    but the paths cannot be named."""
    if not (launch.get("measured") and now.get("measured")):
        return {"integrity": "UNMEASURED", "changed_paths": []}
    key = ("source_head", "source_tree_fingerprint")
    if all(launch[name] == now[name] for name in key):
        return {"integrity": "STABLE", "changed_paths": []}
    before, after = launch.get("dirty"), now.get("dirty")
    if before is None or after is None:
        return {"integrity": "DRIFTED", "changed_paths": None}
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    if launch["source_head"] != now["source_head"]:
        try:
            changed.update(_git_paths(
                root, "diff", "--name-only", "-z", "--no-renames",
                launch["source_head"], now["source_head"], "--",
            ))
        except (OSError, subprocess.SubprocessError):
            return {"integrity": "DRIFTED", "changed_paths": None}
    return {"integrity": "DRIFTED", "changed_paths": sorted(changed) or None}


def source_report(root: Path, launch: dict, end: dict, samples: list[dict],
                  elapsed: float) -> dict:
    """STABLE only when the end matches the launch and no sample saw drift;
    a drift seen by any sample stays DRIFTED even if the tree later returned."""
    final = source_drift(root, launch, end)
    drifted = [sample for sample in samples if sample["integrity"] == "DRIFTED"]
    if final["integrity"] == "DRIFTED":
        drifted.append({**final, "elapsed_seconds": round(elapsed, 1)})
    changed: set[str] | None = set()
    for sample in drifted:
        if sample["changed_paths"] is None:
            changed = None
        elif changed is not None:
            changed.update(sample["changed_paths"])
    return {
        "root": str(root),
        "at_launch": launch,
        "at_end": end,
        "integrity": "DRIFTED" if drifted else final["integrity"],
        "changed_paths": sorted(changed) if changed is not None else None,
        "first_drift_elapsed_seconds": drifted[0]["elapsed_seconds"] if drifted else None,
        "samples": len(samples),
        "unmeasured_samples": sum(1 for s in samples if s["integrity"] == "UNMEASURED"),
    }


def supplier(root: Path, minimum: int, stop: threading.Event, log: list[dict]) -> None:
    """Keep bounded Work available for a long soak: one new small task
    whenever fewer than `minimum` are open. Same shape, same acceptance style,
    numbered so each is distinct Work (never a duplicate by construction)."""
    number = 0
    while not stop.wait(30.0):
        try:
            if _open_tickets(root) >= minimum:
                continue
            number += 1
            added = ticket_add(
                root, "test-agent", "P2",
                f"create src/value_{number}.py defining value_{number}() that returns "
                f"{number}, and tests/test_value_{number}.py asserting it",
                [],
                "python -m unittest discover -s tests -t . passes",
            )
            log.append({"at": time.time(), "ok": added.ok, "ticket": added.data.get("ticket")})
        except (OSError, ValueError, RuntimeError) as exc:
            log.append({"at": time.time(), "ok": False, "error": str(exc)[:200]})


def interim(root: Path, out: Path, started: float, kills: list, supplied: list,
            stop: threading.Event, every: float, source_launch: dict | None = None,
            source_samples: list | None = None) -> None:
    """Durable evidence while the soak runs: a driver death loses nothing."""
    while not stop.wait(every):
        source = None
        if source_launch is not None:
            sample = source_drift(SOURCE_ROOT, source_launch, source_identity(SOURCE_ROOT))
            sample["elapsed_seconds"] = round(time.monotonic() - started, 1)
            if source_samples is not None:
                source_samples.append(sample)
            source = {"integrity": sample["integrity"], "changed_paths": sample["changed_paths"]}
        try:
            board = parse_board((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
            sections: dict[str, int] = {}
            titles: dict[str, int] = {}
            for ticket in board.get("tickets", {}).values():
                section = ticket.get("section", "?")
                sections[section] = sections.get(section, 0) + 1
                title = str(ticket.get("description") or "").strip().lower()
                titles[title] = titles.get(title, 0) + 1
            live = root / worker.LIVE_GENERATION_REL
            snapshot = {
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "sections": sections,
                "duplicate_work_count": sum(c - 1 for c in titles.values() if c > 1),
                "live_generation": json.loads(live.read_text(encoding="utf-8"))
                if live.exists() else None,
                "deliberate_kills": list(kills),
                "supplied": len(supplied),
                "source": source,
            }
            with (out / "interim.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(snapshot) + "\n")
        except (OSError, ValueError) as exc:
            with (out / "interim.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"error": str(exc)[:200], "source": source}) + "\n")


def killer(root: Path, kill_at: list[float], started: float, log: list[dict]) -> None:
    """Deliberate worker death: kill the LIVE generation's whole process tree."""
    for moment in sorted(kill_at):
        delay = started + moment - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        live = root / worker.LIVE_GENERATION_REL
        try:
            record = json.loads(live.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.append({"at": moment, "killed": None, "reason": "no live generation"})
            continue
        pid = int(record.get("pid") or 0)
        if os.name == "nt":
            done = subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True, text=True
            )
            ok = done.returncode == 0
        else:
            try:
                os.killpg(pid, 9)
                ok = True
            except OSError:
                ok = False
        log.append({"at": moment, "killed": pid, "generation": record.get("lease_generation"),
                    "ok": ok})


def assess(root: Path) -> dict:
    """QUALITY dimensions read from the project itself after the run."""
    board = parse_board((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
    tickets = board.get("tickets", {})
    titles: dict[str, int] = {}
    for ticket in tickets.values():
        title = str(ticket.get("description") or "").strip().lower()
        titles[title] = titles.get(title, 0) + 1
    sections: dict[str, list[str]] = {}
    for tid, ticket in tickets.items():
        sections.setdefault(ticket.get("section", "?"), []).append(tid)
    intake = root / ".saipen" / "intake" / "active"
    receipts = sorted(p.name for p in intake.glob("SRC-*.md")) if intake.exists() else []
    app_path = root / "src" / "app.py"
    app = app_path.read_text(encoding="utf-8") if app_path.exists() else ""
    readme = root / "README.md"
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        cwd=str(root), capture_output=True, text=True, timeout=120,
    ) if (root / "tests").exists() else None
    validate = subprocess.run(
        [sys.executable, str(TOOLS / "validate.py"), "--gate", "core"],
        cwd=str(root), capture_output=True, text=True, timeout=300,
    )
    verdict = (validate.stdout.strip().splitlines() or [""])[-1]
    return {
        "tickets_by_section": {key: sorted(value) for key, value in sections.items()},
        "duplicate_work_count": sum(count - 1 for count in titles.values() if count > 1),
        "source_receipts": receipts,
        "acceptance": {
            "T-1_docstring": app.lstrip().startswith(('"""', "'''", '"', "'", "#")),
            "T-2_tests_pass": bool(tests and tests.returncode == 0),
            "T-3_readme_one_sentence": readme.exists()
            and len(re.findall(r"[.!?](\s|$)", readme.read_text(encoding="utf-8"))) == 1,
        },
        "validator": verdict,
        "validator_exit": validate.returncode,
    }


def survey(root: Path) -> dict:
    """`assess`, but a run's evidence never dies with its project (T-1484).

    Measured 2026-09-23: the relaunched 24H gate's project vanished whole at a
    generation boundary, `assess` raised FileNotFoundError on BOARD.md, and the
    report -- supervise counters, history, gpu_lane -- was never written.
    """
    if not (root / ".saipen" / "BOARD.md").is_file():
        left = None
        if root.exists():
            left = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))[:50]
        return {"verdict": "PROJECT_VANISHED", "left_in_project": left}
    try:
        return assess(root)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return {"verdict": "ASSESS_FAILED", "error": f"{type(exc).__name__}: {exc}"[:300]}


def efficiency(result: dict) -> dict:
    history = result.get("history") or []
    generations = [item for item in history if "generation" in item]
    asked = sum(
        1
        for item in generations
        if not item.get("progressed")
        and re.search(r"what would you like|could you clarify|do you want me to|"
                      r"should i (?:continue|proceed)|typo or shorthand",
                      str(item.get("output_tail") or ""), re.IGNORECASE)
    )
    return {
        "generations": len(generations),
        "progress_generations": sum(1 for item in generations if item.get("progressed")),
        "slow_bounded_generations": sum(1 for item in generations if item.get("bounded")),
        "asked_user_heuristic_count": asked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--fallback-model", action="append", default=[])
    parser.add_argument("--wall-seconds", type=float, default=3600.0)
    parser.add_argument("--kill-at", type=float, action="append", default=[])
    parser.add_argument("--slice-timeout", type=float, default=420.0)
    parser.add_argument("--max-slice-seconds", type=float, default=1200.0)
    parser.add_argument("--max-cycles", type=int, default=80)
    parser.add_argument("--kill-every", type=float, default=0.0,
                        help="also kill the live generation every N seconds")
    parser.add_argument("--supply-min-open", type=int, default=0,
                        help="keep at least N open tickets by adding small tasks")
    parser.add_argument("--interim-every", type=float, default=1800.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if not OPENCODE:
        print(json.dumps({"ok": False, "code": "CAPABILITY_UNAVAILABLE", "detail": "opencode"}))
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    source_launch = source_identity(SOURCE_ROOT)
    source_samples: list[dict] = []
    (out / "source.json").write_text(
        json.dumps({"root": str(SOURCE_ROOT), "at_launch": source_launch}, indent=2),
        encoding="utf-8",
    )
    root = build_project()
    (out / "project.txt").write_text(str(root), encoding="utf-8")
    started_wall = time.time()
    started = time.monotonic()
    kills: list[dict] = []
    supplied: list[dict] = []
    stop = threading.Event()
    schedule = list(args.kill_at)
    if args.kill_every > 0:
        moment = args.kill_every
        while moment < args.wall_seconds:
            schedule.append(moment)
            moment += args.kill_every
    sampler = threading.Thread(
        target=interim,
        args=(root, out, started, kills, supplied, stop, args.interim_every,
              source_launch, source_samples),
        daemon=True,
    )
    threads = [
        threading.Thread(target=killer, args=(root, schedule, started, kills), daemon=True),
        sampler,
    ]
    if args.supply_min_open > 0:
        threads.append(threading.Thread(
            target=supplier, args=(root, args.supply_min_open, stop, supplied), daemon=True
        ))
    for thread in threads:
        thread.start()
    result = worker.supervise(
        root,
        [OPENCODE, "run", "cc", "--format", "json", "--auto", "--model", worker.MODEL_PLACEHOLDER],
        model=args.model,
        fallback_models=tuple(args.fallback_model),
        max_cycles=args.max_cycles,
        slice_timeout=args.slice_timeout,
        max_slice_seconds=args.max_slice_seconds,
        heartbeat_every=5.0,
        max_wall_seconds=args.wall_seconds,
        keep_output_tail=1500,
    )
    stop.set()
    sampler.join(timeout=120.0)
    elapsed = time.monotonic() - started
    source = source_report(
        SOURCE_ROOT, source_launch, source_identity(SOURCE_ROOT), list(source_samples), elapsed
    )
    report = {
        "supplied_tickets": supplied,
        "schema_version": 1,
        "project": str(root),
        "model": args.model,
        "fallback_models": args.fallback_model,
        "started_at_unix": started_wall,
        "elapsed_seconds": round(elapsed, 1),
        "wall_bound_seconds": args.wall_seconds,
        "supervise": {key: value for key, value in result.items() if key != "history"},
        "history": result.get("history"),
        "deliberate_kills": kills,
        "quality": survey(root),
        "efficiency": efficiency(result),
        "manual_continue_count": 0,
        "source": source,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = {k: report[k] for k in ("elapsed_seconds", "quality", "efficiency")}
    summary["source_integrity"] = source["integrity"]
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
