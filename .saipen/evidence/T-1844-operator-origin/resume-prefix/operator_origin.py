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
UNAVAILABLE = "HOST_PROVENANCE_UNAVAILABLE"
MAX_EVENTS = 4096
ACTIONS = frozenset({"start", "continue", "goal", "authorize-goal", "append", "handoff", "report"})


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
                    or any(prior[name] != value for name, value in binding.items())
                ):
                    return refused("a native event identity cannot be reused with another intent")
                if not known["receipt"] and self.clock() > prior["expires"]:
                    return refused("the unconsumed native operator event has expired")
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
            self.records[proof["nonce"]] = {"proof": proof, "revoked": False, "receipt": None}
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
            if not known["receipt"] and self.clock() > proof["expires"]:
                return refused("the unconsumed native operator event has expired")
            for fact in facts:
                existing = self.workers.get((fact.pid, _birth(fact)))
                if existing and existing != proof["nonce"]:
                    return refused("a live worker cannot be rebound to a different operator event")
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
    def _scope_matches(root, proof):
        current = context(root)
        names = ("project", "lineage", "task", "goal")
        return all(current[name] == proof[name] for name in names) and (
            proof["action"] != "continue" or current["budget"] == proof["budget"]
        )

    def verify(self, payload, peer):
        proof, root = payload.get("proof"), payload.get("project")
        with self.lock:
            known = self._record(proof)
            if not known or not self._worker(peer, proof["nonce"]):
                return refused("operator origin or delivering OS worker is unverified")
            try:
                root = Path(root).resolve()
                if (
                    project_identity(root) != proof["project"]
                    or project_lineage_identity(root) != proof["lineage"]
                    or payload.get("request_digest") != proof["request_digest"]
                    or payload.get("session") not in (None, proof["session"])
                ):
                    return refused("operator origin belongs to another project, session or content")
                receipt = payload.get("receipt")
                if receipt is not None:
                    if known["receipt"] not in (None, receipt) or not self._source(
                        root, receipt, proof
                    ):
                        return refused("operator event is not bound to this exact canonical Source")
                    if known["receipt"] is None:
                        if self.clock() > proof["expires"] or not self._scope_matches(root, proof):
                            return refused("native event expired or changed scope before binding")
                        known["receipt"] = receipt
                else:
                    if known["receipt"] is not None:
                        return refused("operator delivery is bound; use its original Source")
                    if self.clock() > proof["expires"] or not self._scope_matches(root, proof):
                        return refused("operator delivery has expired or changed task/action scope")
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

    def revoke(self, proof, identity):
        with self.lock:
            known = self._record(proof)
            if not known or identity.get("host_pid") != proof["host_pid"]:
                return refused("operator event does not belong to this native host invocation")
            known["revoked"] = True
            return {"ok": True, "code": None}
