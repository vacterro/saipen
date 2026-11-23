"""Bounded local provenance capture. No authority inferred from actor labels."""
from __future__ import annotations

import collections
import datetime
import hashlib
import json
import re
import sqlite3
import stat
import subprocess
from pathlib import Path

CASE = Path(__file__).resolve().parent
LOCATION = json.loads((CASE / "location.json").read_text())
ROOT = Path(LOCATION["root"])
SNAP = Path(LOCATION["snapshot"])
CAPTURE = CASE / "provenance-capture"
CAPTURE.mkdir(exist_ok=True)


def save(name, raw):
    target = CAPTURE / name
    if target.exists():
        assert target.read_bytes() == raw, name
    else:
        target.write_bytes(raw)
        target.chmod(stat.S_IREAD)
    return {"file": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def main():
    report = {"captured_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "root": str(ROOT)}
    git_records = []
    for label, args in (
        ("commit-metadata", ["show", "-s", "--format=fuller", "HEAD"]),
        ("lifecycle-diff", ["diff", "HEAD^", "HEAD", "--", ".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md", ".saipen/MANIFEST.json"]),
        ("canonical-blame", ["blame", "--line-porcelain", "-L", "1,8", "HEAD", "--", ".saipen/BOARD.md"]),
        ("canonical-log-blame", ["blame", "--line-porcelain", "-L", "1,4", "HEAD", "--", ".saipen/LOG.md"]),
        ("evidence-and-engineering-files", ["show", "--format=", "--name-only", "HEAD"]),
    ):
        argv = ["git", "-C", str(ROOT), *args]
        proc = subprocess.run(argv, capture_output=True, check=False)
        record = save(label + ".txt", proc.stdout + proc.stderr)
        record.update({"argv": argv, "exit_code": proc.returncode})
        git_records.append(record)
    for revision in ("HEAD", "HEAD^"):
        for name in ("STATE.md", "BOARD.md", "LOG.md", "MANIFEST.json"):
            proc = subprocess.run(["git", "-C", str(ROOT), "show", revision + ":.saipen/" + name], capture_output=True)
            if proc.returncode == 0:
                git_records.append({"revision": revision, **save(revision.replace("^", "-parent") + "-" + name, proc.stdout)})
    report["git"] = git_records

    # Search the captured project corpus, including recovery copies, for real
    # event lines; parent references and prose mentions cannot fill a gap.
    missing = {3133, 3136, 3145, 3147}
    found = []
    candidates = []
    for path in SNAP.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".json"}:
            continue
        if path.name == "ACQUISITION.json" or path.stat().st_size > 8_000_000:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if path.name.endswith("BOARD.md") or path.name.endswith("STATE.md") or path.name.endswith("LOG.md"):
            candidates.append({"path": path.relative_to(SNAP).as_posix(), "tail": max([int(n) for n in re.findall(r"\[E-(\d+)\]", text)] or [0]),
                               "t299_record_count": len(re.findall(r"^- \[[ x/]\] T-299\b", text, re.M))})
        for line_no, line in enumerate(text.splitlines(), 1):
            match = re.match(r"^- \d{2}\.\d{2}\.\d{2} \d{2}:\d{2} \[E-(\d+)\]", line)
            if match and int(match.group(1)) in missing:
                found.append({"path": path.relative_to(SNAP).as_posix(), "line": line_no, "event": int(match.group(1)), "text": line[:700]})
    report["gap_search"] = {"events": sorted(missing), "scope": "captured .md/.txt/.json files <=8MB, no binaries or host databases", "matches": found, "recovery_heads": candidates}

    db = Path("C:/Users/vac34/.local/share/opencode/opencode.db")
    conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    conn.execute("BEGIN")
    sessions = [dict(zip(("id", "directory", "title", "agent", "model", "created", "updated"), row)) for row in conn.execute(
        "SELECT id,directory,title,agent,model,time_created,time_updated FROM session WHERE lower(directory) LIKE ?", ("%audapack%",))]
    report["host_sessions"] = sessions
    # The incident predates this investigation; exclude its new user prompt
    # and any copied handoff from being mistaken for evidence of an edit.
    start = int(datetime.datetime(2026, 10, 7, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    end = int(datetime.datetime(2026, 10, 10, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    matches = []
    for ident, message_id, session_id, created, data in conn.execute(
        "SELECT p.id,p.message_id,p.session_id,p.time_created,p.data FROM part p JOIN session s ON p.session_id=s.id "
        "WHERE lower(s.directory) LIKE ? AND p.time_created>=? AND p.time_created<? "
        "AND (p.data LIKE ? OR p.data LIKE ? OR p.data LIKE ?)",
        ("%audapack%", start, end, "%T-299%", "%TODO## DOING%", "%trust-boundary-p1a-p1b%"),
    ):
        parsed = json.loads(data)
        # Preserve only incident-related parts, not credentials, settings, or
        # unrelated conversations. Tool invocations are primary evidence.
        record = save("host-part-" + ident + ".json", data.encode("utf-8"))
        record.update({"id": ident, "message_id": message_id, "session_id": session_id, "created": created,
                       "type": parsed.get("type"), "tool": parsed.get("tool"), "state_status": parsed.get("state", {}).get("status")})
        if parsed.get("type") == "tool":
            record["input"] = parsed.get("state", {}).get("input")
            record["output_excerpt"] = str(parsed.get("state", {}).get("output", ""))[:1200]
        else:
            record["text_excerpt"] = str(parsed.get("text", ""))[:1200]
        msg = conn.execute("SELECT data FROM message WHERE id=?", (message_id,)).fetchone()
        if msg:
            meta = json.loads(msg[0])
            record["message_actor"] = {k: meta.get(k) for k in ("role", "agent", "mode", "modelID", "providerID", "parentID", "path", "time")}
        matches.append(record)
    conn.rollback()
    conn.close()
    report["host_incident_parts"] = matches
    report["host_scope"] = "Read-only SQLite transaction; AUDAPACK directory sessions, 2026-10-07 through 2026-10-09 UTC, three exact incident terms"
    (CASE / "provenance.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"git_records": len(git_records), "gap_matches": found, "audapack_sessions": len(sessions), "incident_parts": len(matches),
                      "tool_parts": [{k: r.get(k) for k in ("id", "session_id", "created", "tool", "state_status", "message_actor", "input", "output_excerpt")} for r in matches if r.get("type") == "tool"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
