"""The declared core-unit family as SHIP evidence (T-1344).

``test_runner`` declares one core-unit family -- ``python -m unittest discover
-s tools -p test_*.py`` -- and closures kept recording green from narrower
invocations (named modules imported dotted, never the whole discovery in its
own order). Waves closed green while the declared family was red, because
nothing tied the evidence a SHIP cites to the family the repository declares.

This module is that tie, in three parts:

* **Baseline.** ``tools/core_unit_baseline.json`` records the family's inherited
  red set by test id. A NEW red is a test id outside it; the inherited ones stay
  visible without blocking unrelated Work.
* **Record.** A run of the declared family, in a disposable copy of the working
  tree, is written as a JSON record under ``.saipen/evidence/core-unit/`` with
  the content fingerprint of the copy it tested. A LOG record anchored on
  ``CORE-UNIT-EVIDENCE`` cites it by path and digest. The record is produced by
  running the family; prose about a run is not a run.
* **Gate.** ``ship_gate`` refuses a transition into SHIP when the project
  declares the family and the ticket's current VERIFY cycle cites no admissible
  record: none, a digest that does not match, a run with a new red, a run that
  did not complete, or a fingerprint that is not the tree being shipped.
  A repository may explicitly opt into focused ticket evidence; then the full
  family gates publication of the final batch instead (``focused_unit``).
"""

from __future__ import annotations

import contextlib
import datetime
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path

FAMILY_NAME = "unit"
#: The project declares the family by carrying the runner that declares it.
DECLARATION_REL = "tools/saipen_engine/test_runner.py"
BASELINE_REL = "tools/core_unit_baseline.json"
RECORD_DIR_REL = ".saipen/evidence/core-unit"
#: T-1481. The red sections of a fresh run, kept beside nothing that decides:
#: a runtime cache for advisory triage (SAIGPU), never part of a record.
RED_SECTIONS_REL = ".saipen/cache/core-unit"
#: One red section is cut to this many characters; the tail holds the error.
RED_SECTION_CHARS = 4000
MARKER = "CORE-UNIT-EVIDENCE"
SCHEMA_VERSION = 1
#: The subject is everything the sandbox copy holds except canonical state.
#: The family reads far more than tools/ and saipen/ -- tests/ fixtures,
#: bootstrap/, extensions/, VERSION and the root file set through validate.py
#: -- so a narrower digest let a PASS be reused for a tree it never tested.
#: `.saipen/` is left out on purpose: every checkpoint rewrites it, so
#: fingerprinting it would make any record stale the moment its own LOG line
#: lands. `.git/` is history, not the tree under test.
FINGERPRINT_EXCLUDED = (".git", ".saipen")

#: T-1779: top-level operator INPUT, not tested subject. The audit inbox takes
#: handoff drops at any moment; inside the family it moved the fingerprint
#: mid-run (a full re-snapshot) and could move a validator verdict in the
#: sandbox. It is left out of the copy AND the fingerprint, so a record still
#: describes exactly the bytes that ran. Only the top level: a directory named
#: `audit` anywhere below it stays subject.
FAMILY_INPUT_EXCLUDED = ("audit",)

#: T-1530: how many times `evidence` re-snapshots when the live tree drifts
#: away from the copy that ran during the run window (a concurrent editor in a
#: busy multi-session tree). Each retry is a fresh family run against a fresh
#: copy, so the bound is small: a transient edit clears in one, and persistent
#: drift is a real mismatch that should fail rather than loop.
EVIDENCE_DRIFT_RETRIES = 3

#: One red test in the unittest summary. ``-v`` prints a docstring in place of
#: the id on the progress line, so ids come from these headers only. A subTest
#: header appends ``[message]`` and/or ``(params)``; they are dropped, so every
#: red subtest of one test is that test's single id.
_RED_RE = re.compile(r"^(FAIL|ERROR|UNEXPECTED SUCCESS): (\S+) \(([^()\s]+)\)(?: .*)?$")
#: unittest's error list writes this separator directly above every header, so
#: a line that merely LOOKS like a header (a test printing `FAIL: ...`) is not one.
_SEPARATOR = "=" * 70
_HEADER_PREFIXES = ("FAIL: ", "ERROR: ", "UNEXPECTED SUCCESS: ")
_RAN_RE = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
_TALLY_RE = re.compile(r"^(OK|FAILED)\b(?: \((.*)\))?\s*$", re.MULTILINE)
_TALLY_FIELD_RE = re.compile(r"\b(?:failures|errors|unexpected successes)=(\d+)")
_EVIDENCE_RE = re.compile(
    r"^" + MARKER + r" (?P<verdict>PASS|FAIL)\b.*?"
    r"\brecord:(?P<record>\S+) sha256:(?P<sha>[0-9a-f]{64})\b"
)


def declared(root: Path | str) -> bool:
    """True when this project declares the core-unit family."""
    return (Path(root) / DECLARATION_REL).is_file()


def family():
    """The declared family, from the ONE registry `saipen test` also runs."""
    from .test_runner import _families

    for item in _families():
        if item.name == FAMILY_NAME:
            return item
    raise LookupError(f"test_runner declares no {FAMILY_NAME!r} family")


def parse_output(text: str) -> dict:
    """The red ids of a complete unittest run, with the counts that audit them.

    ``text`` is the runner's stream (stderr): a test's own stdout can print
    anything. ``headers`` counts red headers, ``unparsed`` the ones the id
    grammar missed, and ``tallied`` is the red total unittest printed on its
    final ``OK``/``FAILED (...)`` line (None when there is none).
    """
    body = (text or "").replace("\r\n", "\n")
    lines = body.split("\n")
    red = set()
    headers = parsed = 0
    for above, line in zip(lines, lines[1:]):
        if above != _SEPARATOR or not line.startswith(_HEADER_PREFIXES):
            continue
        headers += 1
        match = _RED_RE.match(line)
        if match is None:
            continue
        parsed += 1
        _kind, name, where = match.groups()
        red.add(where if where.endswith("." + name) else f"{where}.{name}")
    ran = _RAN_RE.findall(body)
    tally = _TALLY_RE.findall(body)
    tallied = None
    if tally:
        tallied = sum(int(count) for count in _TALLY_FIELD_RE.findall(tally[-1][1]))
    return {
        "ran": int(ran[-1]) if ran else None,
        "red": sorted(red),
        "headers": headers,
        "unparsed": headers - parsed,
        "tallied": tallied,
    }


def red_sections(text: str) -> dict:
    """``{test id: its section of the unittest error list}`` (T-1481).

    The same anchoring as ``parse_output``: a section starts at a separator
    line directly above a red header and ends at the next separator or dash
    rule that closes the error list. Long sections keep their tail, where the
    exception is.
    """
    lines = (text or "").replace("\r\n", "\n").split("\n")
    sections: dict = {}
    for index, (above, line) in enumerate(zip(lines, lines[1:])):
        if above != _SEPARATOR or not line.startswith(_HEADER_PREFIXES):
            continue
        match = _RED_RE.match(line)
        if match is None:
            continue
        _kind, name, where = match.groups()
        test_id = where if where.endswith("." + name) else f"{where}.{name}"
        body = []
        for follow in lines[index + 2 :]:
            if follow == _SEPARATOR or (follow.startswith("-" * 70) and body and body[-1] == ""):
                break
            body.append(follow)
        section = "\n".join([line, *body]).strip()
        if len(section) > RED_SECTION_CHARS:
            section = line + "\n...\n" + section[-RED_SECTION_CHARS:]
        sections.setdefault(test_id, section)
    return sections


def keep_red_sections(root: Path | str, record_path: str, sections: dict) -> str | None:
    """Cache a fresh run's red sections next to nothing canonical (T-1481)."""
    if not sections:
        return None
    directory = Path(root) / RED_SECTIONS_REL
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (Path(record_path).stem + ".red.json")
    payload = {"record": record_path, "sections": sections}
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return path.relative_to(Path(root)).as_posix()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_fingerprint(root: Path | str, *, exclude_top=None) -> str:
    """Content digest of the tested subject, tracked or not.

    The file set is the one ``run_family`` copies into its sandbox -- the same
    ignore rule -- minus ``FINGERPRINT_EXCLUDED`` at the top level, so the
    digest of the real tree and of the copy agree exactly when the bytes do.
    """
    from .test_runner import _ignore_copy

    base = Path(root)
    excluded = (FINGERPRINT_EXCLUDED + FAMILY_INPUT_EXCLUDED
                if exclude_top is None else tuple(exclude_top))
    files = []
    for directory, dirnames, filenames in os.walk(base):
        here = Path(directory)
        ignored = _ignore_copy(directory, [*dirnames, *filenames])
        if here == base:
            ignored |= set(excluded)
        dirnames[:] = sorted(name for name in dirnames if name not in ignored)
        files.extend(here / name for name in filenames if name not in ignored)
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(base).as_posix()):
        if not path.is_file():
            continue
        digest.update(path.relative_to(base).as_posix().encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def load_baseline(root: Path | str) -> tuple[dict | None, str | None]:
    """``(baseline, error)``; exactly one is None."""
    path = Path(root) / BASELINE_REL
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"{BASELINE_REL} is missing"
    except (OSError, ValueError) as exc:
        return None, f"{BASELINE_REL} is unreadable: {exc}"
    red = data.get("red") if isinstance(data, dict) else None
    if (
        not isinstance(data, dict)
        or data.get("schema") != SCHEMA_VERSION
        or data.get("family") != FAMILY_NAME
        or not isinstance(red, list)
        or not all(isinstance(item, str) for item in red)
    ):
        return None, f"{BASELINE_REL} is not a schema {SCHEMA_VERSION} {FAMILY_NAME!r} baseline"
    return data, None


def baseline_digest(root: Path | str) -> str:
    return _sha256_file(Path(root) / BASELINE_REL)


#: The four files one checkpoint writes together. A copy that straddles a
#: checkpoint holds a STATE ahead of its LOG (T-1479).
CHECKPOINT_FILES = ("STATE.md", "LOG.md", "BOARD.md", "MANIFEST.json")
#: Attempts to copy `.saipen` between two checkpoints before giving up.
CONSISTENT_COPY_ATTEMPTS = 20


def _checkpoint_stamp(saipen_dir: Path) -> tuple:
    stamp = []
    for name in CHECKPOINT_FILES:
        try:
            st = (saipen_dir / name).stat()
        except FileNotFoundError:
            stamp.append(None)
            continue
        stamp.append((st.st_size, st.st_mtime_ns))
    return tuple(stamp)


def _without_locks(ignore):
    """Lock files are this process's runtime, not state: a held one cannot even
    be read on Windows, and a sandbox creates its own on demand."""

    def wrapped(directory: str, names: list[str]) -> set[str]:
        ignored = set(ignore(directory, names))
        if Path(directory).name == "locks":
            ignored.update(name for name in names if name.endswith(".lock"))
        return ignored

    return wrapped


def _copy_saipen_once(source: Path, target: Path, ignore, *, lock: bool,
                      allowed=None) -> bool:
    """Copy ``source/.saipen`` to ``target``; True when no checkpoint landed meanwhile.

    The checkpoint files are compared before and after, so an optimistic copy
    that straddled a checkpoint is detected. With ``lock`` the canonical writer
    lock is also taken when it is free, so no writer can start a checkpoint
    mid-copy. Copying `.saipen` takes tens of seconds and a held lock refuses
    every canonical writer WRITER_BUSY meanwhile, so the lock is for a retry
    only, never the first attempt.

    ``allowed`` (T-1889) names the `.saipen` child directories the subject
    declared it reads; ``None`` copies every one of them. The canonical top
    level FILES are copied either way, so the stamp compared below covers the
    same four files whether the copy was narrowed or not.
    """
    from .lock import WriterLock

    held = False
    # timeout=0: this is a probe, not a wait. A held lock must not stall the
    # family run for the bounded writer budget; the retry path handles it.
    writer = WriterLock(source, timeout=0)
    if lock:
        try:
            held = writer.acquire()
        except PermissionError:
            held = False
    try:
        canonical = source / ".saipen"
        inner = ignore
        if allowed is not None:
            inner = _only_saipen_subtrees(canonical, allowed, ignore)
        before = _checkpoint_stamp(canonical)
        shutil.copytree(canonical, target, symlinks=True, ignore=_without_locks(inner))
        return held or _checkpoint_stamp(canonical) == before
    finally:
        if held:
            writer.release()


def _only_saipen_subtrees(canonical: Path, allowed, ignore):
    """Keep only the DECLARED child DIRECTORIES of `.saipen`; files always stay.

    T-1889. The top-level canonical files are never filtered: project
    resolution reads `.saipen/`, and a sandbox carrying a `.saipen` it cannot
    parse would test a different subject than the one the record names. Only
    the heavy subtree (evidence, recovery, kitchen, ...) is optional, and only
    when the manifest entry names it.
    """
    allowed = frozenset(allowed)
    children = {entry.name for entry in canonical.iterdir() if entry.is_dir()}

    def wrapped(directory: str, names: list[str]) -> set[str]:
        ignored = set(ignore(directory, names))
        if Path(directory) == canonical:
            ignored.update(name for name in names
                           if name in children and name not in allowed)
        return ignored

    return wrapped


def copy_tree_consistent(source: Path, sandbox: Path, ignore, *, scope=None) -> dict:
    """``shutil.copytree`` whose ``.saipen`` part is ONE checkpoint (T-1479).

    A checkpoint written while the tree is being copied left the sandbox with
    STATE.last_event ahead of the LOG tail; every state-reading test in it then
    answered VALIDATION_FAILED, and the evidence verdict described the copy
    race, not the subject.

    ``scope`` is a resolved decision from ``sandbox_scope``; ``None`` (or a
    FULL decision) copies everything, which is the only behaviour this function
    had before T-1889. A DECLARED decision copies the source tree and `.saipen`
    exactly as always, and adds only the heavy trees the subject declared:
    `.git` when named, and only the named `.saipen` child directories. The
    canonical `.saipen` FILES are always copied -- project resolution reads
    them, and a sandbox that could not resolve its own project would test a
    different subject than the record describes.
    """
    from .sandbox_scope import FULL, copy_plan

    if scope is not None and scope.get("mode") == FULL:
        scope = None
    extra_top = None
    saipen_children = None
    if scope is not None:
        trees, saipen_children = copy_plan(scope)
        extra_top = frozenset() if trees is None else trees

    def ignore_top_saipen(directory: str, names: list[str]) -> set[str]:
        ignored = set(ignore(directory, names))
        if Path(directory) == source:
            if ".saipen" in names:
                ignored.add(".saipen")
            if extra_top is not None:
                # `.git` is a choice, not part of the tested subject: the
                # fingerprint never covered it, so a subject that does not read
                # it must not pay 345 MiB to carry it.
                ignored |= {name for name in names
                            if name in FINGERPRINT_EXCLUDED and name not in extra_top}
            ignored |= set(FAMILY_INPUT_EXCLUDED) & set(names)
        return ignored

    began = time.monotonic()
    shutil.copytree(source, sandbox, symlinks=True, ignore=ignore_top_saipen)
    observed = {"subject_copy_s": round(time.monotonic() - began, 6),
                "canonical_copy_s": 0.0, "canonical_copy_attempts": 0,
                "trees": None if scope is None else sorted(scope["trees"])}
    if not (source / ".saipen").is_dir():
        return observed
    for attempt in range(CONSISTENT_COPY_ATTEMPTS):
        # Each attempt gets a fresh directory BESIDE the sandbox, never inside
        # it: a torn copy is abandoned, not deleted. `.saipen` holds read-only
        # git objects (the saiwiki kitchen clone) that rmtree cannot remove on
        # Windows, and a half-deleted copy made the next attempt fail with
        # FileExistsError. The enclosing temporary directory reclaims them.
        staging = sandbox.parent / f"saipen-copy-{attempt}"
        began = time.monotonic()
        consistent = _copy_saipen_once(source, staging, ignore, lock=attempt > 0,
                                       allowed=saipen_children)
        observed["canonical_copy_s"] += time.monotonic() - began
        observed["canonical_copy_attempts"] += 1
        if consistent:
            os.replace(staging, sandbox / ".saipen")
            observed["canonical_copy_s"] = round(observed["canonical_copy_s"], 6)
            return observed
        time.sleep(min(0.25 * (attempt + 1), 2.0))
    raise RuntimeError(
        f"CORE_UNIT_COPY_TORN: .saipen changed during each of {CONSISTENT_COPY_ATTEMPTS} copies"
    )


#: T-1472. The family is ONE discovery; run as concurrent shards of it, each in
#: its own copy of the same subject, it proves the same thing in a fraction of
#: the wall time (2254 s sequential at af93fd56). One job is the declared
#: command itself, unchanged.
DEFAULT_JOBS = max(1, min(6, (os.cpu_count() or 2) // 2))
#: The stdlib-only shard runner. Like this module it is the harness, not the
#: subject: it runs from the engine, so any project declaring the family shards.
SHARD_RUNNER = Path(__file__).resolve().with_name("core_unit_shard.py")
#: Each module's measured time, kept to balance the next run's shards. A cache
#: beside the red sections: it decides only which shard runs a module.
DURATIONS_REL = ".saipen/cache/core-unit/durations.json"


def shardable(command) -> tuple[str, str] | None:
    """``(start, pattern)`` when ``command`` is exactly the declared discovery
    shape the shard runner reproduces, else None (the family then runs whole)."""
    tail = list(command)[1:]
    if len(tail) != 9 or tail[:4] != ["-B", "-m", "unittest", "discover"]:
        return None
    if tail[4] != "-s" or tail[6] != "-p" or tail[8] != "-v":
        return None
    return tail[5], tail[7]


def plan_shards(modules, weights: dict, jobs: int) -> list[list[str]]:
    """Longest-first onto the least-loaded shard; deterministic for equal input.

    A module with no measured weight is costed at the mean of the measured
    ones, so a new module neither starves nor swamps a shard.

    A shard that drew no module is dropped rather than returned empty. An
    empty shard runs no test, and `unittest` has exited 5 for "no tests ran"
    since CPython 3.12 -- so keeping one turned every run with fewer modules
    than jobs into a red family on a newer interpreter and a green one on an
    older one, over a shard that was never going to assert anything.
    """
    modules = sorted(set(modules))
    known = [float(weights[name]) for name in modules if name in weights]
    default = sum(known) / len(known) if known else 1.0
    cost = {name: float(weights.get(name, default)) for name in modules}
    shards: list[list[str]] = [[] for _ in range(max(1, int(jobs)))]
    loads = [0.0] * len(shards)
    for name in sorted(modules, key=lambda item: (-cost[item], item)):
        index = min(range(len(shards)), key=lambda item: (loads[item], item))
        shards[index].append(name)
        loads[index] += cost[name]
    return [shard for shard in shards if shard]


def load_durations(root: Path | str) -> dict:
    try:
        data = json.loads((Path(root) / DURATIONS_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    modules = data.get("modules") if isinstance(data, dict) else None
    if not isinstance(modules, dict):
        return {}
    return {
        str(name): float(seconds)
        for name, seconds in modules.items()
        if isinstance(seconds, (int, float)) and seconds >= 0
    }


def keep_durations(root: Path | str, measured: dict) -> None:
    """Merge a run's per-module times into the balancing cache."""
    if not measured:
        return
    merged = {**load_durations(root), **measured}
    path = Path(root) / DURATIONS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": 1, "modules": dict(sorted(merged.items()))}
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")


def _modules(sandbox: Path, start: str, pattern: str) -> list[str]:
    """The top-level test modules discovery will import, by file name. A module
    this misses is still run: the catch-all shard takes every unnamed one."""
    import fnmatch

    return sorted(
        path.stem
        for path in (sandbox / start).iterdir()
        if path.is_file()
        and path.suffix == ".py"
        and fnmatch.fnmatch(path.name, pattern)
        and path.stem.isidentifier()
    )


def _run_whole(sandbox: Path, declared_family, spool: Path) -> dict:
    from .test_runner import _run_family

    report = _run_family(
        sandbox, declared_family, spool=spool, owner=sandbox.parent / SANDBOX_OWNER
    )
    # unittest's runner writes to stderr; stdout is the tests' own output.
    text = (spool / "stderr").read_bytes().decode("utf-8", errors="replace")
    return {
        "status": report["status"],
        "exit_code": report.get("exit_code"),
        "processes_leaked": report.get("processes_leaked") or [],
        "duration_s": report.get("duration_s"),
        "process_create_s": report.get("process_create_s"),
        **parse_output(text),
        "sections": red_sections(text),
        "stdout": report.get("stdout") or "",
        "stderr": report.get("stderr") or "",
    }


def _run_shard(sandbox: Path, declared_family, shape: tuple, spec: dict, work: Path) -> dict:
    from .test_runner import TestFamily, _run_family

    spool = work / "spool"
    spool.mkdir()
    spec_path = work / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    manifest_path = work / "manifest.json"
    command = (
        declared_family.command[0],
        "-B",
        str(SHARD_RUNNER),
        *shape,
        str(spec_path),
        str(manifest_path),
    )
    began = time.monotonic()
    report = _run_family(
        sandbox,
        TestFamily(declared_family.name, command, declared_family.timeout),
        spool=spool,
        owner=work / SANDBOX_OWNER,
    )
    text = (spool / "stderr").read_bytes().decode("utf-8", errors="replace")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = None
    return {
        "status": report["status"],
        "exit_code": report.get("exit_code"),
        "processes_leaked": report.get("processes_leaked") or [],
        **parse_output(text),
        "sections": red_sections(text),
        "stdout": report.get("stdout") or "",
        "stderr": report.get("stderr") or "",
        "manifest": manifest if isinstance(manifest, dict) else None,
        "membership_required": True,
        "duration_s": round(time.monotonic() - began, 1),
    }


def _empty_partition_member(shard: dict, proof) -> bool:
    """A discovered worker may own no occurrences, never the whole family.

    Imported cases are attributed to their defining module. A planned alias
    module (or a helper with no tests) can therefore have an empty partition.
    CPython 3.12 reports that worker with exit 5, while 3.11 reports exit 0.
    Only the exact nonempty full-inventory partition proof may justify it.
    """
    if (not isinstance(proof, dict) or type(proof.get("occurrences")) is not int
            or proof["occurrences"] < 1
            or not isinstance(proof.get("inventory_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", proof["inventory_sha256"])):
        return False
    manifest = shard.get("manifest")
    manifest = manifest if isinstance(manifest, dict) else shard
    return (type(shard.get("ran")) is int and shard["ran"] == 0
            and type(manifest.get("selected")) is int and manifest["selected"] == 0
            and manifest.get("selected_indices") == []
            and manifest.get("inventory_sha256") == proof["inventory_sha256"]
            and type(manifest.get("discovered")) is int
            and manifest.get("discovered") == proof["occurrences"]
            and (shard.get("status"), shard.get("exit_code")) in {("PASS", 0), ("FAIL", 5)}
            and not shard.get("red") and shard.get("headers") == 0
            and shard.get("unparsed") == 0 and shard.get("tallied") in (None, 0))


def merge_shards(shards: list[dict]) -> dict:
    """Merge verdicts and prove every canonical test occurrence exactly once.

    Current runners bind the ordered inventory digest and selected positions;
    arithmetic alone is retained only for readable legacy records.
    """
    rans = [shard.get("ran") for shard in shards]
    tallies = [shard.get("tallied") for shard in shards]
    manifests = [shard.get("manifest") or {} for shard in shards]
    sections: dict = {}
    durations: dict = {}
    for shard, manifest in zip(shards, manifests):
        sections.update(shard.get("sections") or {})
        for name, seconds in (manifest.get("modules") or {}).items():
            durations[name] = round(durations.get(name, 0.0) + float(seconds), 1)
    discovered = {manifest.get("discovered") for manifest in manifests}
    selected = [manifest.get("selected") for manifest in manifests]
    partition_error = None
    if None in discovered or None in selected:
        silent = [index for index, item in enumerate(selected) if item is None]
        partition_error = f"shard(s) {silent} never reported their discovery"
    elif len(discovered) != 1:
        partition_error = f"shards discovered different families: {sorted(discovered)}"
    elif sum(selected) != min(discovered):
        partition_error = f"shards kept {sum(selected)} of {min(discovered)} discovered tests"
    membership_required = any(
        shard.get("membership_required") or "inventory_sha256" in manifest
        for shard, manifest in zip(shards, manifests)
    )
    membership_proof = None
    if membership_required and partition_error is None:
        digests = [manifest.get("inventory_sha256") for manifest in manifests]
        indices = [manifest.get("selected_indices") for manifest in manifests]
        if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
               for value in digests) or len(set(digests)) != 1:
            partition_error = "shards do not prove the same exact test inventory"
        elif any(not isinstance(value, list) or len(value) != count
                 for value, count in zip(indices, selected)):
            partition_error = "shards did not report their selected test occurrences"
        else:
            positions = [position for values in indices for position in values]
            size = min(discovered)
            if (any(type(position) is not int for position in positions)
                    or len(positions) != size or sorted(positions) != list(range(size))):
                partition_error = "shards duplicate, omit or misidentify required test occurrences"
            else:
                membership_proof = {"inventory_sha256": digests[0], "occurrences": size}
    empty = [index for index, shard in enumerate(shards)
             if _empty_partition_member(shard, membership_proof)]
    # Keep each worker's raw status/exit/count below. Only a proved empty
    # partition is neutral in the complete family's aggregate verdict.
    statuses = ["PASS" if index in empty else shard["status"]
                for index, shard in enumerate(shards)]
    status = "TIMEOUT" if "TIMEOUT" in statuses else (
        "PASS" if all(item == "PASS" for item in statuses) else "FAIL"
    )
    exits = [0 if index in empty else shard.get("exit_code")
             for index, shard in enumerate(shards)]
    exit_code = None if status == "TIMEOUT" or None in exits else next(
        (code for code in exits if code != 0), 0
    )
    return {
        "status": status,
        "exit_code": exit_code,
        "ran": sum(rans) if None not in rans else None,
        "red": sorted({test for shard in shards for test in shard.get("red") or []}),
        "headers": sum(int(shard.get("headers") or 0) for shard in shards),
        "unparsed": sum(int(shard.get("unparsed") or 0) for shard in shards),
        "tallied": sum(tallies) if None not in tallies else None,
        "sections": sections,
        "stdout": "\n".join(shard.get("stdout") or "" for shard in shards)[-8000:],
        "stderr": "\n".join(shard.get("stderr") or "" for shard in shards)[-8000:],
        "processes_leaked": sorted({pid for shard in shards
                                    for pid in shard.get("processes_leaked") or []}),
        "discovered": next(iter(discovered)) if len(discovered) == 1 else None,
        "partition_error": partition_error,
        "membership_required": membership_required,
        "membership_proof": membership_proof,
        "empty_shards": empty,
        "discovery_process_s": (
            round(sum(float(manifest["discovery_s"]) for manifest in manifests), 6)
            if all(isinstance(manifest.get("discovery_s"), (int, float))
                   for manifest in manifests) else None
        ),
        "shards": [
            {
                "status": shard["status"],
                "exit_code": shard.get("exit_code"),
                "ran": shard.get("ran"),
                "selected": manifest.get("selected"),
                "discovered": manifest.get("discovered"),
                "red": shard.get("red") or [],
                "headers": shard.get("headers"),
                "unparsed": shard.get("unparsed"),
                "tallied": shard.get("tallied"),
                "duration_s": shard.get("duration_s"),
                "inventory_sha256": manifest.get("inventory_sha256"),
                "selected_indices": manifest.get("selected_indices"),
                "discovery_s": manifest.get("discovery_s"),
                "processes_leaked": shard.get("processes_leaked") or [],
            }
            for shard, manifest in zip(shards, manifests)
        ],
        "module_durations_s": dict(sorted(durations.items())),
    }


#: T-1505. A run's sandboxes are stamped with their owner, reclaimed in its own
#: `finally`, and swept by a later run when the owner died first. Measured
#: 2026-09-24: 24 `saipen-core-unit-*` directories (4 runs x 6 shards, about
#: 40 MB each, every one a full copy of `.saipen`) had accumulated in %TEMP%;
#: what survived in each was the read-only object store of the copied saiwiki
#: kitchen clone, which a plain `shutil.rmtree` cannot remove on Windows.
SANDBOX_PREFIX = "saipen-core-unit-"
SANDBOX_OWNER = "owner.json"
#: A sandbox without an owner stamp predates T-1505; reclaim it only this old.
LEGACY_SANDBOX_AGE_S = 12 * 3600
#: A just-exited shard can hold a handle for a moment on Windows.
RECLAIM_ATTEMPTS = 5


def pid_alive(pid: int) -> bool:
    """Whether a process with this id is running (never raises)."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return kernel32.GetLastError() == 5  # ACCESS_DENIED: exists, not ours
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _unlink_writable(target: Path) -> None:
    try:
        os.unlink(target)
    except PermissionError:
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        os.unlink(target)


def reclaim(path: Path) -> bool:
    """Remove one sandbox tree, read-only files included; True when it is gone.

    `shutil.rmtree` stops at the first read-only file on Windows (WinError 5),
    which is exactly what a copied git object store contains, and a handle a
    lingering process holds (WinError 32) cannot be removed at all until that
    process exits. Read-only entries are made writable and retried; a held
    tree gets a few short retries and is then reported. The owner stamp goes
    last and is put back if the directory itself cannot be removed, so a
    later `sweep_stale_sandboxes` still recognises the tree as a sandbox.
    """
    path = Path(path)
    stamp = path / SANDBOX_OWNER

    def writable_retry(func, target, _exc):
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
            func(target)
        except FileNotFoundError:
            pass

    for attempt in range(RECLAIM_ATTEMPTS):
        if not path.exists():
            return True
        try:
            saved = stamp.read_bytes() if stamp.is_file() else None
        except OSError:
            saved = None
        with contextlib.suppress(OSError):
            for child in list(path.iterdir()):
                if child.name == SANDBOX_OWNER:
                    continue
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child, onerror=writable_retry)
                else:
                    _unlink_writable(child)
            if saved is not None:
                _unlink_writable(stamp)
            try:
                path.rmdir()
            except OSError:
                if saved is not None and not stamp.exists():
                    stamp.write_bytes(saved)
                raise
        if not path.exists():
            return True
        time.sleep(0.2 * (attempt + 1))
    return not path.exists()


def reclaim_all(paths) -> list[str]:
    """Reclaim every sandbox concurrently; return the ones that survived.

    T-1876: the sandboxes of one run are disjoint trees, so removing them is
    the one part of the family run that was both serial and purely I/O. At 12
    shards the loop-per-tree cost 286 s of a 2066 s run against 116 s at 6
    shards, paying back most of what the shard split saved. Concurrency keeps
    the per-tree contract exactly: `reclaim` owns one path and reports it.
    """
    items = list(paths)
    if not items:
        return []
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=len(items)) as pool:
        gone = list(pool.map(reclaim, items))
    return [str(item) for item, ok in zip(items, gone) if not ok]


def new_sandbox_root(project: Path | str | None = None) -> Path:
    """One owner-stamped `saipen-core-unit-*` directory under the temp root.

    The stamp names the project the sandbox belongs to when the caller knows
    it: the temp root is shared by every project on the machine, and a run in
    another tree has no business reclaiming this one's sandboxes (T-1823).
    """
    root = Path(tempfile.mkdtemp(prefix=SANDBOX_PREFIX)).resolve()
    stamp = {"pid": os.getpid(), "created": time.time(), "spawn_phase": "COPYING"}
    if project is not None:
        stamp["project"] = str(Path(project).resolve())
    (root / SANDBOX_OWNER).write_text(json.dumps(stamp), encoding="utf-8")
    from .verification_cache import register_sandbox

    register_sandbox(root)
    return root


def _owner_pids(owner: dict) -> list:
    """Every process a stamp names as reading the tree: the process that
    created the sandbox, and the family child it handed the tree to.

    The two are different processes by construction -- the family always runs
    as a child of the run that copies the tree -- so a stamp that named only
    the creator could not tell a sweep that the tree was in use. Measured
    2026-10-19 (T-1823): a sandbox was emptied under a live family child while
    the run that created it was itself still alive to write the record.
    """
    return [owner.get("pid"), owner.get("reader")]


def sweep_stale_sandboxes(
    temp_root: Path | None = None,
    now: float | None = None,
    project: Path | str | None = None,
) -> list[str]:
    """Reclaim sandboxes whose owning run is gone; returns the names reclaimed.

    Only direct children of the temp root named `saipen-core-unit-*` are
    considered. A stamped one is stale when NO process its stamp names is
    running; an unstamped one (pre-T-1505) only when it holds a `project/`
    sandbox and is older than LEGACY_SANDBOX_AGE_S. Nothing outside those
    trees is touched.

    ``project`` is the tree the caller is running; a sandbox stamped with a
    DIFFERENT project is never reclaimed, whatever its stamp says about
    liveness. A pid is only meaningful inside one process space, so the
    liveness of a foreign stamp says nothing about the tree, and reclaiming on
    it deletes a live run's working copy (T-1823).
    """
    base = (Path(temp_root).resolve() if temp_root is not None
            else Path(tempfile.gettempdir()).resolve())
    mine = str(Path(project).resolve()) if project is not None else None
    now = time.time() if now is None else now
    reclaimed: list[str] = []
    try:
        candidates = sorted(base.glob(SANDBOX_PREFIX + "*"))
    except OSError:
        return reclaimed
    for candidate in candidates:
        if not candidate.is_dir() or candidate.is_symlink():
            continue
        stale = False
        try:
            owner = json.loads((candidate / SANDBOX_OWNER).read_text(encoding="utf-8"))
        except FileNotFoundError:
            owner = None
        except (OSError, ValueError):
            continue
        if isinstance(owner, dict):
            recorded = owner.get("project")
            if isinstance(recorded, str) and recorded != mine:
                continue
            stale = not any(pid_alive(pid) for pid in _owner_pids(owner))
        elif owner is None:
            try:
                age = now - candidate.stat().st_mtime
            except OSError:
                continue
            stale = (candidate / "project").is_dir() and age > LEGACY_SANDBOX_AGE_S
        if stale and reclaim(candidate):
            reclaimed.append(candidate.name)
    return reclaimed


def run_family(root: Path | str, *, timeout: int | None = None, jobs: int = 1) -> dict:
    """Run the declared family in a disposable copy; parse the COMPLETE output.

    With ``jobs`` > 1 and a declared command of the discovery shape, the same
    discovery runs as that many concurrent shards, each in its own copy of the
    one consistent snapshot, and every copy must carry the tested fingerprint.
    """
    started = time.monotonic()
    from concurrent.futures import ThreadPoolExecutor

    from .test_runner import _ignore_copy

    if os.name == "nt":
        for var in ("TEMP", "TMP"):
            val = os.environ.get(var)
            if val:
                with contextlib.suppress(OSError):
                    os.environ[var] = str(Path(val).resolve())
    source = Path(root).resolve()
    declared_family = family()
    if timeout is not None:
        declared_family = type(declared_family)(
            declared_family.name, declared_family.command, timeout,
            environment_tools=declared_family.environment_tools,
        )
    shape = shardable(declared_family.command) if int(jobs) > 1 else None
    from .verification_cache import capture

    mark = time.monotonic()
    verification_identity = capture(source, verification_configuration(timeout=timeout, jobs=jobs))
    identity_wall_s = time.monotonic() - mark
    # No sandbox past the module count: `plan_shards` drops a shard that drew
    # no module, and a sandbox with no shard to run is a copy of the tree
    # paid for nothing.
    count = max(1, min(int(jobs), len(_modules(source, *shape)))) if shape else 1
    timings = {"shard_copy_wall_s": 0.0,
               "environment_identity_wall_s": round(identity_wall_s, 6)}
    mark = time.monotonic()
    swept = sweep_stale_sandboxes(project=source)
    timings["sweep_wall_s"] = round(time.monotonic() - mark, 6)
    tmps: list[Path] = []
    try:
        # Each shard lives where the sequential run lives -- its own
        # `saipen-core-unit-*/project` -- so no test sees a longer path.
        tmps = [new_sandbox_root(source) for _ in range(count)]
        sandboxes = [tmp / "project" for tmp in tmps]
        mark = time.monotonic()
        copy_metrics = copy_tree_consistent(source, sandboxes[0], _ignore_copy)
        timings["copy_wall_s"] = round(time.monotonic() - mark, 6)
        # The subject is what was copied, fingerprinted where it was tested:
        # a write to the real tree after this line changes nothing here.
        mark = time.monotonic()
        tested = tree_fingerprint(sandboxes[0])
        timings["hash_wall_s"] = round(time.monotonic() - mark, 6)
        if count == 1:
            spool = tmps[0] / "spool"
            spool.mkdir()
            mark = time.monotonic()
            run = _run_whole(sandboxes[0], declared_family, spool)
            timings["execution_wall_s"] = round(time.monotonic() - mark, 6)
        else:
            mark = time.monotonic()
            with ThreadPoolExecutor(max_workers=count) as pool:
                list(pool.map(lambda target: shutil.copytree(sandboxes[0], target, symlinks=True),
                              sandboxes[1:]))
                copies = list(pool.map(tree_fingerprint, sandboxes[1:]))
            timings["shard_copy_wall_s"] = round(time.monotonic() - mark, 6)
            if any(item != tested for item in copies):
                raise RuntimeError("CORE_UNIT_SHARD_COPY: a shard copy is not the tested subject")
            plan = plan_shards(_modules(sandboxes[0], *shape), load_durations(source), count)
            # Shard 0 is the catch-all: every module no other shard names.
            named = sorted({name for shard in plan[1:] for name in shard})
            specs = [{"exclude": named}, *({"include": shard} for shard in plan[1:])]
            mark = time.monotonic()
            with ThreadPoolExecutor(max_workers=len(specs)) as pool:
                shards = list(pool.map(
                    lambda index: _run_shard(
                        sandboxes[index], declared_family, shape, specs[index], tmps[index]
                    ),
                    range(len(specs)),
                ))
            run = merge_shards(shards)
            timings["execution_wall_s"] = round(time.monotonic() - mark, 6)
    finally:
        mark = time.monotonic()
        leaked = reclaim_all(tmps)
        timings["cleanup_wall_s"] = round(time.monotonic() - mark, 6)
    return {
        **run,
        "sandboxes_swept": swept,
        "sandboxes_leaked": leaked,
        "fingerprint": tested,
        "jobs": count,
        "timings_s": timings,
        "copy_metrics": copy_metrics,
        "verification_identity": verification_identity,
        "duration_s": round(time.monotonic() - started, 1),
        "timeout_s": declared_family.timeout,
        "command": ["python", *declared_family.command[1:]],
    }


def _consistency(run: dict) -> list[str]:
    """What makes a run -- or one shard of it -- not a complete run."""
    red = run.get("red") or []
    problems = []
    if run.get("status") == "TIMEOUT":
        problems.append(f"the family did not finish inside {run.get('timeout_s')} s")
    if not run.get("ran"):
        problems.append("no 'Ran N tests' line: the family did not run to its summary")
    if run.get("exit_code") not in (0, None) and not red:
        problems.append(f"exit code {run.get('exit_code')} with no parsed red test")
    if run.get("exit_code") == 0 and red:
        problems.append("exit code 0 contradicts the parsed red tests")
    if run.get("unparsed"):
        problems.append(f"{run['unparsed']} red header(s) outside the id grammar")
    if run.get("tallied") is not None and run.get("tallied") != run.get("headers"):
        problems.append(
            f"unittest tallied {run['tallied']} red but {run.get('headers')} header(s) were read"
        )
    return problems


def judge(run: dict, baseline_red) -> dict:
    """The verdict of one run against the baseline; the arithmetic lives here only."""
    red = set(run.get("red") or [])
    inherited = set(baseline_red or [])
    new_red = sorted(red - inherited)
    fixed = sorted(inherited - red)
    problems = _consistency(run)
    for index, shard in enumerate(run.get("shards") or []):
        if (run.get("ran") and not run.get("partition_error")
                and _empty_partition_member(shard, run.get("membership_proof"))):
            continue
        shard_run = {**shard, "timeout_s": run.get("timeout_s")}
        problems.extend(f"shard {index}: {problem}" for problem in _consistency(shard_run))
    if run.get("partition_error"):
        problems.append(str(run["partition_error"]))
    if run.get("membership_required") and not run.get("membership_proof"):
        problems.append("the run has no exact shard membership proof")
    if new_red:
        problems.append(f"{len(new_red)} new red outside the baseline")
    return {
        "verdict": "FAIL" if problems else "PASS",
        "new_red": new_red,
        "fixed": fixed,
        "problems": problems,
    }


def _git_head(root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            # No shared stdin and a bound: this one call sat for two hours
            # behind an orphaned test child that was reading the stdin both
            # had inherited (T-1624), so the record was never written.
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True, encoding="utf-8",
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def full_scope_problem(record: dict) -> str | None:
    """A scoped executor/configuration cannot be relabelled as full evidence."""
    if (record.get("scope_kind") == "impact-subset"
            or record.get("verification_tier") not in (None, "FULL")):
        return "narrow verification scope cannot authorize a full core-unit family"
    identity = record.get("verification_identity")
    configuration = identity.get("configuration") if isinstance(identity, dict) else None
    if isinstance(configuration, dict) and configuration.get("family") != FAMILY_NAME:
        return "full core-unit evidence uses a scoped verification configuration"
    return None


def write_record(root: Path | str, run: dict, fingerprint: str) -> dict:
    """Judge ``run`` against the current baseline and persist the record."""
    if issue := full_scope_problem(run):
        raise ValueError(issue)
    base = Path(root)
    baseline, error = load_baseline(base)
    if error:
        raise ValueError(error)
    verdict = judge(run, baseline["red"])
    now = datetime.datetime.now(datetime.timezone.utc)
    from .verification_cache import capture

    verification_identity = run.get("verification_identity")
    if verification_identity is None:
        verification_identity = capture(base, verification_configuration())
    record = {
        "schema": SCHEMA_VERSION,
        "family": FAMILY_NAME,
        "command": run["command"],
        "fingerprint": fingerprint,
        "verification_identity": verification_identity,
        "fingerprint_excludes": list(FINGERPRINT_EXCLUDED + FAMILY_INPUT_EXCLUDED),
        "baseline_sha256": baseline_digest(base),
        "head": _git_head(base),
        "finished_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": run["status"],
        "exit_code": run["exit_code"],
        "ran": run["ran"],
        "duration_s": run["duration_s"],
        "timeout_s": run.get("timeout_s"),
        "headers": run.get("headers"),
        "unparsed": run.get("unparsed"),
        "tallied": run.get("tallied"),
        "red": run["red"],
        "red_sections": run.get("sections") or {},
        "processes_leaked": run.get("processes_leaked") or [],
        # T-1472: how the one discovery was executed, and the proof that its
        # shards covered it. Absent for a whole (single-process) run.
        **{
            key: run[key]
            for key in ("jobs", "discovered", "partition_error", "shards", "module_durations_s",
                        "timings_s", "copy_metrics", "membership_required", "membership_proof",
                        "discovery_process_s")
            if run.get(key) is not None
        },
        **verdict,
    }
    directory = base / RECORD_DIR_REL
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{fingerprint[:16]}-{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "record": record,
        "path": path.relative_to(base).as_posix(),
        "sha256": _sha256_file(path),
    }


def verification_configuration(*, timeout=None, jobs=None) -> dict:
    declared_family = family()
    return {"family": FAMILY_NAME, "command": list(declared_family.command),
            "timeout": timeout if timeout is not None else declared_family.timeout,
            "jobs": DEFAULT_JOBS if jobs is None else int(jobs),
            "environment_tools": (list(declared_family.environment_tools)
                                  if declared_family.environment_tools is not None else None)}


def reusable_record(
    root: Path | str, fingerprint: str, *, verification_identity=None
) -> dict | None:
    """The newest PASS record of exactly this tree and baseline, or None.

    The family's subject is the fingerprinted content, so a Work that changed
    none of it (state, knowledge, a doc outside the trees) is proven by the run
    that already tested those bytes; rerunning would measure the same subject.
    """
    base = Path(root)
    baseline, error = load_baseline(base)
    if error:
        return None
    from .verification_cache import capture

    from .verification_cache import replay_supported

    expected = verification_identity or capture(base, verification_configuration())
    if not replay_supported(expected):
        return None
    digest = baseline_digest(base)
    for path in sorted((base / RECORD_DIR_REL).glob(f"{fingerprint[:16]}-*.json"), reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(record, dict):
            return None
        if (
            record.get("fingerprint") == fingerprint
            and record.get("baseline_sha256") == digest
            and record.get("verification_identity") == expected
        ):
            # Latest compatible outcome wins. A new red must not resurrect
            # an older PASS of the same generation/environment/configuration.
            if full_scope_problem(record) or judge(record, baseline["red"])["verdict"] != "PASS":
                return None
            return {
                "record": record,
                "path": path.relative_to(base).as_posix(),
                "sha256": _sha256_file(path),
            }
    return None


def evidence_line(written: dict) -> str:
    """The anchored LOG text that cites one record."""
    record = written["record"]
    return (
        f"{MARKER} {record['verdict']} family:{FAMILY_NAME} ran:{record['ran']} "
        f"red:{len(record['red'])} new_red:{len(record['new_red'])} "
        f"fixed:{len(record['fixed'])} fingerprint:{record['fingerprint'][:16]} "
        f"record:{written['path']} sha256:{written['sha256']}"
    )


def parse_evidence(text: str) -> dict | None:
    """The anchored citation in one LOG text, or None for anything else."""
    match = _EVIDENCE_RE.match((text or "").strip())
    return match.groupdict() if match else None


def _current_cycle(ticket_id: str, events: list[dict]) -> list[dict] | None:
    from .log import _is_verify_boundary

    for index in range(len(events) - 1, -1, -1):
        event = events[index]
        if (
            event.get("ticket") == ticket_id
            and event.get("taxonomy") == "RUN"
            and _is_verify_boundary(event)
        ):
            return events[index:]
    return None


def evidence_command(ticket_id: str) -> str:
    return f"python tools/core_unit.py evidence {ticket_id}"


def ship_gate(root: Path | str, ticket_id: str, events: list[dict]) -> str | None:
    """Why ``ticket_id`` may not enter SHIP, or None.

    Silent for a project that does not declare the family. Otherwise the
    ticket's CURRENT VERIFY cycle must cite intact executed evidence for the
    current tree. A focused-policy project may use focused evidence locally;
    otherwise the full family and current baseline are mandatory here.
    """
    base = Path(root)
    if not declared(base):
        return None
    from . import focused_unit

    focused, policy_error = focused_unit.policy(base)
    if policy_error:
        return policy_error
    if focused:
        cited, problem = focused_unit.ship_gate(base, ticket_id, events)
        if cited:
            return problem
    baseline, error = load_baseline(base)
    if error:
        return f"the declared core-unit family has no usable baseline: {error}"
    cycle = _current_cycle(ticket_id, events)
    if cycle is None:
        return f"{ticket_id} has no current VERIFY cycle to carry core-unit evidence"
    cited = None
    for event in reversed(cycle):
        if event.get("ticket") != ticket_id or event.get("taxonomy") != "RUN":
            continue
        cited = parse_evidence(event.get("text", ""))
        if cited is not None:
            break
    if cited is None:
        return (
            f"the current VERIFY cycle of {ticket_id} names no run of the declared "
            f"core-unit family ({' '.join(family().command[1:])})"
        )
    path = base / cited["record"]
    try:
        if not path.resolve().is_relative_to((base / RECORD_DIR_REL).resolve()):
            return f"cited record {cited['record']} is outside {RECORD_DIR_REL}"
        if _sha256_file(path) != cited["sha"]:
            return f"cited record {cited['record']} does not match its sha256"
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"cited record {cited['record']} is unreadable: {exc}"
    if record.get("family") != FAMILY_NAME or record.get("schema") != SCHEMA_VERSION:
        return f"cited record {cited['record']} is not a {FAMILY_NAME!r} family record"
    if issue := full_scope_problem(record):
        return issue
    verdict = judge(record, baseline["red"])
    if verdict["verdict"] != "PASS":
        return f"cited core-unit run is not admissible: {'; '.join(verdict['problems'])}"
    if record.get("baseline_sha256") != baseline_digest(base):
        return "cited core-unit run was judged against a different baseline"
    if record.get("fingerprint") != tree_fingerprint(base):
        return (
            "cited core-unit run tested a different tree: the working tree "
            f"(outside {', '.join(FINGERPRINT_EXCLUDED)}) changed after it ran"
        )
    from .verification_cache import compatible, incompatibility, replay_supported

    if not compatible(base, record.get("verification_identity")):
        reason = incompatibility(record.get("verification_identity"))
        message = ("cited core-unit run has missing or incompatible "
                   "verification environment identity")
        return message + (f" ({reason})" if reason else "")
    if not replay_supported(record["verification_identity"]):
        return "cited core-unit run has unresolved verification runtime dependencies"
    return None


def main(argv: list[str] | None = None) -> int:
    """CLI; run as ``python tools/core_unit.py`` (the package uses relative imports)."""
    import argparse

    parser = argparse.ArgumentParser(prog="core_unit.py", description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    evidence = sub.add_parser("evidence", help="run the family and cite it in the ticket's LOG")
    evidence.add_argument("ticket")
    evidence.add_argument("--project-root", default=".")
    evidence.add_argument("--agent")
    evidence.add_argument("--timeout", type=int)
    evidence.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        help="concurrent shards of the one discovery (1 = the declared command, whole)",
    )
    evidence.add_argument(
        "--fresh", action="store_true", help="run even when a PASS record of this tree exists"
    )
    focused = sub.add_parser(
        "focused", help="bounded ticket checks; full evidence is still required to publish"
    )
    focused.add_argument("ticket")
    focused.add_argument("--project-root", default=".")
    focused.add_argument("--agent")
    focused.add_argument(
        "--pattern", action="append", required=True,
        help="test filename/glob in tools/; repeat for direct consumers",
    )
    focused.add_argument(
        "--timeout", type=int, default=300, help="total local test budget, 1..300 seconds"
    )
    focused.add_argument("--fresh", action="store_true")
    impact = sub.add_parser("impact", help="conservative impact plan or scoped execution")
    impact.add_argument("ticket")
    impact.add_argument("--project-root", default=".")
    impact.add_argument("--agent")
    impact.add_argument("--changed", action="append",
                        help="explicit changed path; default: Git delta")
    impact.add_argument("--plan", action="store_true",
                        help="read-only; never executes or cites a check")
    impact.add_argument("--timeout", type=int, default=300)
    impact.add_argument("--fresh", action="store_true")
    baseline = sub.add_parser("baseline", help="record the family's current red set")
    baseline.add_argument("--project-root", default=".")
    baseline.add_argument("--from-record", help="a record path to take the red set from")
    baseline.add_argument(
        "--grow",
        metavar="REASON",
        help="required when the new baseline adds red ids the old one lacks",
    )
    baseline.add_argument("--timeout", type=int)
    baseline.add_argument("--jobs", type=int, default=DEFAULT_JOBS)
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()

    if args.command == "impact":
        from .verification_impact import command

        return command(root, args)
    if args.command == "baseline":
        return _baseline(root, args)
    if args.command == "focused":
        from .focused_unit import evidence as focused_evidence

        return focused_evidence(root, args)
    return _evidence(root, args)


def _emit(payload: dict) -> int:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


def _baseline(root: Path, args) -> int:
    if args.from_record:
        record = json.loads((root / args.from_record).read_text(encoding="utf-8"))
        run = {key: record.get(key) for key in ("status", "exit_code", "ran", "red", "command")}
    else:
        from .inflight import holding

        with holding(root, "", "core_unit baseline"):
            run = run_family(root, timeout=args.timeout, jobs=args.jobs)
        keep_durations(root, run.get("module_durations_s") or {})
    if run["status"] not in ("PASS", "FAIL") or not run["ran"]:
        return _emit({"ok": False, "detail": "the family did not complete", "run": run})
    old, _error = load_baseline(root)
    grown = sorted(set(run["red"]) - set((old or {}).get("red") or []))
    if old is not None and grown and not args.grow:
        return _emit(
            {"ok": False, "detail": "baseline would grow; pass --grow REASON", "grown": grown}
        )
    data = {
        "schema": SCHEMA_VERSION,
        "family": FAMILY_NAME,
        "command": run["command"],
        "recorded_at": _git_head(root),
        "ran": run["ran"],
        "grown_because": args.grow if grown else None,
        "red": sorted(run["red"]),
    }
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    (root / BASELINE_REL).write_text(text, encoding="utf-8")
    return _emit({"ok": True, "red": len(data["red"]), "grown": grown})


class _EvidenceIncomplete(ValueError):
    def __init__(self, payload):
        super().__init__(payload["detail"])
        self.payload = payload


def _produce_evidence(root: Path, args, fingerprint: str, expected: dict) -> dict:
    from .inflight import holding

    with holding(root, args.ticket, "core_unit evidence"):
        for attempts in range(1, EVIDENCE_DRIFT_RETRIES + 1):
            run = run_family(root, timeout=args.timeout, jobs=args.jobs)
            run.setdefault("verification_identity", expected)
            keep_durations(root, run.get("module_durations_s") or {})
            written = write_record(root, run, run.get("fingerprint") or fingerprint)
            keep_red_sections(root, written["path"], run.get("sections") or {})
            written["sandboxes_leaked"] = run.get("sandboxes_leaked") or []
            if tree_fingerprint(root) == written["record"]["fingerprint"]:
                return written
        raise _EvidenceIncomplete({
            "ok": False,
            "detail": (
                "the working tree changed after the family's copy was taken, "
                f"and kept changing across {attempts} snapshots; the record describes "
                "the copy that ran and is not cited. Remove the drift and request "
                "evidence of the stable generation."
            ),
            "verdict": written["record"]["verdict"], "record": written["path"],
            "attempts": attempts,
        })


def _evidence(root: Path, args) -> int:
    request_started = time.monotonic()
    request_started_ns = time.time_ns()
    from . import operations
    from .state import parse_state
    from .verification_cache import capture, compatible, single_flight

    _baseline_data, error = load_baseline(root)
    if error:
        return _emit({"ok": False, "detail": error})
    state = parse_state((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
    agent = args.agent or state.get("agent") or "unknown"
    board = (root / ".saipen/BOARD.md").read_text(encoding="utf-8")
    refusal = operations._active_claim_refusal(state, board, agent)
    if refusal is not None:
        return _emit(refusal.to_dict())
    fingerprint = tree_fingerprint(root)
    try:
        expected = capture(root, verification_configuration(timeout=args.timeout, jobs=args.jobs))
        written = None if args.fresh else reusable_record(
            root, fingerprint, verification_identity=expected
        )
        identity = {"family": FAMILY_NAME, "fingerprint": fingerprint,
                    "verification_identity": expected}
        with single_flight(root, identity, fresh=args.fresh, available=written,
                           request_started_ns=request_started_ns,
                           request_started_monotonic=request_started,
                           consumer=args.ticket) as flight:
            if flight.written is None:
                if tree_fingerprint(root) != fingerprint:
                    raise ValueError("source generation changed while waiting for verification")
                flight.publish(_produce_evidence(root, args, fingerprint, expected))
            written = flight.written
            reused, joined = flight.reused, flight.joined
            if not compatible(root, written["record"].get("verification_identity")):
                raise ValueError("verification environment changed before citation")
            result = cite_evidence(root, agent, args.ticket, evidence_line(written))
    except _EvidenceIncomplete as exc:
        return _emit(exc.payload)
    except (OSError, ValueError, TimeoutError) as exc:
        return _emit({"ok": False, "detail": str(exc)})
    record = written["record"]
    return _emit(
        {
            "ok": result.ok and record["verdict"] == "PASS",
            "verdict": record["verdict"],
            "ran": record["ran"],
            "red": len(record["red"]),
            "new_red": record["new_red"],
            "fixed": record["fixed"],
            "problems": record["problems"],
            "record": written["path"],
            "reused": reused,
            "shared": joined,
            "request_wall_s": round(time.monotonic() - request_started, 6),
            "checkpoint": result.code,
            "checkpoint_detail": result.message or None,
            # T-1505: a sandbox a process still held; a later run sweeps it.
            "sandboxes_leaked": written.get("sandboxes_leaked") or [],
        }
    )


def cite_evidence(root: Path, agent: str, ticket: str, line: str):
    """Replan only a stale canonical citation; never rerun its tested subject."""
    from . import operations

    for _attempt in range(3):
        result = operations.checkpoint(root, agent, "RUN", ticket, line)
        if result.code != "STALE_STATE":
            break
    return result
