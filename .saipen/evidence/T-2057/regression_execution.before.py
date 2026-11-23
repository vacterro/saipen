"""Measured active VERIFY pairs; legacy checkpoint arithmetic remains typed as attested."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from . import operations as ops
from .attempt import build_attempts
from .capability import may_mutate, negotiate_capability
from .journal import hash_bytes, hash_source_identity, semantic_receipts_for_operation_safe
from .log import _hand_authored, _is_verify_boundary
from .paths import (
    project_lineage_identity,
    prove_owned_dir_chain,
    prove_owned_regular,
    read_bound_regular_bytes,
    update_digest_regular_bytes,
)
from .plan import TargetPlan, apply_plan, build_plan
from .process_tree import run
from .result import Result
from .state import patch_state

OPERATION = "regression_execution"
PROFILE = "executed"
MAX_BYTES = 32 * 1024 * 1024
FORMATS = frozenset({"unittest", "pytest", "tap", "playwright-json"})
FIELDS = frozenset(
    {"schema", "command", "format", "context", "oracle_files", "subject_files", "before", "timeout"}
)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _unique(pairs):
    found = {}
    for key, value in pairs:
        if key in found:
            raise ValueError("duplicate JSON field: " + key)
        found[key] = value
    return found


def _relative(value):
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError("a canonical project-relative path is required")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in (".", "..") for part in value.split("/")):
        raise ValueError("path leaves the owned project")
    return str(path)


def _read(root, relative, *, max_bytes=MAX_BYTES):
    relative = _relative(relative)
    path = root / relative
    prove_owned_dir_chain(path.parent, ownership_root=root, kind="regression input")
    info = prove_owned_regular(path, kind="regression input")
    return read_bound_regular_bytes(path, info, max_bytes=max_bytes)


def _paths(values, *, allow_empty=False):
    if not isinstance(values, list) or (not values and not allow_empty) or len(values) > 256:
        raise ValueError("a nonempty bounded path list is required")
    result = [_relative(value) for value in values]
    if len({value.casefold() for value in result}) != len(result):
        raise ValueError("duplicate or case-aliased input path")
    if any(value.split("/")[0].casefold() in (".git", ".saipen") for value in result):
        raise ValueError("canonical memory and Git are not execution subjects")
    return result


def _context(root, paths, *, allow_missing=False, required=(), reader=None, on_path=None):
    from .test_runner import _ignore_copy

    files = {}
    visited = set()
    pending = list(paths)
    explicit = (*paths, *required)
    cache_scopes = [
        relative for relative in paths
        if any(part in _ignore_copy("", [part]) for part in PurePosixPath(relative).parts)
    ]
    while pending:
        relative = pending.pop()
        if relative in visited:
            continue
        visited.add(relative)
        if len(visited) > 100000:
            raise ValueError("execution context exceeds its bounded path count")
        if on_path is not None:
            on_path(relative)
        path = root / relative
        prove_owned_dir_chain(path.parent, ownership_root=root, kind="regression context")
        try:
            info = path.lstat()
        except FileNotFoundError:
            if not allow_missing:
                raise
            files[relative] = reader(relative) if reader is not None else None
            continue
        if (
            stat.S_ISDIR(info.st_mode)
            and not path.is_symlink()
            and not (getattr(info, "st_file_attributes", 0) & 0x400)
        ):
            children = []
            for child in path.iterdir():
                if on_path is not None:
                    on_path(child.relative_to(root).as_posix())
                children.append(child)
                if len(children) + len(visited) + len(pending) > 100000:
                    raise ValueError("execution context exceeds its bounded path count")
            ignored = set() if any(
                relative == scope or relative.startswith(scope + "/") for scope in cache_scopes
            ) else _ignore_copy(str(path), [child.name for child in children])
            for child in children:
                child_relative = child.relative_to(root).as_posix()
                if child.name not in ignored or any(
                    value == child_relative or value.startswith(child_relative + "/")
                    for value in explicit
                ):
                    pending.append(child_relative)
        else:
            files[relative] = reader(relative) if reader is not None else _read(root, relative)
        if len(files) + len(pending) > 100000:
            raise ValueError("execution context exceeds its bounded file count")
    if not files:
        raise ValueError("execution context is empty")
    return files


def _manifest(files):
    return {key: _sha(value) if value is not None else None for key, value in sorted(files.items())}


def execution_environment():
    """The one environment every verified command runs under.

    No SAIPEN_* variable crosses into a verifier, bytecode writing is off and
    the capability is explicitly no-publish, so a check can neither observe
    nor inherit session authority.
    """
    from .test_runner import VERIFIER_DIAGNOSTIC_ENV

    environment = {
        key: item for key, item in os.environ.items()
        if not key.startswith("SAIPEN_") and key not in VERIFIER_DIAGNOSTIC_ENV
    }
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["SAIPEN_CAPABILITY"] = "no-publish"
    return environment


def _runtime(command):
    executable = sys.executable if command[0] == "{python}" else shutil.which(command[0])
    if not executable:
        raise ValueError("verifier runtime is unavailable")
    executable = Path(executable).absolute()
    if os.name == "nt" and executable.suffix.lower() != ".exe":
        raise ValueError("use a native executable with argv, not a shell shim")
    info = prove_owned_regular(executable, kind="verifier runtime")
    digest = hashlib.sha256()
    update_digest_regular_bytes(executable, info, digest)
    runtime = {"path": str(executable), "sha256": digest.hexdigest()}
    argv = [str(executable), *command[1:]]
    return runtime, argv, execution_environment()


def _load(root, path, *, closed=False):
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        raise ValueError("contract must be inside the owned project") from None
    if not relative.startswith(".saipen/evidence/"):
        raise ValueError("contract must be under project evidence")
    raw = _read(root, relative)
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    fields = FIELDS - {"before"} if closed else FIELDS
    if not isinstance(value, dict) or set(value) != fields or type(value["schema"]) is not int:
        raise ValueError("unsupported or incomplete regression execution contract")
    if value["schema"] != 1 or value["format"] not in FORMATS:
        raise ValueError("unrecognized verifier format/schema")
    if type(value["timeout"]) is not int or not 1 <= value["timeout"] <= 5400:
        raise ValueError("timeout must be 1..5400 seconds")
    command = value["command"]
    if (
        not isinstance(command, list)
        or not 2 <= len(command) <= 64
        or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in command)
    ):
        raise ValueError("command requires bounded argv; caller verdicts are not inputs")
    oracle = _paths(value["oracle_files"])
    # closed mode measures a CURRENT check (a focused re-verification or an
    # external-implementation check against the installed bytes), not a local
    # implementation delta, so a contract there may name no subject files.
    subjects = _paths(value["subject_files"], allow_empty=closed)
    context = _context(root, _paths(value["context"]), allow_missing=closed,
                       required=(*oracle, *subjects))
    if set(oracle) & set(subjects) or not set(oracle + subjects) <= set(context):
        raise ValueError("oracle/subject must be disjoint files present in context")
    if any(context[key] is None for key in oracle):
        raise ValueError("verifier input is missing")
    before = {} if closed else value["before"]
    if not isinstance(before, dict) or (not closed and set(before) != set(subjects)):
        raise ValueError("before must name exactly the subject files")
    prior = {}
    for target, carrier in before.items():
        if carrier is None:
            prior[target] = None
        else:
            normalized_carrier = _relative(carrier)
            if not normalized_carrier.startswith(".saipen/evidence/"):
                raise ValueError("pre-fix material must be preserved in project evidence")
            prior[target] = _read(root, normalized_carrier)
    current = {key: context[key] for key in subjects}
    if not closed and _manifest(current) == _manifest(prior):
        raise ValueError("SUBJECT_UNCHANGED: no material implementation difference")
    runtime, argv, environment = _runtime(command)
    verifier = _sha(
        _json(
            {
                "command": command,
                "format": value["format"],
                "timeout": value["timeout"],
                "runtime": {**runtime, "path": os.path.normcase(runtime["path"])},
                "oracle": {key: _sha(context[key]) for key in oracle},
                "environment_digest": _sha(_json(environment)),
            }
        )
    )
    return {
        "contract": value,
        "contract_path": relative,
        "contract_raw": raw,
        "context": context,
        "prior": prior,
        "current": current,
        "argv": argv,
        "runtime": runtime,
        "verifier": verifier,
        "environment": environment,
    }


def _binding(root, ticket, agent, docs, state):
    if state.get("task") != ticket:
        raise ValueError("execution belongs to the active Work")
    refused = ops._active_claim_refusal(state, docs["board"].text_norm, agent)
    if refused is not None:
        raise ValueError(refused.message)
    events = docs["_history"].events
    boundaries = [
        event["event"]
        for event in events
        if event.get("ticket") == ticket
        and event.get("taxonomy") == "RUN"
        and not _hand_authored(event)
        and _is_verify_boundary(event)
    ]
    if not boundaries:
        raise ValueError("no canonical VERIFY boundary")
    attempts, errors = build_attempts(events)
    if errors:
        raise ValueError("invalid Attempt history")
    own = [item for item in attempts.values() if item.get("ticket") == ticket]
    active = [item for item in own if item.get("close_event") is None]
    if len(active) > 1:
        raise ValueError("ambiguous producing Attempt")
    lineage = project_lineage_identity(root)
    if not lineage:
        raise ValueError("canonical project lineage is required")
    fields = ops.parse_board(docs["board"].text_norm)["tickets"][ticket].get("fields", {})
    source_receipts = {}
    for receipt_id in sorted(set(re.findall(r"SRC-\d+", str(fields.get("source_receipts", ""))))):
        from . import intake

        source = intake.status(root, receipt_id)
        if not source.get("ok") or not source.get("source_sha256"):
            raise ValueError("unavailable Source identity: " + receipt_id)
        contract = intake._read_contract(root, receipt_id)
        source_receipts[receipt_id] = {
            "body_sha256": source["source_sha256"],
            "contract_sha256": _sha(_json(contract)),
        }
    return {
        "project_identity": ops._identity(root),
        "project_lineage": lineage,
        "ticket": ticket,
        "agent": agent,
        "verify_boundary": boundaries[-1],
        "attempt": active[0]["id"] if active else None,
        "latest_attempt_open": max((item["open_event"] for item in own), default=0),
        "source_identity": hash_source_identity(root),
        "acceptance_sha256": _sha(str(fields.get("verify", "")).encode("utf-8")),
        "source_receipts": source_receipts,
    }


def parse_summary(body, format_name):
    """A completed, nonzero test execution; a process exit alone is not a check."""
    if format_name not in FORMATS:
        raise ValueError("unrecognized verifier summary format")
    if format_name == "unittest":
        counts = re.findall(r"^Ran (\d+) tests? in ", body, re.MULTILINE)
        finals = re.findall(r"^(OK|FAILED)(?: \(([^\n]*)\))?\s*$", body, re.MULTILINE)
        if len(counts) != 1 or len(finals) != 1:
            raise ValueError("no unambiguous completed unittest summary")
        ran = int(counts[0])
        bad = sum(
            int(value)
            for value in re.findall(r"(?:failures|errors|unexpected successes)=(\d+)", finals[0][1])
        )
        skipped = sum(int(value) for value in re.findall(r"skipped=(\d+)", finals[0][1]))
        if finals[0][0] == "FAILED" and not bad:
            raise ValueError("failure summary contains no failing test")
    elif format_name == "tap":
        values = {}
        for key in ("tests", "pass", "fail", "skipped", "cancelled"):
            found = re.findall(r"^# " + key + r" (\d+)\s*$", body, re.MULTILINE)
            if len(found) != 1:
                raise ValueError("no unambiguous completed TAP summary")
            values[key] = int(found[0])
        ran, bad, skipped = values["tests"], values["fail"] + values["cancelled"], values["skipped"]
        if values["pass"] + bad + skipped != ran:
            raise ValueError("contradictory TAP totals")
    elif format_name == "playwright-json":
        value = json.loads(body, object_pairs_hook=_unique)
        numbers = value.get("stats") if isinstance(value, dict) else None
        if not isinstance(numbers, dict) or any(
            type(numbers.get(key)) is not int
            for key in ("expected", "unexpected", "skipped", "flaky")
        ):
            raise ValueError("invalid Playwright test totals")
        if numbers["flaky"] or value.get("errors"):
            raise ValueError("flaky/startup error cannot prove a regression pair")
        if any(numbers[key] < 0 for key in ("expected", "unexpected", "skipped", "flaky")):
            raise ValueError("negative test totals")
        bad, skipped = numbers["unexpected"], numbers["skipped"]
        ran = numbers["expected"] + bad + skipped
    else:
        matches = re.findall(r"^=+ (.+?) in [\d.]+s(?: \([^\n]*\))? =+\s*$", body, re.MULTILINE)
        if len(matches) != 1:
            raise ValueError("no unambiguous completed pytest summary")
        totals = {
            key: int(number)
            for number, key in re.findall(
                r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed)", matches[0]
            )
        }
        bad = (
            totals.get("failed", 0)
            + totals.get("error", 0)
            + totals.get("errors", 0)
            + totals.get("xpassed", 0)
        )
        skipped = totals.get("skipped", 0) + totals.get("xfailed", 0)
        ran = totals.get("passed", 0) + bad + skipped
    if ran <= 0 or ran <= skipped:
        raise ValueError("zero executed tests cannot prove a pair")
    return {"ran": ran, "failed": bad, "skipped": skipped}


def _measure(material, stage, subject):
    temp_root = Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix="saipen-regression-", dir=temp_root) as temporary:
        sandbox = Path(temporary).resolve()
        if not sandbox.is_relative_to(temp_root):
            raise ValueError("temporary execution scope escaped")
        files = {**material["context"], **subject}
        for relative, raw in files.items():
            if raw is None:
                continue
            target = sandbox / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        env = material["environment"]
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (sandbox / ".stdout").open("wb") as stdout, (sandbox / ".stderr").open("wb") as stderr:
            result = run(
                material["argv"],
                cwd=sandbox,
                env=env,
                stdout=stdout,
                stderr=stderr,
                timeout=material["contract"]["timeout"],
            )
        finished = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for relative, raw in files.items():
            target = sandbox / relative
            if raw is None:
                if target.exists():
                    raise ValueError("pre-fix absence changed during execution")
            elif _read(sandbox, relative) != raw:
                raise ValueError("subject/oracle/context moved during execution")
        out = _read(sandbox, ".stdout").decode("utf-8", errors="replace")
        err = _read(sandbox, ".stderr").decode("utf-8", errors="replace")
        summary = parse_summary(
            err if material["contract"]["format"] == "unittest" else out,
            material["contract"]["format"],
        )
        return {
            "stage": stage,
            "started_utc": started,
            "finished_utc": finished,
            "exit_code": result.returncode,
            "stdout": out,
            "stderr": err,
            **summary,
        }


def _records(root):
    records, errors = semantic_receipts_for_operation_safe(root, OPERATION)
    if errors:
        raise ValueError("regression receipt journal is corrupt: " + "; ".join(errors[:2]))
    result = []
    for receipt in records:
        if receipt.get("status") != "COMMITTED":
            continue
        meta = receipt.get("receipt_metadata") or {}
        relative = meta.get("regression_record")
        if not isinstance(relative, str) or not relative.startswith(".saipen/evidence/regression/"):
            raise ValueError("regression receipt has no owned evidence carrier")
        raw = _read(root, relative)
        if _sha(raw) != meta.get("regression_sha256"):
            raise ValueError("regression execution receipt integrity mismatch")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
        if value.get("op_id") != receipt.get("op_id") or value.get("evidence_class") != PROFILE:
            raise ValueError("unrecognized execution receipt identity")
        result.append((receipt, value, relative))
    return result


def authenticated_record(root, relative):
    """Return a current executed regression record only with its committed journal proof.

    A JSON file with PASS fields is not evidence that a test ran. This reader
    binds the exact carrier to the engine's committed operation and rechecks
    its exact current verifier inputs before Source coverage may consume it.
    """
    root = Path(root)
    relative = _relative(relative)
    if not relative.startswith(".saipen/evidence/regression/"):
        return None
    for _receipt, value, carrier in _records(root):
        if carrier != relative:
            continue
        if value.get("evidence_class") != PROFILE:
            return None
        if (
            (value.get("before") or {}).get("result") != "FAIL"
            or (value.get("after") or {}).get("result") != "PASS"
            or value.get("project_lineage") != project_lineage_identity(root)
        ):
            return None
        try:
            material = _load(root, value["contract_path"])
            if (
                _sha(material["contract_raw"]) == value.get("contract_sha256")
                and material["verifier"] == value.get("verifier")
                and _sha(_json(_manifest(material["context"])))
                == value.get("context_digest")
                and _sha(_json(_manifest(material["current"])))
                == (value.get("after") or {}).get("subject")
            ):
                return value
        except (OSError, ValueError, KeyError, TypeError):
            return None
    return None


def oracle_files_for_record(root, record):
    """Return the exact oracle paths bound to an authenticated execution."""
    path = _relative(record["contract_path"])
    raw = _read(Path(root), path)
    if _sha(raw) != record.get("contract_sha256"):
        raise ValueError("regression acceptance contract changed after execution")
    contract = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    return set(_paths(contract["oracle_files"]))


def evidence_gate(root, ticket, docs, state):
    """Consume committed execution, rechecking authority and exact current inputs."""
    try:
        binding = _binding(Path(root), ticket, str(state.get("agent") or ""), docs, state)
        stored = _records(Path(root))
        own = [
            event
            for event in docs["_history"].events
            if event.get("ticket") == ticket
            and event.get("taxonomy") == "RUN"
            and not _hand_authored(event)
            and event.get("event", 0) >= binding["verify_boundary"]
            and event.get("text", "").startswith("REGRESSION-EVIDENCE ")
        ]
        if len(own) < 2 or own[-2].get("op_id") != own[-1].get("op_id"):
            return "UNRECOGNIZED_VERIFIER: executed profile has no measured regression receipt"
        producing = own[-1].get("op_id")
        candidates = [item for item in stored if item[0].get("op_id") == producing]
        if len(candidates) != 1 or candidates[0][1].get("ticket") != ticket:
            return "UNRECOGNIZED_VERIFIER: latest pair is not a registered execution"
        receipt, value, _ = candidates[0]
        if value.get("attempt") is not None and binding["attempt"] is None:
            attempts, errors = build_attempts(docs["_history"].events)
            produced = attempts.get(value["attempt"])
            if (
                not errors
                and produced
                and produced.get("result") == "candidate"
                and produced.get("open_event") == binding["latest_attempt_open"]
                and produced.get("close_event", 0) > own[-1]["event"]
            ):
                binding["attempt"] = value["attempt"]
        for key in (
            "project_identity",
            "project_lineage",
            "verify_boundary",
            "attempt",
            "latest_attempt_open",
            "source_identity",
            "acceptance_sha256",
            "source_receipts",
        ):
            if value.get(key) != binding[key]:
                return "STALE_REGRESSION_EVIDENCE: execution binding changed: " + key
        material = _load(Path(root), Path(root) / value["contract_path"])
        verifier_matches = material["verifier"] == value["after"]["verifier"]
        if (
            not verifier_matches
            or _sha(material["contract_raw"]) != value.get("contract_sha256")
            or _sha(_json(_manifest(material["prior"]))) != value["before"]["subject"]
            or _sha(_json(_manifest(material["context"]))) != value["context_digest"]
            or _sha(_json(_manifest(material["current"]))) != value["after"]["subject"]
        ):
            return "STALE_REGRESSION_EVIDENCE: verifier or subject bytes changed"
        if len(own) < 2 or [event.get("op_id") for event in own[-2:]] != [receipt["op_id"]] * 2:
            return "UNRECOGNIZED_VERIFIER: latest pair is not the measured execution"
        return None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return "REGRESSION_EXECUTION_INVALID: " + str(exc)


def _derive_request_clauses(root, board, ticket):
    """Derive the request clause a linked request receipt still lacks (T-1771).

    The binding below freezes each linked receipt's Contract digest. A receipt
    captured by `saipen user-request` holds no clause until its request clause
    is derived, and the closure path derives it (`ensure_request_clause`) --
    after the measurement -- so the first finish moved the binding it checked
    and refused STALE_REGRESSION_EVIDENCE, with no way back to VERIFY but a
    rebuild (_SAIRELAY T-8; SRC-248 R004). The clause is the operator's own
    request text and is derived the same way wherever it is derived; deriving
    it before the binding is taken measures the Contract the finish will read.
    Returns whether anything was written.
    """
    from . import intake

    fields = board["tickets"][ticket].get("fields", {})
    derived = False
    for receipt_id in sorted(set(re.findall(r"SRC-\d+", str(fields.get("source_receipts", ""))))):
        contract = intake._read_contract(root, receipt_id) or {}
        if contract.get("clauses"):
            continue
        result = intake.ensure_request_clause(root, receipt_id)
        derived = derived or result.get("code") == "REQUIREMENT_ADDED"
    return derived


@ops._state_guard
def execute_pair(project_root, ticket, agent, contract_path, *, dry_run=False):
    root = Path(project_root).absolute()
    if not may_mutate(negotiate_capability()):
        return ops._refuse("CAPABILITY_READ_ONLY", "current capability forbids evidence admission")
    if negotiate_capability() == "manual-verify":
        return ops._refuse("INCOMPLETE_TICKET", "manual verification requires its operator result")
    try:
        docs, state, board, tail = ops._read(root)
        if ticket not in board["tickets"]:
            return ops._refuse("TICKET_NOT_FOUND", "Work is not on the canonical board")
        if str(board["tickets"][ticket].get("fields", {}).get("regression")) != "required":
            return ops._refuse(
                "INCOMPLETE_TICKET", "declare the regression requirement before execution"
            )
        binding = _binding(root, ticket, agent, docs, state)
        if state.get("phase") != "VERIFY":
            return ops._refuse("INCOMPLETE_TICKET", "execution requires the active VERIFY phase")
        material = _load(root, contract_path)
        if dry_run:
            return Result(True, "DRY_RUN", data={"ticket": ticket, "execution": "not_run"})
        # Derived only after the binding admitted this session as the owner of
        # the active Work and its inputs loaded: a call refused before this
        # point writes nothing.
        if _derive_request_clauses(root, board, ticket):
            docs, state, board, tail = ops._read(root)
            binding = _binding(root, ticket, agent, docs, state)
        for _, value, relative in reversed(_records(root)):
            if value.get("ticket") == ticket and all(
                value.get(key) == item for key, item in binding.items()
            ):
                if value.get("verifier") == material["verifier"] and value.get(
                    "context_digest"
                ) == _sha(_json(_manifest(material["context"]))):
                    if evidence_gate(root, ticket, docs, state) is None:
                        return Result(
                            True,
                            "ALREADY_APPLIED",
                            data={"record": relative, "evidence_class": PROFILE},
                        )
                    break
        observations = [
            _measure(material, "before", material["prior"]),
            _measure(material, "after", material["current"]),
        ]
        if not (
            observations[0]["exit_code"] == 1
            and observations[0]["failed"] > 0
            and observations[1]["exit_code"] == 0
            and observations[1]["failed"] == 0
        ):
            return ops._refuse(
                "INCOMPLETE_TICKET",
                "REGRESSION_PAIR_FAILED: measured runs do not prove FAIL then PASS",
                runs=observations,
            )
        fresh_docs, fresh_state, _, _ = ops._read(root)
        refreshed = _load(root, contract_path)
        if (
            ops._docs_preconditions(fresh_docs, "state", "board", "log")
            != ops._docs_preconditions(docs, "state", "board", "log")
            or _binding(root, ticket, agent, fresh_docs, fresh_state) != binding
            or _manifest(refreshed["context"]) != _manifest(material["context"])
            or _manifest(refreshed["prior"]) != _manifest(material["prior"])
            or refreshed["verifier"] != material["verifier"]
        ):
            return ops._refuse("STALE_STATE", "source or active authority moved during execution")
        op_id = "regression-execution-" + ops.uuid4_hex()
        before = {
            "result": "FAIL",
            "verifier": material["verifier"],
            "subject": _sha(_json(_manifest(material["prior"]))),
        }
        after = {
            "result": "PASS",
            "verifier": material["verifier"],
            "subject": _sha(_json(_manifest(material["current"]))),
        }
        value = {
            "schema": 1,
            "evidence_class": PROFILE,
            "op_id": op_id,
            **binding,
            "contract_path": material["contract_path"],
            "contract_sha256": _sha(material["contract_raw"]),
            "verifier": material["verifier"],
            "context_digest": _sha(_json(_manifest(material["context"]))),
            "before": before,
            "after": after,
            "runs": observations,
            "runtime": material["runtime"],
        }
        record = ".saipen/evidence/regression/" + op_id + ".json"
        raw = _json(value) + b"\n"
        now, utc = ops._now(), ops._utc_iso()
        lines = []
        for half in (before, after):
            event, line = ops._event_line(
                docs,
                tail,
                "RUN",
                ticket,
                agent,
                f"REGRESSION-EVIDENCE {half['result']} verifier:{half['verifier']} "
                f"subject:{half['subject']} -- measured execution {record}",
                now,
                op_id,
            )
            tail = event
            lines.append(line)
        new_log = docs["log"].text_norm.rstrip("\n") + "\n" + "\n".join(lines) + "\n"
        projected = ops._project_board_mutation(
            root,
            docs["board"].text_norm,
            lambda text: ops._ticket_fields_in_place(
                text, ticket, {"regression_evidence": PROFILE}, enforce_cap=False
            ),
            [ticket],
            op_id=op_id,
            event_id=f"E-{tail}",
            reason="bounded executed regression evidence profile",
        )
        new_board = projected.board_text
        refreshed_board, _ = ops._refresh_active_claim(new_board, state, agent, utc, root=root)
        if refreshed_board is not None:
            new_board = refreshed_board
        new_state = patch_state(
            docs["state"].text_norm, {"last_event": tail, "updated": utc, "agent": agent}
        )
        preconditions = ops._docs_preconditions(docs, "state", "board", "log")
        preconditions["."] = binding["source_identity"]
        for relative, body in material["context"].items():
            preconditions[relative] = hash_bytes(body)
        preconditions[material["contract_path"]] = hash_bytes(material["contract_raw"])
        for target, carrier in material["contract"]["before"].items():
            if carrier is not None:
                preconditions[carrier] = hash_bytes(material["prior"][target])
        targets = [
            TargetPlan(record, "generic", raw, "", hash_bytes(raw)),
            *ops._log_targets(docs, new_log),
            *projected.targets,
            ops._target(docs["board"], ".saipen/BOARD.md", "board", new_board),
            ops._target(docs["state"], ".saipen/STATE.md", "state", new_state),
        ]
        plan = build_plan(
            OPERATION,
            agent,
            binding["project_identity"],
            {"operation": OPERATION, "ticket": ticket, "verifier": material["verifier"]},
            preconditions,
            targets,
            {
                "ok": True,
                "code": "CHECKPOINTED",
                "record": record,
                "evidence_class": PROFILE,
                "event_id": f"E-{tail}",
            },
            op_id=op_id,
            receipt_metadata={
                "ticket_id": ticket,
                "regression_record": record,
                "regression_sha256": _sha(raw),
            },
        )
        return apply_plan(root, plan)
    except subprocess.TimeoutExpired:
        return ops._refuse(
            "INCOMPLETE_TICKET", "REGRESSION_EXECUTION_TIMEOUT: owned process tree reaped"
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ops._refuse("VALIDATION_FAILED", "REGRESSION_EXECUTION_INVALID: " + str(exc))
