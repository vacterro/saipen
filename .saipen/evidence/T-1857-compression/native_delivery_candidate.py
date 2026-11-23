"""UNDEPLOYED candidate: broker-issued intent -> owned worker -> canonical CLI.

Nothing in this module signs an event or changes a caller identity policy.
The native host must call it from its actual admitted user-input callback.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

from saipen_engine import host_authority_client as authority
from saipen_engine import operator_task
from saipen_engine.commands import resume_policy
from saipen_engine.pending_ingress import ingress_digest
from saipen_engine.process_tree import ProcessTree

MAX_PACKET_BYTES = 256 * 1024


def refusal(detail, code="HOST_PROVENANCE_UNAVAILABLE"):
    return {"ok": False, "code": code, "detail": detail, "sealed": False}


def checked_input(event):
    """Validate transport only. The broker alone authenticates the producer."""
    if not isinstance(event, dict) or event.get("event") != "UserPromptSubmit":
        raise ValueError("an original native UserPromptSubmit event is required")
    data = event.get("host_ingress")
    if not isinstance(data, dict):
        raise ValueError("native ingress body is missing")
    text, message = data.get("request_text"), data.get("message_id")
    session, host, root = event.get("session_id"), event.get("host"), event.get("cwd")
    for label, value, limit in (("message ID", message, 160), ("session", session, 160),
                                ("host", host, 80), ("project", root, 32768)):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"the original native {label} is missing or invalid")
    if data.get("session_id") != session:
        raise ValueError("native event and envelope sessions disagree")
    if not isinstance(text, str) or text.strip() not in resume_policy()["operator_inputs"]:
        raise ValueError("this delivery accepts declared resume intent only")
    if data.get("request_digest") not in (None, ingress_digest(text)):
        raise ValueError("native intent bytes and declared digest disagree")
    return {"host": host, "session": session, "project": str(Path(root).resolve()),
            "event_id": message, "request_text": text, "action": "continue"}


def deliver(event, runtime, *, client=authority, tree_factory=ProcessTree, timeout=60):
    """No packet is sent until the broker binds the actual owned child PID."""
    try:
        intent = checked_input(event)
        worker = Path(runtime) / "tools/native_operator_worker.py"
        if not worker.is_file():
            return refusal("the canonical native worker is not installed")
        issued = client.issue_operator_origin(**intent)
        if not isinstance(issued, dict):
            return refusal("native issuer supplied no valid broker reply")
        if issued.get("ok") is not True:
            return refusal(str(issued.get("detail") or "native issuer was not verified"))
        proof = issued.get("proof")
        if not isinstance(proof, dict):
            return refusal("the broker supplied no operator-origin proof")
        packet = {**intent, "operator_origin": proof}
        raw = json.dumps(packet, ensure_ascii=False).encode("utf-8")
        if len(raw) > MAX_PACKET_BYTES:
            client.revoke_operator_origin(proof)
            return refusal("native delivery exceeds its bounded frame")

        environment = os.environ.copy()
        environment.pop(operator_task.ENV_TASK_FILE, None)
        environment[operator_task.ENV_TASK_SHA256] = ingress_digest(intent["request_text"])
        environment[operator_task.ENV_HOST_SESSION] = intent["session"]

        def register(process):
            if process.poll() is not None:
                raise ValueError("native worker exited before registration")
            answer = client.register_operator_worker(proof, process.pid)
            if not isinstance(answer, dict) or answer.get("ok") is not True:
                raise ValueError("the broker refused the actual worker binding")

        sent = False
        try:
            with tree_factory() as owned:
                try:
                    child = owned.start(
                        [sys.executable, "-B", str(worker), "--project-root", intent["project"]],
                        cwd=intent["project"], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
                        on_started=register,
                    )
                    # The shipped worker blocks on stdin; it cannot admit intent
                    # before the above native registration succeeds.
                    sent = True
                    stdout, stderr = child.communicate(raw, timeout=timeout)
                    if len(stdout) > MAX_PACKET_BYTES or len(stderr) > MAX_PACKET_BYTES:
                        return refusal("native worker output exceeded its bounded carrier")
                    answer = json.loads(stdout.decode("utf-8"))
                    if child.returncode != 0 or not isinstance(answer, dict):
                        return refusal("native worker did not return a valid delivery result")
                    return answer
                finally:
                    process = getattr(owned, "process", None)
                    if process is not None:
                        for stream in (process.stdin, process.stdout, process.stderr):
                            if stream is not None:
                                with contextlib.suppress(OSError):
                                    stream.close()
        finally:
            # Before any packet, no grant can have committed. After sending,
            # preserve the broker record: canonical continuation may already
            # have journaled authority even if its response was interrupted.
            if not sent:
                client.revoke_operator_origin(proof)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return refusal(str(error))


def consume(packet, expected_project, *, verify=authority.verify_operator_origin,
            admit=operator_task.admit_host_ingress, continuation=None):
    """The actual worker independently checks the proof before cache/CLI writes."""
    try:
        intent = checked_input({"event": "UserPromptSubmit", "host": packet["host"],
                                "cwd": packet["project"], "session_id": packet["session"],
                                "host_ingress": {"message_id": packet["event_id"],
                                                 "session_id": packet["session"],
                                                 "request_text": packet["request_text"]}})
        if Path(intent["project"]).resolve() != Path(expected_project).resolve():
            raise ValueError("native worker project differs from its launch binding")
        proof = packet.get("operator_origin")
        if not isinstance(proof, dict) or any(
            proof.get(key) != intent[key] for key in ("host", "session", "event_id", "action")
        ):
            raise ValueError("native proof purpose/event/session does not match delivery")
        if not verify(proof, project=intent["project"],
                      request_digest=ingress_digest(intent["request_text"]),
                      session=intent["session"]):
            return refusal("the broker did not authenticate this worker and exact intent")
        accepted = admit(
            {"message_id": intent["event_id"], "session_id": intent["session"],
             "request_text": intent["request_text"], "operator_origin": proof},
            intent["project"], event_session=intent["session"],
        )
        if accepted.get("ok") is not True:
            return accepted
        if continuation is None:
            # Transport of an already verified session is not an authority
            # witness. The canonical CLI independently verifies the origin.
            os.environ["SAIPEN_HOST_SESSION"] = intent["session"]
            import saipen as canonical_cli

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = canonical_cli.main([
                    "--project-root", intent["project"], "continue", "--json",
                ])
            result = json.loads(output.getvalue())
        else:
            exit_code, result = continuation(intent["project"])
        if not isinstance(result, dict):
            raise ValueError("canonical continuation result is not an object")
        return {"ok": True, "sealed": True, "ingress_id": accepted.get("ingress_id"),
                "continuation": {"exit_code": exit_code, "answer": result}}
    except (KeyError, TypeError, OSError, ValueError) as error:
        return refusal(str(error))


def worker_main(expected_project):
    """EOF/invalid packet refuses; no canonical write happens before verify."""
    try:
        raw = sys.stdin.buffer.read(MAX_PACKET_BYTES + 1)
        if not raw or len(raw) > MAX_PACKET_BYTES:
            raise ValueError("native worker received no complete bounded packet")
        answer = consume(json.loads(raw.decode("utf-8")), expected_project)
    except (UnicodeError, ValueError) as error:
        answer = refusal(str(error))
    print(json.dumps(answer, ensure_ascii=False))
    return 0 if answer.get("ok") is True else 1
