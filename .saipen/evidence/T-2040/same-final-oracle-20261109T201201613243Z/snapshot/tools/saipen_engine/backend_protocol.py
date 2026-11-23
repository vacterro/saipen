"""The neutral vocabulary a campaign backend answers in.

A campaign drives *some* external analysis backend. Which one is a deployment
fact, not a protocol fact: no module in this package may branch on a producer
name, and `test_audit_dogfood` enforces that by scanning every module here for
one (T-1947). The status words below are therefore the ONLY thing the engine
agrees to understand, and they are spelled without naming any backend.

The rule this module exists to make possible is the repository's own, stated in
`KNOWLEDGE/roadmaps/next-2026-08-31/11_WAVE_9_SAIPAL_BRIDGE.md`:

    SAIPEN must not branch semantically on `producer == SAIPAL`

Three shapes of backend answer are distinguished, and they are not
interchangeable:

* progress -- the backend did bounded work and has more eligible work. It is
  NOT a finished objective and must not put a campaign to sleep (AUT-007).
* findings -- qualified results are ready and each one has to be offered to the
  audit transport, whose own gate decides publication.
* nothing -- a complete, honest "no new evidence", distinct from a failure.

Everything else is a failure taxonomy, split by WHO can act on it: the caller's
authority, the environment, or neither.
"""

from __future__ import annotations

#: A backend performed one bounded slice and has further eligible work.
ANALYSIS_PROGRESS = "ANALYSIS_PROGRESS"
#: Qualified findings are ready for delivery.
NEW_QUALIFIED_FINDINGS = "NEW_QUALIFIED_FINDINGS"
#: A complete answer carrying no new evidence. Not a failure.
NO_NEW_EVIDENCE = "NO_NEW_EVIDENCE"

#: The finding reached the audit transport but publication was not authorized.
STAGED_PUBLICATION = "STAGED_PUBLICATION"
#: The finding was published.
DELIVERED_PUBLICATION = "DELIVERED_PUBLICATION"

#: The backend answered, but this project is not enrolled with it.
SOURCE_NOT_ENROLLED = "SOURCE_NOT_ENROLLED"
#: The backend cannot run here at all.
RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
#: The caller lacks authority for the requested operation.
AUTHORITY_REQUIRED = "AUTHORITY_REQUIRED"
#: The backend refused the analysis itself.
ANALYSIS_BLOCKED = "ANALYSIS_BLOCKED"

#: Retrying the same call may succeed (transient).
RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
#: Retrying the same call cannot succeed.
PERMANENT_FAILURE = "PERMANENT_FAILURE"
#: The backend broke its own wire contract.
BACKEND_PROTOCOL_ERROR = "BACKEND_PROTOCOL_ERROR"
#: The backend hit a resource ceiling.
BACKEND_RESOURCE_LIMIT = "BACKEND_RESOURCE_LIMIT"


class CampaignBackend:
    """What a campaign needs from an external analysis backend. Nothing more.

    A concrete backend lives OUTSIDE `saipen_engine/`. This class only states
    the two operations the driver calls and the shape each answer takes, so
    `campaign.py` can hold a backend it cannot name.
    """

    def discover(self, project_root):  # pragma: no cover - protocol
        """Run at most one bounded discovery slice.

        Returns an envelope whose `status` is one of the constants above. A
        `NEW_QUALIFIED_FINDINGS` answer also carries `findings`, one dict per
        finding, each with at least `finding_id`.
        """
        raise NotImplementedError

    def deliver_finding_to_audit_inbox(
        self, project_root, finding, *, publication_authorized: bool
    ):  # pragma: no cover - protocol
        """Offer one finding to the audit transport.

        The enqueue is the backend's ONLY write path; `publication_authorized`
        is the campaign's answer about authority, never the backend's.
        """
        raise NotImplementedError
