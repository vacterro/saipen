"""Read a ledger directly, without invoking a launcher or performing recovery."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    runtime, root = Path(args.runtime).resolve(), Path(args.project).resolve()
    sys.path.insert(0, str(runtime / "tools"))
    from saipen_engine import log
    from saipen_engine import codec

    paths = log.history_paths(root)
    rows, independent, located, bad = [], [], [], []
    grammar = re.compile(
        r"^- (?:\d{2}[./]\d{2}[./]\d{2} \d{2}:\d{2} )?"
        r"\[E-(\d+)\](?: \[parent: E-(\d+)\])?"
        r"(?: \[T-[^\]]*\])?(?: \[agent: [^\]]*\])?"
        r"(?: \[op: [^\]]*\])? [A-Z]+: .*$"
    )
    before = {}
    for path in paths:
        if not path.exists():
            rows.append({"path": str(path), "exists": False})
            continue
        raw = path.read_bytes()
        before[str(path)] = hashlib.sha256(raw).hexdigest()
        text, encoding, bom = codec._decode(raw)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        parsed, rejected = [], []
        for number, line in enumerate(text.split("\n"), 1):
            match = grammar.fullmatch(line)
            native = log.parse_log_line(line)
            if match:
                event = int(match.group(1))
                parent = int(match.group(2)) if match.group(2) else None
                independent.append((event, parent))
            elif line.strip() and not line.lstrip().startswith("#"):
                bad.append(f"{path.name}:{number}")
            if native:
                parsed.append(native["event"])
            elif line.strip() and not line.lstrip().startswith("#"):
                rejected.append(number)
            if re.search(r"\[E-(3133|3134|3136|3137|3145|3146)\]", line):
                located.append({"path": str(path), "line": number, "text": line,
                                "native_event": native["event"] if native else None,
                                "line_bytes": len(line.encode("utf-8")),
                                "control_codepoints": [f"U+{ord(c):04X}" for c in line
                                                       if ord(c) < 32 or ord(c) in (133, 8232, 8233)]})
        rows.append({"path": str(path), "exists": True, "bytes": len(raw),
                     "sha256": before[str(path)], "encoding": encoding, "bom_hex": bom.hex(),
                     "first_event": parsed[0] if parsed else None,
                     "last_event": parsed[-1] if parsed else None,
                     "event_count": len(parsed), "parser_rejection_count": len(rejected),
                     "parser_rejection_lines": rejected})
    ids = [event for event, _ in independent]
    seen = set(ids)
    independent_errors = list(bad)
    if len(ids) != len(seen):
        independent_errors.append("duplicate event IDs")
    for index, (event, parent) in enumerate(independent):
        if index and event <= independent[index - 1][0]:
            independent_errors.append(f"event order at {event}")
        if parent is not None and (parent not in seen or parent >= event):
            independent_errors.append(f"invalid parent at {event}: {parent}")
    snapshot = log.read_history_snapshot(root)
    summary = log.read_history_routing_summary(root)
    mutation_snapshot, dependency_digest = log.read_history_snapshot_and_logs_digest(
        root, retain_text=False)
    verdict = log.snapshot_contract_errors(snapshot)
    direct = log.history_contract_errors(root)
    after = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in before}
    result = {
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.executable, "python_version": sys.version,
        "runtime": str(runtime), "module": str(Path(log.__file__).resolve()),
        "module_sha256": hashlib.sha256(Path(log.__file__).read_bytes()).hexdigest(),
        "project": str(root), "segments": rows, "located": located,
        "independent": {"events": len(independent), "errors": independent_errors},
        "snapshot": {"events": len(snapshot.events), "tail": snapshot.tail,
                     "hash": snapshot.hash, "illegal": list(snapshot.illegal_lines),
                     "contract_errors": verdict},
        "direct_contract_errors": direct,
        "mutation_loader": {"events": len(mutation_snapshot.events),
                            "hash": mutation_snapshot.hash,
                            "contract_errors": log.snapshot_contract_errors(mutation_snapshot),
                            "sealed_dependency_digest": dependency_digest},
        "routing_summary": {"events": summary.event_count, "tail": summary.tail,
                            "hash": summary.hash, "illegal": list(summary.illegal_lines),
                            "duplicates": list(summary.duplicate_event_ids),
                            "ordering": list(summary.ordering_errors)},
        "inputs_stable": before == after, "before_sha256": before, "after_sha256": after,
    }
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"runtime": str(runtime), "events": len(snapshot.events),
                      "contract_errors": verdict, "independent_errors": independent_errors,
                      "inputs_stable": before == after}))


if __name__ == "__main__":
    main()
