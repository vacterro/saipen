"""The CURRENT-SESSION capability -- negotiated, never remembered (CORE § 1.3).

`STATE.mode` records the LAST handshake outcome. It is history: the session that
wrote it is over, and a value on disk can neither grant nor revoke the authority
of the session reading it. Authorization, routing, release and crew therefore
consume the capability THIS session negotiated, which every public command
boundary obtains from `negotiate_capability()` and injects downstream
(hostile-regression, P0#4).

Two failure modes this closes:

  * a stale `mode: full` letting a read-only session route mutation, plan a
    release or close a crew epoch;
  * a stale `mode: read-only` freezing a session that really is writable.

The negotiation is deliberately explicit and machine-readable: the host declares
the session's capability through `SAIPEN_CAPABILITY`, and absent a declaration
the session is a normal writable one (`full`). Nothing here reads `STATE.md`.
"""

from __future__ import annotations

import os

# The closed capability set (identical to the STATE `mode` enum, because the
# handshake outcome and the live capability describe the same four policies --
# only their AUTHORITY over the current session differs).
CAPABILITIES = ("full", "read-only", "no-publish", "manual-verify")

DEFAULT_CAPABILITY = "full"

ENV_VAR = "SAIPEN_CAPABILITY"


def negotiate_capability(env: dict | None = None) -> str:
    """The capability of the RUNNING session.

    Honors `SAIPEN_CAPABILITY` (one of `CAPABILITIES`); an absent or
    unrecognized declaration negotiates the default writable session. The
    result is always a member of `CAPABILITIES`, so no caller has to defend
    against a None/garbage capability leaking into an authorization decision.
    """
    source = os.environ if env is None else env
    declared = str(source.get(ENV_VAR, "") or "").strip().lower()
    return declared if declared in CAPABILITIES else DEFAULT_CAPABILITY


def capability_error(capability: object) -> str | None:
    """Why `capability` is not a usable current-session capability, or None.

    Authorization sites use this so an unknown capability fails CLOSED instead
    of silently behaving like `full`.
    """
    if capability is None:
        return (
            "no current-session capability was negotiated; the public "
            "command boundary must inject one (CORE § 1.3)"
        )
    if not isinstance(capability, str) or capability not in CAPABILITIES:
        return (
            f"current-session capability {capability!r} is outside the "
            f"closed set {'/'.join(CAPABILITIES)}"
        )
    return None


def may_mutate(capability: object) -> bool:
    """True when the CURRENT session may perform local canonical writes."""
    return capability_error(capability) is None and capability != "read-only"


def may_publish(capability: object) -> bool:
    """True when the CURRENT session may publish (git push/tag)."""
    return capability_error(capability) is None and capability == "full"
