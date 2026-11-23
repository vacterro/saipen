"""Exact operator-event records owned by the existing host-authority broker.

No signer, endpoint or client identity is created here. The broker supplies its
existing keyed ledger and OS process reader. Native issue/register/revoke calls
must already have passed the broker's shipped-hook identity check. Consumers
are identified by an OS-observed registered worker, never a supplied PID/env.
"""

from __future__ import annotations

import copy
import math
import os
import re
import secrets
import threading
from pathlib import Path

from .paths import project_identity, project_lineage_identity
from .pending_ingress import ingress_digest
from .state import parse_state

KIND = "operator-origin"
VERDICT = "operator-origin-verdict"
SOURCE_VERDICT = "operator-source-origin"
UNAVAILABLE = "HOST_PROVENANCE_UNAVAILABLE"
MAX_EVENTS = 4096
ACTIONS = frozenset({
    "start", "continue", "goal", "authorize-goal", "append", "handoff", "report", "resolve-gate",
    "retire", "supersede",
})


def refused(detail):
    return {"ok": False, "code": UNAVAILABLE, "detail": detail}


def _birth(fact):
    value = getattr(fact, "created", None)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value


def _pid(value):
    return value if type(value) is int and value > 0 else None


def context(root):
    """An independent current project/task scope; no carrier supplies it."""
    root = Path(root).resolve()
    state = parse_state((root / ".saipen/STATE.md").read_text(encoding="utf-8-sig"))
    task = state.get("task")
    if not isinstance(task, str) or not re.fullmatch(r"(?:T-\d+|none)", task):
        raise ValueError("current task scope is unreadable")
    lineage = project_lineage_identity(root)
    if not lineage:
        raise ValueError("current project has no proven lineage")
    return {
        "project": project_identity(root),
        "lineage": lineage,
        "task": task,
        "goal": str(state.get("goal_ingress") or ""),
        "budget": str(state.get("authority_source") or ""),
    }


class OperatorOrigins:
    """One broker generation's native events and registered worker bindings."""

    def __init__(self, ledger, *, clock, ancestry, ttl):
        self.ledger, self.clock, self.ancestry = ledger, clock, ancestry
        self.ttl = ttl
        self.events = {}
        self.records = {}
        self.workers = {}
        self.lock = threading.RLock()

    def _chain(self, pid):
        if _pid(pid) is None:
            return []
        facts = list(self.ancestry(pid, 32))
        if not facts or facts[0].pid != pid:
            return []
        for i, fact in enumerate(facts):
            if _birth(fact) is None:
                return []
            if i and (_birth(fact) > _birth(facts[i - 1]) or facts[i - 1].ppid != fact.pid):
                return []
        return facts

    def _record(self, proof):
        if not isinstance(proof, dict) or proof.get("kind") != KIND:
            return None
        if not isinstance(proof.get("nonce"), str) or not re.fullmatch(
            r"[0-9a-f]{32}",
            proof["nonce"],
        ):
            return None
        known = self.records.get(proof.get("nonce"))
        if not known or known["revoked"] or known["proof"] != proof:
            return None
        if not self.ledger.verify(proof)[0]:
            return None
        return known

    def issue(self, scope, identity, *, text, event_id, action):
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text.encode("utf-8")) > 256 * 1024
            or not isinstance(event_id, str)
            or not 1 <= len(event_id) <= 160
            or not isinstance(action, str)
            or action not in ACTIONS
            or not _pid(identity.get("host_pid"))
        ):
            return refused("native operator event is missing a bounded identity, body or action")
        try:
            project = context(scope["root"])
            hosts = self._chain(identity["host_pid"])
        except (OSError, ValueError, TypeError):
            return refused("native operator project or host process scope is unavailable")
        if not hosts:
            return refused("native host process birth could not be observed")
        binding = {
            **project,
            "session": scope["session"],
            "host": scope["host"],
            "model": str(scope.get("model") or ""),
            "provider": str(scope.get("provider") or ""),
        }
        from .cold_recovery import goal_ingress_identity
        from .codec import redact_credentials

        goal_target = goal_ingress_identity(redact_credentials(text).strip(), binding["project"])
        authorization = None
        if action == "authorize-goal":
            from .goal_authority import current_binding, parse_capsule
            from .log import read_history_snapshot

            try:
                authorization = parse_capsule(text)
                current = parse_state(
                    (Path(scope["root"]) / ".saipen/STATE.md").read_text(encoding="utf-8-sig")
                )
                binding_now = current_binding(
                    scope["root"], current, read_history_snapshot(scope["root"]).events, {},
                )
                if authorization != binding_now:
                    return refused("native authorization names a different existing goal")
            except (OSError, ValueError, TypeError, KeyError):
                return refused("native goal authorization is not an exact goal capsule")
            goal_target = authorization["goal_ingress"]
        key = (binding["project"], binding["host"], binding["session"], event_id)
        digest = ingress_digest(text)
        with self.lock:
            if key in self.events:
                known = self.records[self.events[key]]
                prior = known["proof"]
                if (
                    known["revoked"]
                    or prior["request_digest"] != digest
                    or prior["action"] != action
                    or prior["host_pid"] != hosts[0].pid
                    or prior["host_birth"] != _birth(hosts[0])
                    or any(prior[name] != value for name, value in binding.items())
                ):
                    return refused("a native event identity cannot be reused with another intent")
                if self.clock() > prior["expires"]:
                    return refused("the native operator event has expired")
                return {"ok": True, "code": None, "proof": copy.deepcopy(prior), "reused": True}
            # Never evict a live authority to manufacture room for another.
            if len(self.records) >= MAX_EVENTS:
                return refused("operator event capacity is full; existing authority is preserved")
            proof = {
                "schema": 1,
                "kind": KIND,
                **binding,
                "event_id": event_id,
                "nonce": secrets.token_hex(16),
                "action": action,
                "request_digest": digest,
                "issued": self.clock(),
                "expires": self.clock() + self.ttl,
                "host_pid": hosts[0].pid,
                "host_birth": _birth(hosts[0]),
            }
            proof = self.ledger.seal_payload(proof)
            self.records[proof["nonce"]] = {
                "proof": proof, "revoked": False, "receipt": None,
                "goal_target": goal_target, "goal_grant": None,
                "authorization": authorization,
            }
            self.events[key] = proof["nonce"]
            return {"ok": True, "code": None, "proof": copy.deepcopy(proof), "reused": False}

    def register_worker(self, proof, identity, pid):
        """Only an already authenticated native writer may call this method."""
        with self.lock:
            known = self._record(proof)
            if not known or identity.get("host_pid") != proof["host_pid"]:
                return refused("operator event does not belong to this native host invocation")
            try:
                facts = self._chain(pid)
            except (OSError, ValueError, TypeError):
                facts = []
            if (
                not facts
                or pid == proof["host_pid"]
                or not any(
                    f.pid == proof["host_pid"] and _birth(f) == proof["host_birth"]
                    for f in facts[1:]
                )
            ):
                return refused("worker is not an observed child of the proven native host")
            if self.clock() > proof["expires"] and known["goal_grant"] is None:
                return refused("the native operator event has expired")
            for fact in facts:
                existing = self.workers.get((fact.pid, _birth(fact)))
                if existing and existing != proof["nonce"]:
                    previous = self.records.get(existing)
                    if not previous or not previous["revoked"]:
                        return refused(
                            "a live worker cannot be rebound to a different operator event"
                        )
            self.workers[(pid, _birth(facts[0]))] = proof["nonce"]
            return {"ok": True, "code": None, "worker": pid}

    def _worker(self, peer, nonce):
        try:
            facts = self._chain(getattr(peer, "pid", None))
        except (OSError, ValueError, TypeError):
            return False
        for fact in facts:
            owner = self.workers.get((fact.pid, _birth(fact)))
            if owner:
                return owner == nonce
        return False

    def _goal_worker(self, peer, proof, reserved):
        """An accepted goal also belongs to later native turns in its session.

        Each delivery retains its separate worker binding. A later independently
        registered event can read the original committed grant only in that
        grant's exact host/session/model and goal/budget epoch. This neither
        rebinds a worker nor restores another event's delivery capabilities.
        """
        if self._worker(peer, proof["nonce"]):
            return True
        try:
            facts = self._chain(getattr(peer, "pid", None))
        except (OSError, ValueError, TypeError):
            return False
        for fact in facts:
            owner = self.workers.get((fact.pid, _birth(fact)))
            if not owner:
                continue
            current = self.records.get(owner)
            if not current or self._record(current["proof"]) is None:
                return False
            event = current["proof"]
            return (
                all(event[name] == proof[name] for name in (
                    "project", "lineage", "host", "session", "model", "provider",
                    "host_pid", "host_birth",
                ))
                and event["goal"] == reserved["grant"]["goal_ingress"]
                and event["budget"] == reserved["grant"]["authority_source"]
            )
        return False

    @staticmethod
    def _source(root, receipt, proof):
        """Read canonical Source bytes; never trust a receipt name from a cache."""
        from . import intake

        if not isinstance(receipt, str) or not re.fullmatch(r"SRC-\d+", receipt):
            return False
        found = intake.read_body(root, receipt)
        if not found.get("ok"):
            return False
        meta = found.get("meta") or {}
        provenance = meta.get("request_provenance") or {}
        body = found.get("body") or ""
        if body.startswith("# User request\n"):
            _header, separator, body = body.partition("\n## Request\n")
            if not separator:
                return False
        return bool(
            provenance.get("witness") == "operator_carrier"
            and provenance.get("operator_origin") == proof
            and provenance.get("compared_digest") == proof["request_digest"]
            and ingress_digest(body) == proof["request_digest"]
        )

    @staticmethod
    def _scope_matches(root, proof, *, bound_retirement=False):
        current = context(root)
        names = ("project", "lineage", "goal") if bound_retirement else (
            "project", "lineage", "task", "goal"
        )
        return all(current[name] == proof[name] for name in names) and (
            proof["action"] not in {"continue", "resolve-gate", "retire"}
            or current["budget"] == proof["budget"]
        )

    def verify(self, payload, peer):
        proof, root = payload.get("proof"), payload.get("project")
        with self.lock:
            known = self._record(proof)
            if not known or not self._worker(peer, proof["nonce"]):
                return refused("operator origin or delivering OS worker is unverified")
            if (known["goal_grant"] is not None and payload.get("receipt") is not None
                    and proof["action"] != "authorize-goal"):
                return refused("operator delivery is reserved for its original goal operation")
            try:
                root = Path(root).resolve()
                if (
                    project_identity(root) != proof["project"]
                    or project_lineage_identity(root) != proof["lineage"]
                    or payload.get("request_digest") != proof["request_digest"]
                    or payload.get("session") not in (None, proof["session"])
                ):
                    return refused("operator origin belongs to another project, session or content")
                # A Source reference preserves the event identity, never an
                # exemption from expiry, task/goal scope or a spent cc budget.
                bound_retirement = (
                    proof["action"] == "retire" and known["receipt"] is not None
                    and payload.get("receipt") == known["receipt"]
                )
                if self.clock() > proof["expires"] or not self._scope_matches(
                    root, proof, bound_retirement=bound_retirement,
                ):
                    return refused("native event expired or changed task/action scope")
                receipt = payload.get("receipt")
                if receipt is not None:
                    if payload.get("existing_only") and known["receipt"] != receipt:
                        return refused("the original Source has not already bound this event")
                    if known["receipt"] not in (None, receipt) or not self._source(
                        root, receipt, proof
                    ):
                        return refused("operator event is not bound to this exact canonical Source")
                    if known["receipt"] is None:
                        known["receipt"] = receipt
                else:
                    if known["receipt"] is not None:
                        return refused("operator delivery is bound; use its original Source")
            except (OSError, ValueError, TypeError, KeyError):
                return refused("operator origin scope or canonical Source is unreadable")
            return {
                "ok": True,
                "code": None,
                "kind": VERDICT,
                "project": os.path.normcase(str(root)),
                "request_digest": proof["request_digest"],
                "action": proof["action"],
            }

    def received_source(self, payload):
        """Attest an already accepted Source, never accept one or grant delivery.

        A past human report remains a human report across worker/task churn and
        delivery expiry. Its consumer must check the report's exact Work,
        contract and build. Revocation, issuer loss and changed/copied Sources
        remain unverified. This verdict carries no current capabilities.
        """
        proof = payload.get("proof")
        with self.lock:
            known = self._record(proof)
            receipt = payload.get("receipt")
            if not known or not known["receipt"] or receipt != known["receipt"]:
                return refused("the issuer has not accepted this exact Source")
            try:
                root = Path(payload.get("project")).resolve()
                if (project_identity(root) != proof["project"]
                        or project_lineage_identity(root) != proof["lineage"]
                        or payload.get("request_digest") != proof["request_digest"]
                        or not self._source(root, receipt, proof)):
                    return refused("the accepted Source origin is absent or changed")
            except (OSError, ValueError, TypeError, KeyError):
                return refused("the accepted Source is unreadable")
            return {"ok": True, "code": None, "kind": SOURCE_VERDICT,
                    "project": os.path.normcase(str(root)), "receipt": receipt,
                    "request_digest": proof["request_digest"], "action": proof["action"]}

    def revoke(self, proof, identity):
        with self.lock:
            known = self._record(proof)
            if not known or identity.get("host_pid") != proof["host_pid"]:
                return refused("operator event does not belong to this native host invocation")
            known["revoked"] = True
            return {"ok": True, "code": None}

    def prepare_goal(self, payload, peer):
        """Reserve one exact intent for one planned goal, before its APPLY.

        A committed goal is existing scoped authority, not an unexpired
        delivery that can be spent again. The live owner retains this binding;
        a journal, matching file or signed proof copied elsewhere cannot mint it.
        """
        from .goal_authority import FIELDS, grant_fields

        proof = payload.get("proof")
        with self.lock:
            known = self._record(proof)
            if (not known or proof["action"] not in {"goal", "authorize-goal"}
                    or not self._worker(peer, proof["nonce"])):
                return refused("a registered native goal intent is required")
            try:
                root = Path(payload.get("project")).resolve()
                if (project_identity(root) != proof["project"]
                        or self.clock() > proof["expires"]
                        or not self._scope_matches(root, proof)):
                    return refused("goal intent expired or changed scope before reservation")
                grant = payload.get("grant")
                source = grant.get("authority_source") if isinstance(grant, dict) else None
                prefix = "goal-entry-" if proof["action"] == "goal" else "goal-authorize-"
                if (not isinstance(source, str) or not re.fullmatch(r"E-[1-9]\d*", source)
                        or grant != {**grant_fields(source), "goal_ingress": known["goal_target"]}
                        or payload.get("operation") != prefix + proof["nonce"]
                        or not isinstance(payload.get("semantic_hash"), str)
                        or not re.fullmatch(r"[0-9a-f]{16}", payload["semantic_hash"])):
                    return refused("goal reservation does not match the exact native intent")
                reservation = {
                    "operation": payload["operation"], "semantic_hash": payload["semantic_hash"],
                    "grant": {key: grant[key] for key in (*FIELDS, "goal_ingress")},
                }
                if proof["action"] == "authorize-goal":
                    if (source != known["authorization"]["authority_source"] or not known["receipt"]
                            or payload.get("authorization") != known["authorization"]
                            or not self._source(root, known["receipt"], proof)):
                        return refused("the existing goal authorization Source is unbound")
                elif known["receipt"] is not None:
                    return refused("native goal intent is already bound to a Source")
                if known["goal_grant"] not in (None, reservation):
                    return refused("native goal intent is already bound to another effect")
                known["goal_grant"] = reservation
            except (OSError, ValueError, TypeError, KeyError):
                return refused("native goal reservation scope is unreadable")
            return {"ok": True, "code": None}

    def verify_goal(self, payload, peer):
        """Prove a committed reservation in its unchanged goal epoch.

        Task churn and delivery expiry do not revoke an accepted goal. Another
        goal, revoked proof, lost issuer or changed canonical operation does.
        """
        from .goal_authority import FIELDS
        from .journal import Journal

        proof = payload.get("proof")
        with self.lock:
            known = self._record(proof)
            if not known:
                return refused("the goal issuer or registered delivering worker is unavailable")
            reserved = known["goal_grant"]
            if not reserved or payload.get("operation") != reserved["operation"]:
                return refused("native intent has no matching goal reservation")
            if not self._goal_worker(peer, proof, reserved):
                return refused("the goal issuer or registered delivering worker is unavailable")
            try:
                root = Path(payload.get("project")).resolve()
                state = parse_state((root / ".saipen/STATE.md").read_text(encoding="utf-8-sig"))
                if (project_identity(root) != proof["project"]
                        or project_lineage_identity(root) != proof["lineage"]
                        or state.get("phase") == "CORRUPT"
                        or any(state.get(key) != value
                               for key, value in reserved["grant"].items())):
                    return refused("the accepted goal no longer owns this exact continuation scope")
                record = Journal(root, reserved["operation"]).read()
                transition = proof["action"] == "authorize-goal"
                metadata = record.get("receipt_metadata") or {}
                grant = metadata.get(
                    "goal_authority_transition" if transition else "goal_authority"
                ) or {}
                provenance = grant.get("request_provenance") or {}
                scope = grant.get("binding") if transition else grant
                if (record.get("status") != "COMMITTED"
                        or record.get("operation") != (
                            "goal_authorize" if transition else "goal_entry")
                        or record.get("semantic_payload_hash") != reserved["semantic_hash"]
                        or record.get("project_lineage") != proof["lineage"]
                        or provenance.get("witness") != "operator_carrier"
                        or provenance.get("operator_origin") != proof
                        or provenance.get("compared_digest") != proof["request_digest"]
                        or not isinstance(scope, dict)
                        or any(scope.get(key) != reserved["grant"][key]
                               for key in (*FIELDS, "goal_ingress"))):
                    return refused("the original canonical goal operation is absent or changed")
                if transition and (
                    scope != known["authorization"]
                    or grant.get("authorization_receipt") != known["receipt"]
                    or not self._source(root, known["receipt"], proof)
                ):
                    return refused("the original existing-goal authorization has changed")
            except (OSError, ValueError, TypeError, KeyError):
                return refused("the accepted goal operation is unreadable")
            return {"ok": True, "code": None, "kind": "operator-goal-verdict",
                    "operation": reserved["operation"], "grant": copy.deepcopy(reserved["grant"])}
