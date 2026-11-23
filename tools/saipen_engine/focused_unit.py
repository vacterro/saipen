"""Bounded ticket checks; complete core-unit evidence remains a publication gate."""

from __future__ import annotations

import datetime
import json
import re
import sys
import time
from pathlib import Path

from . import core_unit

POLICY_REL = "tools/verification_policy.json"
POLICY = {"schema": 1, "ticket": "focused", "publication": "full"}
RECORD_DIR_REL = ".saipen/evidence/focused-unit"
MARKER = "FOCUSED-UNIT-EVIDENCE"
MAX_SECONDS = 300
_CITATION = re.compile(
    rf"^{MARKER} (?:PASS|FAIL)\b.*?record:(\S+) sha256:([0-9a-f]{{64}})\b"
)


def policy(root: Path) -> tuple[bool, str | None]:
    """Opt in explicitly. Missing preserves legacy gates; invalid fails closed."""
    path = root / POLICY_REL
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False, None
    except OSError as exc:
        return False, f"verification policy unreadable: {exc}"
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return False, f"verification policy invalid: {exc}"
    if data != POLICY or type(data.get("schema")) is not int:
        return False, f"verification policy must be exactly {POLICY}"
    return True, None


def _patterns(patterns) -> list[str]:
    if not isinstance(patterns, list) or not patterns:
        raise ValueError("at least one --pattern test_name.py is required")
    for pattern in patterns:
        if (not isinstance(pattern, str) or not pattern.startswith("test_")
                or not pattern.endswith(".py") or "/" in pattern or "\\" in pattern):
            raise ValueError("patterns must select test_*.py filenames inside tools/")
    return sorted(set(patterns))


def record_problem(root: Path, record: dict, *, verification_identity=None) -> str | None:
    if not isinstance(record, dict) or record.get("schema") != 1 \
            or record.get("family") != "focused-unit":
        return "not a focused-unit record"
    if record.get("verdict") != "PASS":
        return "focused record is not passing"
    try:
        patterns = _patterns(record.get("patterns"))
    except ValueError as exc:
        return str(exc)
    runs = record.get("runs")
    if not isinstance(runs, list) or not runs or len(runs) != len(patterns):
        return "focused record does not cover its selected patterns"
    if any(not isinstance(run, dict) for run in runs):
        return "focused record has an invalid run"
    if [run.get("pattern") for run in runs] != patterns:
        return "focused record does not cover its selected patterns"
    for run in runs:
        if (run.get("status") != "PASS" or run.get("exit_code") != 0
                or type(run.get("ran")) is not int or run["ran"] < 1):
            errors = (run.get("manifest") or {}).get("dependency_origin_errors")
            if errors and not (run.get("manifest") or {}).get("import_error_indices"):
                return "impact dependency origin mismatch: " + "; ".join(errors)
            return "focused check failed, timed out, or collected zero tests"
        verdict = core_unit.judge(run, [])
        if verdict["verdict"] != "PASS":
            return "; ".join(verdict["problems"])
    if record.get("ran") != sum(run["ran"] for run in runs):
        return "focused record test totals disagree"
    if record.get("fingerprint") != core_unit.tree_fingerprint(root):
        return "focused check tested a different tree"
    selection = record.get("impact_selection")
    tier = record.get("verification_tier")
    if tier != "IMPACT" and any(run.get("scope_kind") == "impact-subset" for run in runs):
        return "impact output has no bound selection contract"
    if tier not in (None, "FOCUSED", "IMPACT"):
        return "focused evidence cannot impersonate another verification tier"
    if selection is not None or tier == "IMPACT":
        from .verification_impact import manifest_problem, problem

        if tier != "IMPACT" or (issue := problem(root, selection)):
            return issue if tier == "IMPACT" else "impact selection has no declared tier"
        if patterns != ["test_*.py"] or len(runs) != 1:
            return "impact execution has a noncanonical discovery shape"
        if issue := manifest_problem(selection, runs[0]):
            return issue
    from .verification_cache import compatible, incompatibility
    from .verification_cache import incompatibility_detail

    if verification_identity is not None:
        if record.get("verification_identity") != verification_identity:
            return "focused check used a different verification configuration or environment"
    elif not compatible(root, record.get("verification_identity")):
        reason = incompatibility(record.get("verification_identity"))
        if reason is None:
            reason = incompatibility_detail(root, record.get("verification_identity"))
        return "focused check has missing or incompatible verification environment identity" + (
            f" ({reason})" if reason else ""
        )
    from .sandbox_scope import ScopeError, is_current, resolve as resolve_scope

    try:
        current = resolve_scope(root, patterns)
    except ScopeError as exc:
        # A validator returns a refusal; it does not raise through a gate.
        return str(exc)
    recorded_scope = record.get("sandbox_scope")
    if recorded_scope is None:
        # A record from before T-1889 copied the WHOLE tree, so it is valid
        # exactly while the manifest still asks for the whole tree. Presenting
        # it for a narrowed run would claim bytes it did carry but this run's
        # identity does not describe.
        if current["mode"] != "FULL":
            return "focused record predates sandbox scope and does not describe this run's copy"
        return None
    return is_current(recorded_scope, current)


def ship_gate(root: Path, ticket: str, events: list[dict]) -> tuple[bool, str | None]:
    """Return (citation present, problem). Full evidence remains a valid fallback."""
    cycle = core_unit._current_cycle(ticket, events) or []
    for event in reversed(cycle):
        if event.get("ticket") != ticket or event.get("taxonomy") != "RUN":
            continue
        match = _CITATION.match(str(event.get("text") or "").strip())
        if match is None:
            continue
        relative, digest = match.groups()
        path = root / relative
        try:
            if not path.resolve().is_relative_to((root / RECORD_DIR_REL).resolve()):
                return True, "focused record is outside its evidence directory"
            if core_unit._sha256_file(path) != digest:
                return True, "focused record does not match its sha256"
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return True, f"focused record unreadable: {exc}"
        return True, record_problem(root, record)
    return False, None


#: T-2122 (SRC-440 wave B): the CLOSED vocabulary of ``red_owners``
#: dispositions. An attribution outside this set must never become
#: permission to publish.
_OWNER_DISPOSITIONS = frozenset({"undecided", "resolved"})

_OWNER_TICKET_RE = re.compile(r"^T-\d+$")


def _red_owners_attribution_problem(
    baseline: dict, record: dict, root: Path | str
) -> str | None:
    """Absorbed reds authorize publication only with an owner disposition.

    Fail-closed everywhere (T-2118 + the T-2122 regression): an OPTIONAL
    ``red_owners`` map may carry ``{name: {"ticket": "T-###", "disposition":
    ...}}``. A baseline WITHOUT the field stays permissive (the documented
    pre-attribution back-compat). With the field present:

    - a non-dict ``red_owners`` value is malformed and REFUSES (it is never
      silently read as "absent" -- the pre-T-2122 fail-open hole);
    - every entry must be a dict with a well-formed ``ticket`` id;
    - ``disposition`` is mandatory, a string, and inside the CLOSED set
      ``{undecided, resolved}`` -- unknown or empty values refuse instead of
      passing as resolved (the measured WHATEVER/""-admits hole);
    - ``undecided`` refuses for any red the record carries (INV iv-2);
    - ``resolved`` additionally requires the owning ticket to be WITNESSED in
      the project journal (``[T-###]`` in ``.saipen/LOG.md``) so a fabricated
      resolution cannot authorize the bytes; a missing journal fails closed.

    The adversarial corpora live in ``tools/test_t2118_baseline_admission.py``
    and ``tools/test_t2122_red_owner_fail_closed.py``.
    """
    if "red_owners" not in baseline:
        return None
    owners = baseline.get("red_owners")
    if not isinstance(owners, dict):
        return "baseline red_owners is malformed (must be an object of owner entries)"
    carried = {name for name in (record.get("red") or [])}
    # T-2132 (Campaign VII P0-A): ``resolved`` needs a TERMINAL owner, proven
    # from BOTH canonical projections -- a closing operation event for the
    # owner ticket in ONE consistent history snapshot, and the owner row
    # projected into ``## DONE`` on the BOARD. A journal mention only proves
    # that something happened, not that the right thing happened: the
    # substring witness admitted a live DOING owner with a single RUN
    # checkpoint mention (reproduced live on 713f49c76). Both surfaces are
    # parsed at most ONCE per gate evaluation -- never re-read per owner --
    # so many resolved owners cost one snapshot, not one LOG read each.
    terminal_events: set[str] | None = None
    done_on_board: set[str] | None = None

    def _owner_terminal_projections() -> tuple[set[str], set[str]]:
        nonlocal terminal_events, done_on_board
        if terminal_events is None:
            from . import codec
            from .board import parse_board
            from .board_scrub import CLOSING_OP_CLASSES
            from .log import read_history_snapshot

            events = read_history_snapshot(root, lean=True).events
            terminal_events = {
                str(event.get("ticket"))
                for event in events
                if str(event.get("op_id") or "").startswith(CLOSING_OP_CLASSES)
            }
            board_path = Path(root) / ".saipen" / "BOARD.md"
            raw = board_path.read_bytes()
            document = codec.read_document(board_path, raw=raw)
            board = parse_board(document.text_norm)
            done_on_board = {
                str(tid)
                for tid, row in (board.get("tickets") or {}).items()
                if row.get("section") == "## DONE"
            }
        return terminal_events, done_on_board

    undecided: list[str] = []
    for name, owner in sorted(owners.items()):
        if not isinstance(name, str) or not isinstance(owner, dict):
            return f"baseline red_owners entry for {name!r} is malformed"
        ticket = owner.get("ticket")
        if not isinstance(ticket, str) or not _OWNER_TICKET_RE.match(ticket):
            return f"baseline red_owners entry for {name!r} is malformed (ticket)"
        disposition = owner.get("disposition")
        if not isinstance(disposition, str) or disposition not in _OWNER_DISPOSITIONS:
            return (
                f"baseline red_owners disposition for {name!r} is not in the "
                f"closed vocabulary {sorted(_OWNER_DISPOSITIONS)}; unknown or "
                "empty dispositions never authorize publication"
            )
        if disposition == "undecided":
            if name in carried:
                undecided.append(name)
            continue
        closing_events, done_rows = _owner_terminal_projections()
        if ticket not in closing_events or ticket not in done_rows:
            return (
                f"baseline red_owners entry for {name!r} claims a resolved owner "
                f"({ticket}) that is not terminal in the canonical projections: "
                f"journal closing-op event={'present' if ticket in closing_events else 'MISSING'}, "
                f"BOARD ## DONE row={'present' if ticket in done_rows else 'MISSING'}; "
                "an unresolved owner never authorizes publication (a journal "
                "mention is not a resolution proof -- T-2132)"
            )
    if undecided:
        return (
            "full core-unit run carries inherited red(s) with an undecided "
            "owner: " + "; ".join(undecided)
            + "; resolve the owning WIP decision or record its accepted "
            "disposition in the baseline before publishing (T-2118, SRC-437 P0)"
        )
    return None


def publication_gate(root: Path | str) -> str | None:
    """Batch boundary: a focused result NEVER proves the complete family."""
    root = Path(root)
    if not core_unit.declared(root):
        return None
    enabled, error = policy(root)
    if error or not enabled:
        return error
    fingerprint = core_unit.tree_fingerprint(root)
    baseline, error = core_unit.load_baseline(root)
    if error:
        return error
    # Newest exact-tree record wins, including red. An earlier green must not
    # hide a subsequent failure of the very same subject.
    paths = (root / core_unit.RECORD_DIR_REL).glob(f"{fingerprint[:16]}-*.json")
    for path in sorted(paths, reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return f"full core-unit record unreadable: {exc}"
        if not isinstance(record, dict):
            return "invalid full core-unit record"
        if record.get("fingerprint") != fingerprint:
            continue
        if record.get("schema") != core_unit.SCHEMA_VERSION \
                or record.get("family") != core_unit.FAMILY_NAME:
            return "publication requires a complete core-unit family record"
        if issue := core_unit.full_scope_problem(record):
            return issue
        if record.get("baseline_sha256") != core_unit.baseline_digest(root):
            return "full core-unit run used a different baseline"
        from .verification_cache import compatible, replay_supported

        if not compatible(root, record.get("verification_identity")):
            return ("full core-unit run has missing or incompatible "
                    "verification environment identity")
        if not replay_supported(record["verification_identity"]):
            return ("full core-unit verification has unresolved runtime dependencies; "
                    "publication unproven")
        if record.get("status") not in {"PASS", "FAIL"} \
                or record.get("exit_code") not in {0, 1}:
            return "full core-unit family did not complete"
        verdict = core_unit.judge(record, baseline["red"])
        if verdict["verdict"] != "PASS":
            return "full core-unit run is not admissible: " + "; ".join(verdict["problems"])
        owner_problem = _red_owners_attribution_problem(baseline, record, root)
        if owner_problem:
            return owner_problem
        return None
    return (
        "publication requires one full core-unit run of the final batch; "
        "run python tools/core_unit.py evidence <T-###> after the last content edit"
    )


def configuration(patterns, timeout, selection=None, scope=None):
    result = {"family": "focused-unit", "patterns": patterns, "timeout": timeout}
    if scope is not None:
        from .sandbox_scope import identity as scope_identity

        result["sandbox_scope"] = scope_identity(scope)
    if selection is not None:
        from .verification_impact import digest

        result.update(verification_tier="IMPACT", impact_selection_sha256=digest(selection))
    return result


def run_focused(root: Path, patterns: list[str], *, timeout: int = MAX_SECONDS,
                selection=None) -> dict:
    """Run explicit discovery patterns in one immutable, isolated snapshot."""
    from .sandbox_scope import resolve as resolve_scope
    from .test_runner import TestFamily, _ignore_copy

    started = time.monotonic()
    patterns = _patterns(patterns)
    scope = resolve_scope(root, patterns)
    from .verification_cache import capture

    mark = time.monotonic()
    verification_identity = capture(
        root, configuration(patterns, timeout, selection, scope)
    )
    identity_wall_s = time.monotonic() - mark
    if not 1 <= timeout <= MAX_SECONDS:
        raise ValueError(
            f"focused timeout must be 1..{MAX_SECONDS} seconds; use full evidence for a broad run"
        )
    if selection is None:
        from .sandbox_scope import select_modules

        _, unmatched = select_modules(root, patterns)
        if unmatched:
            raise ValueError(f"pattern {unmatched[0]!r} selects no test files")
    temporary = core_unit.new_sandbox_root(root)
    runs = []
    timings = {"execution_wall_s": 0.0,
               "environment_identity_wall_s": round(identity_wall_s, 6)}
    try:
        sandbox = temporary / "project"
        mark = time.monotonic()
        copy_metrics = core_unit.copy_tree_consistent(root, sandbox, _ignore_copy,
                                                      scope=scope)
        timings["copy_wall_s"] = round(time.monotonic() - mark, 6)
        mark = time.monotonic()
        fingerprint = core_unit.tree_fingerprint(sandbox)
        timings["hash_wall_s"] = round(time.monotonic() - mark, 6)
        if selection is not None:
            from .verification_impact import problem

            if issue := problem(sandbox, selection):
                raise ValueError(issue)
        for index, pattern in enumerate(patterns):
            remaining = int(timeout - (time.monotonic() - started))
            if remaining < 1:
                break
            command = (sys.executable, "-B", "-m", "unittest", "discover",
                       "-s", "tools", "-p", pattern, "-v")
            mark = time.monotonic()
            family = TestFamily("focused-unit", command, remaining)
            if selection is None:
                spool = temporary / f"spool-{index}"
                spool.mkdir()
                run = core_unit._run_whole(sandbox, family, spool)
            else:
                run = core_unit._run_shard(
                    sandbox, family, ("tools", "test_*.py"),
                    {"include": selection["selector_modules"], "include_import_errors": True,
                     "expected_module_paths": selection["dependency_files"]},
                    temporary,
                )
                # The full-family merge's partition flag is not a subset proof.
                # This route validates its own exact selection manifest below.
                run.pop("membership_required", None)
                run["scope_kind"] = "impact-subset"
            timings["execution_wall_s"] += time.monotonic() - mark
            runs.append({"pattern": pattern, "command": ["python", *command[1:]], **run})
            if run["status"] != "PASS" or core_unit.judge(run, [])["verdict"] != "PASS":
                break
    finally:
        mark = time.monotonic()
        reclaimed = core_unit.reclaim(temporary)
        timings["cleanup_wall_s"] = round(time.monotonic() - mark, 6)
    infrastructure = None
    if not runs:
        # T-2163 (Campaign XIII, Wave E): with no run at all the failure is
        # an infrastructure outcome -- the budget gates only execution, so
        # preparation alone consumed it -- and the record must name WHICH
        # stage ate the budget, not merely that no pattern produced a
        # verdict: the measured 1029 s FAIL said "does not cover its
        # selected patterns" and named nothing, twice, at identical cost.
        infrastructure = {
            "stage": "preparation",
            "reason": "PREPARATION_EXHAUSTED_EXECUTION_BUDGET",
            "budget_s": timeout,
            "identity_wall_s": round(identity_wall_s, 3),
            "copy_wall_s": timings["copy_wall_s"],
            "hash_wall_s": timings["hash_wall_s"],
            "cleanup_wall_s": timings.get("cleanup_wall_s"),
            "detail": (
                "no test could start: preparation consumed "
                f"{identity_wall_s:.1f} s identity capture plus "
                f"{timings['copy_wall_s']:.1f} s copy (subject "
                f"{copy_metrics['subject_copy_s']:.1f} s, canonical "
                f"{copy_metrics['canonical_copy_s']:.1f} s) plus "
                f"{timings['hash_wall_s']:.1f} s tree hash against the "
                f"{timeout} s focused budget; zero executed tests is a "
                "preparation outcome, never a subject verdict"
            ),
        }
    record = {
        "schema": 1, "family": "focused-unit", "fingerprint": fingerprint, "verdict": "PASS",
        "patterns": patterns, "runs": runs, "ran": sum(run.get("ran") or 0 for run in runs),
        "duration_s": round(time.monotonic() - started, 3),
        "timings_s": {name: round(seconds, 6) for name, seconds in timings.items()},
        "copy_metrics": copy_metrics,
        "sandbox_scope": scope,
        "verification_identity": verification_identity,
        "sandboxes_leaked": [] if reclaimed else [str(temporary)],
    }
    if selection is not None:
        record.update(verification_tier="IMPACT", impact_selection=selection)
    if infrastructure is not None:
        record["infrastructure"] = infrastructure
    problem = record_problem(root, record)
    if problem and infrastructure is not None:
        # T-2163 (Campaign XIII, Wave E): the coverage complaint alone is the
        # ambiguously-attributed failure the audit flagged; the measured stage
        # split is what the next decision actually needs.
        problem = f"{problem} (infrastructure: {infrastructure['detail']})"
    verdict = "FAIL" if problem else "PASS"
    return {**record, "verdict": verdict, "status": verdict, "problem": problem}


def evidence(root: Path, args) -> int:
    request_started = time.monotonic()
    request_started_ns = time.time_ns()
    from . import operations
    from .inflight import holding
    from .state import parse_state
    from .verification_cache import capture, replay_supported, single_flight

    try:
        patterns = _patterns(args.pattern)
        selection = getattr(args, "impact_selection", None)
        if selection is not None:
            from .verification_impact import problem

            if issue := problem(root, selection):
                raise ValueError(issue)
        # Night-8 preflight: refuse a request whose budget is already proven
        # dead on arrival (or whose selection matches no test at all) BEFORE
        # the sandbox copy is paid for. Every refusal cites measured
        # evidence of this exact scope; no evidence means proceed.
        from . import preflight

        for problem in (preflight.selection_problem(root, patterns),
                        preflight.budget_problem(root, patterns, args.timeout)):
            if problem is not None:
                return core_unit._emit({"ok": False, **problem})
        fingerprint = core_unit.tree_fingerprint(root)
        # Night-9: measured copy history is an ADVISORY carried on the result,
        # never an admission gate. It is bound to this selection and this tree.
        advisory = preflight.timing_advisory(
            root, patterns, args.timeout, fingerprint=fingerprint
        )
        state = parse_state((root / ".saipen/STATE.md").read_text(encoding="utf-8"))
        agent = args.agent or state.get("agent") or "unknown"
        board = (root / ".saipen/BOARD.md").read_text(encoding="utf-8")
        refusal = operations._active_claim_refusal(state, board, agent)
        if refusal is not None:
            return core_unit._emit(refusal.to_dict())
        # T-1889: the reuse decision is part of the identity. A record made from
        # a NARROWED sandbox must never be presented for a manifest that now
        # declares another tree -- that pass describes a copy this run would not
        # make (INV-20).
        from .sandbox_scope import resolve as resolve_scope

        scope = resolve_scope(root, patterns)
        expected = capture(root, configuration(patterns, args.timeout, selection, scope))
        written = None
        if not args.fresh and replay_supported(expected):
            paths = (root / RECORD_DIR_REL).glob(f"{fingerprint[:16]}-*.json")
            for path in sorted(paths, reverse=True):
                record = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(record, dict):
                    raise ValueError(f"invalid focused record: {path}")
                if (record.get("patterns") == patterns
                        and record.get("verification_identity") == expected):
                    if record_problem(root, record, verification_identity=expected) is None:
                        written = (path, record)
                    elif record.get("ran") == 0 and not record.get("runs"):
                        # T-2163 (Campaign XIII, Wave E): the newest record of
                        # THIS exact tree, identity and selection paid for its
                        # preparation and executed zero tests. Re-running the
                        # identical request re-pays the identical cost (the
                        # measured session burned 2 x 1029 s on this shape), so
                        # an automatic repeat is refused until a condition
                        # changes; --fresh is the deliberate override.
                        prior = (record.get("infrastructure") or {}).get("detail") or (
                            "a prior record of this exact tree, identity and "
                            "selection executed zero tests"
                        )
                        return core_unit._emit({
                            "ok": False,
                            "code": "IDENTICAL_INFRASTRUCTURE_FAILURE",
                            "detail": (
                                "the previous run of this exact selection, tree "
                                "and verification identity paid for its "
                                "preparation and executed zero tests; repeating "
                                "it with conditions unchanged re-pays the same "
                                f"cost -- {prior}; change the condition "
                                "(declare the sandbox scope in "
                                "tools/sandbox_scope.json, raise the focused "
                                "budget up to the cap, or quiet the host) or "
                                "request --fresh"
                            ),
                            "prior": path.relative_to(root).as_posix(),
                            "prior_duration_s": record.get("duration_s"),
                            "prior_timings_s": record.get("timings_s"),
                        })
                    break
        identity = {"family": "focused-unit", "fingerprint": fingerprint,
                    "verification_identity": expected}
        available = None if written is None else {
            "path": written[0].relative_to(root).as_posix(),
            "sha256": core_unit._sha256_file(written[0]), "record": written[1],
        }
        with single_flight(root, identity, fresh=args.fresh, timeout=args.timeout + 120,
                           available=available, request_started_ns=request_started_ns,
                           request_started_monotonic=request_started,
                           consumer=args.ticket) as flight:
            if flight.written is None:
                if core_unit.tree_fingerprint(root) != fingerprint:
                    raise ValueError("source generation changed while waiting for verification")
                with holding(root, args.ticket, "focused-unit evidence"):
                    record = run_focused(root, patterns, timeout=args.timeout, selection=selection)
                    moment = datetime.datetime.now(datetime.timezone.utc)
                    stamp = moment.strftime("%Y%m%dT%H%M%S%fZ")
                    path = root / RECORD_DIR_REL / f"{record['fingerprint'][:16]}-{stamp}.json"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
                    flight.publish({"path": path.relative_to(root).as_posix(),
                                    "sha256": core_unit._sha256_file(path), "record": record})
            record = flight.written["record"]
            relative = flight.written["path"]
            reused, joined = flight.reused, flight.joined
            if record["verdict"] == "PASS" and (problem := record_problem(root, record)):
                raise ValueError(problem)
            confidence = "high" if record["verdict"] == "PASS" else "low"
            line = (f"{MARKER} {record['verdict']} conf: {confidence} ran:{record['ran']} "
                    f"record:{relative} sha256:{flight.written['sha256']}")
            result = core_unit.cite_evidence(root, agent, args.ticket, line)
        return core_unit._emit({"ok": result.ok and record["verdict"] == "PASS",
                                "verdict": record["verdict"], "ran": record["ran"],
                                "duration_s": record["duration_s"], "record": relative,
                                "reused": reused, "shared": joined,
                                "request_wall_s": round(time.monotonic() - request_started, 6),
                                "problem": record.get("problem"),
                                "advisory": advisory,
                                "checkpoint": result.code})
    except (OSError, ValueError, TimeoutError) as exc:
        return core_unit._emit({"ok": False, "detail": str(exc)})
