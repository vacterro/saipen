"""Engine exceptions and the closed set of stable result codes.

A weak model should reason about a CODE, not parse an essay. Every refusal the
engine can emit is named here once; `saipen/OPS.md` section 7 is the contract
these must satisfy, and `CODES` is checked against that document so a code
cannot be invented in code and left undocumented (or documented and never
implemented).
"""

from __future__ import annotations

# The closed set. OPS.md section 7 lists exactly these; adding one here without
# adding it there is drift, and the validator's [ops-owner] check says so.
CODES = frozenset({
    "STALE_STATE",
    "TICKET_NOT_FOUND",
    "TICKET_NOT_WORKABLE",
    "TICKET_ALREADY_DONE",
    "ILLEGAL_TICKET_LIFECYCLE",
    "NOT_TOP_WORKABLE",
    "ACTIVE_TICKET_MISMATCH",
    "ALREADY_CLAIMED",
    "ILLEGAL_TRANSITION",
    "ILLEGAL_PHASE",
    "WRITER_BUSY",
    "VALIDATION_FAILED",
    "RECOVERY_REQUIRED",
    "RECOVERY_CONFLICT",
    "NEEDS_REPAIR",
    "DESTRUCTIVE_CONFIRMATION_REQUIRED",
    "CONFLICT",
    "PATH_ESCAPE",
    "INVALID_ID",
    "ACTIVE_IMPROVE_CYCLE",
    "INVALID_DISPOSITION",
    "PACKAGE_INCOMPLETE",
    "MALFORMED_PACKAGE",
    "INCOMPLETE_TICKET",
    "INVALID_MANIFEST",
    # Crew executor codes (T-1003 sweep): HOME_REQUIRED tells the operator the
    # configured saipen_home is unusable (missing/invalid); CREW_BLOCKED is the
    # EXPECTED structured result when the crew circuit has no executable
    # semantic continuation -- inspection is the next action, never an
    # invented action and never a traceback.
    "HOME_REQUIRED",
    "CREW_BLOCKED",
    # CREW_NOT_READY (T-1003 sweep): the human explicitly asked to publish
    # while the crew epoch is not terminal (SC-0..SC-10 not all proven), or a
    # fresh release was requested under an active crew epoch. The refusal is
    # valid -- the crew either defers the ordinary ticket or finishes its
    # circuit first; explicit publication under a non-terminal crew is never
    # authorized by omission.
    "CREW_NOT_READY",
    # INVALID_SOURCE_HOME (T-1003 sweep): the shared-contract SOURCE is a
    # closed mandatory inventory; a broken/incomplete saipen_home refuses with
    # zero writes and zero obsolete deletion -- absence in a broken source is
    # never deletion authority.
    "INVALID_SOURCE_HOME",
    # Release executor codes (T-994)
    "STALE_PLAN",
    "RELEASE_CLOSURE_PENDING",
    "TAG_CONFLICT",
    "FIRST_PUBLISH_WAIT",
    "NO_PUBLISH_MODE",
    "SOURCE_SCOPE_MISSING",
    # T-994 / § 1: every public release refusal that is not a named
    # preflight gate collapses to ONE stable code. The diagnostic stage and
    # the underlying subprocess failure stay in `detail`/`stage` -- they must
    # never become a zoo of global codes the weak model has to parse.
    "RELEASE_FAILED",
})


class EngineError(Exception):
    """Base for every engine refusal.

    Carries a `code` from `CODES` and, where one exists, the exact executable
    next action. "operation failed" tells a cold weak model nothing; the point
    of this class is that it cannot be raised without naming which refusal it
    is.
    """

    code = "VALIDATION_FAILED"

    def __init__(self, message: str, *, code: str | None = None,
                 next_action: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        if self.code not in CODES:
            raise ValueError(
                f"{self.code!r} is not one of OPS.md's stable result codes")
        self.message = message
        self.next_action = next_action

    def __str__(self) -> str:
        tail = f"\nrun: {self.next_action}" if self.next_action else ""
        return f"REFUSE [{self.code}] {self.message}{tail}"


class ParseError(EngineError):
    """A canonical file does not match the shape CORE section 1.2 fixes.

    Raised BEFORE any mutation: a malformed BOARD/STATE/LOG must refuse rather
    than be half-understood and half-rewritten.
    """

    code = "VALIDATION_FAILED"


class StaleSnapshotError(EngineError):
    """A plan computed against one snapshot met a different one at apply time.

    Optimistic concurrency, sequential edition: the operation is refused, not
    retried silently, because the decision that produced it was made against
    state that no longer exists.
    """

    code = "STALE_STATE"
