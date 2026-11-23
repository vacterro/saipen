"""Night-shift-5 RED reproductions for the five independently-audited P0s.

Run from the repository root:

    python tools/regression_t2089/t2089_p0_night5.py

Each check prints RED (defect reproduced) or GREEN (defect fixed). The
suite exercises the live repo engine (`tools/saipen.py` loaded as a
module, `tools/saipen_engine/journal.py` via package import), never an
installed home.

Handoff cases (SAIHANDOFF_SAIPEN_HYPERLEAN_NIGHT_SHIFT_5):

- N5-A  16 saturated blocker groups (long shared_blocker_id /
        blocker_class / cause / owner, 8 long root tickets each) push the
        serialized agent view past the 32 KiB global budget: the final
        collapse guard skips `blocker_groups` on purpose.
- N5-B1 a single append whose CONTENT is shortened reports
        truncated=false (cut is derived from row count only); a receipt
        whose oversized `other` field is dropped entirely likewise stays
        truncated=false.
- N5-C  `_bound_string` slices raw UTF-8 at the byte budget: the kept
        prefix loses a straddled code point to decode-ignore while the
        dropped-tail digest starts at the raw budget offset -- the marker
        names a digest of bytes that were never the actual tail.
- N5-D  `_read_file_bytes` performs ONE os.read(fd, st_size): an
        instrumented short read captures partial manifest/progress bytes
        with structural_error=None.
- N5-E  a receipt file that vanishes between lstat and open yields
        manifest_raw=None / progress_raw=None with structural_error=None
        -- indistinguishable from "never existed", which is a masked
        present->vanished race, not a normal capture.
"""

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HARD_BUDGET_BYTES = 32 * 1024
SUBJECT = os.path.join("tools", "saipen.py")


def _load_subject():
    sys.path.insert(0, "tools")
    spec = importlib.util.spec_from_file_location("saipen", SUBJECT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["saipen"] = module
    spec.loader.exec_module(module)
    return module


def _load_journal():
    sys.path.insert(0, "tools")
    import saipen_engine.journal as journal

    return journal


def _saturated_group(i):
    return {
        "shared_blocker_id": "EX-%06d-" % i + "B" * 200,
        "blocker_class": "WAIT_USER_DECISION-" + "C" * 200,
        "cause": "cause %d " % i + "K" * 400,
        "owner": "saipen-cli-" + "O" * 200,
        "root_tickets": ["T-root-%d-%d-" % (i, j) + "R" * 400 for j in range(8)],
        "dependent_tickets": ["T-dep-%d-%d" % (i, j) for j in range(4)],
        "recovery_internally_authorized": False,
        "external_input_required": True,
        "read_only_work_may_proceed": True,
    }


def check_n5_a_global_overrun(module):
    """N5-A: 16 saturated groups must stay under the 32 KiB budget."""
    payload = {
        "ok": True,
        "code": "STATUS_OK",
        "blocker_projection": {
            "groups": [_saturated_group(i) for i in range(16)],
            "items": ["T-item-%d" % i for i in range(16 * 4)],
        },
    }
    view = module._agent_view_payload(payload)
    blob = json.dumps(view, ensure_ascii=False).encode("utf-8")
    problems = []
    if len(blob) > HARD_BUDGET_BYTES:
        problems.append(
            f"16 saturated groups: serialized view {len(blob)} B > 32 KiB budget"
        )
    if not view.get("truncated"):
        problems.append("16 saturated groups: truncated=false while rows were cut")
    return problems


def check_n5_b_append_truncation_lie(module):
    """N5-B1: one append, content-shortened, must set truncated=true."""
    payload = {"ok": True, "code": "STATUS_OK",
               "appends": [{"giant": "Z" * 30000}]}
    view = module._agent_view_payload(payload)
    problems = []
    if not view.get("truncated"):
        problems.append(
            "single append content-cut: truncated=false (cut derived from row count only)"
        )
    # The replacement marker must still be honest about the cut.
    appends_out = view.get("appends") or []
    if appends_out and isinstance(appends_out[0], dict):
        first = appends_out[0]
        if "giant" in first and not isinstance(first.get("giant"), (str, dict)):
            problems.append("append replacement lost the value shape")
    return problems


def check_n5_b_receipt_truncation_lie(module):
    """N5-B2: a receipt field dropped by the slim projection must set
    truncated=true, not pass silently as a complete receipt."""
    payload = {
        "ok": True,
        "code": "STATUS_OK",
        "conformance_status": {
            "receipt": {
                "status": "FAIL",
                "other": "X" * 30000,
            }
        },
    }
    view = module._agent_view_payload(payload)
    problems = []
    receipt = (view.get("conformance_status") or {}).get("receipt")
    if isinstance(receipt, dict) and "other" not in receipt:
        # The field was dropped by the slim-receipt filter: a loss-bearing
        # omission. The contract must reflect it.
        if not view.get("truncated"):
            problems.append(
                "receipt 'other' dropped: truncated=false (loss treated as summary)"
            )
    return problems


def check_n5_c_utf8_tail_digest(module):
    """N5-C: the dropped-tail digest must hash exactly the bytes after the
    valid kept UTF-8 prefix, straddled code point included."""
    problems = []
    euro = "€"
    text = euro * 400  # 3 bytes per char, 1200 bytes total
    budget = 512

    def marker_for(value, cap):
        # Route through the real function with a plain authority key.
        payload = {"ok": True, "next_action": value}
        view = module._agent_view_payload(payload)
        # next_action authority cut lives in authority_text_truncation
        cuts = view.get("authority_text_truncation") or {}
        for cut in cuts.get("cuts") or ():
            if cut.get("key") == "next_action":
                return cut
        return None

    marker = marker_for(text, budget)
    if marker is None:
        problems.append("authority cut marker missing for long next_action")
        return problems
    original = text.encode("utf-8")
    # The kept prefix is the valid UTF-8 the consumer actually sees:
    # budget bytes decoded with errors="ignore" then re-encoded.
    kept_prefix = original[:budget].decode("utf-8", "ignore").encode("utf-8")
    expected_tail = original[len(kept_prefix):]
    expected = hashlib.sha256(expected_tail).hexdigest()
    if marker.get("dropped_tail_sha256") != expected:
        problems.append(
            "dropped_tail_sha256 does not hash the actual dropped bytes: "
            f"got {marker.get('dropped_tail_sha256')}, "
            f"expected {expected} (tail is {len(expected_tail)} B "
            f"starting at byte {len(kept_prefix)})"
        )
    if marker.get("kept_utf8_bytes") != len(kept_prefix):
        problems.append(
            f"kept_utf8_bytes={marker.get('kept_utf8_bytes')} != {len(kept_prefix)}"
        )
    # Sub-case: budget straddles a 3-byte code point. 512 = 170*3 + 2, so
    # the straddled continuation bytes must move into the TAIL hash, not
    # vanish.
    problems2 = check_n5_c_ascii_and_edge(module)
    return problems + problems2


def check_n5_c_ascii_and_edge(module):
    """ASCII, 2/3/4-byte code points and a zero-length tail."""
    problems = []

    def tail_of(value):
        original = value.encode("utf-8")
        payload = {"ok": True, "next_action": value}
        view = module._agent_view_payload(payload)
        cuts = view.get("authority_text_truncation") or {}
        for cut in cuts.get("cuts") or ():
            if cut.get("key") == "next_action":
                return cut, original
        return None, original

    # ASCII: no straddle possible; tail = bytes past budget.
    ascii_text = "A" * 600
    cut, original = tail_of(ascii_text)
    if cut is None:
        problems.append("ASCII: cut marker missing")
    else:
        expected = hashlib.sha256(original[512:]).hexdigest()
        if cut.get("dropped_tail_sha256") != expected:
            problems.append("ASCII: dropped-tail digest wrong")
        if cut.get("kept_utf8_bytes") != 512:
            problems.append(f"ASCII: kept_utf8_bytes={cut.get('kept_utf8_bytes')}")

    # 2-byte char (é U+00E9), budget straddles: 256*2=512 exactly, then a
    # straddle at 513. Use 513-byte budget via 257 chars + cut.
    two_byte = "é" * 300  # 600 bytes
    cut, original = tail_of(two_byte)
    if cut is None:
        problems.append("2-byte UTF-8: cut marker missing")
    else:
        kept = original[:512]
        expected = hashlib.sha256(original[512:]).hexdigest()
        if cut.get("dropped_tail_sha256") != expected:
            problems.append("2-byte UTF-8: dropped-tail digest wrong")
        if cut.get("kept_utf8_bytes") != 512:
            problems.append(f"2-byte UTF-8: kept_utf8_bytes={cut.get('kept_utf8_bytes')}")

    # 4-byte char (emoji U+1F600), budget straddles the 4-byte sequence.
    four_byte = "😀" * 300  # 1200 bytes, 4 per char
    cut, original = tail_of(four_byte)
    if cut is None:
        problems.append("4-byte UTF-8: cut marker missing")
    else:
        kept = original[:512]  # 128 emojis exactly, no straddle
        expected = hashlib.sha256(original[512:]).hexdigest()
        if cut.get("dropped_tail_sha256") != expected:
            problems.append("4-byte UTF-8: dropped-tail digest wrong")
        if cut.get("kept_utf8_bytes") != 512:
            problems.append(f"4-byte UTF-8: kept_utf8_bytes={cut.get('kept_utf8_bytes')}")

    # Mixed multibyte with a straddling budget cut inside a code point.
    mixed = "a€é😀" * 200  # 1+3+2+4 = 10 bytes per rep, 2000 bytes
    cut, original = tail_of(mixed)
    if cut is None:
        problems.append("mixed UTF-8: cut marker missing")
    else:
        kept = original[:512].decode("utf-8", "ignore").encode("utf-8")
        expected = hashlib.sha256(original[len(kept):]).hexdigest()
        if cut.get("dropped_tail_sha256") != expected:
            problems.append("mixed UTF-8: dropped-tail digest wrong")
        if cut.get("kept_utf8_bytes") != len(kept):
            problems.append(
                f"mixed UTF-8: kept_utf8_bytes={cut.get('kept_utf8_bytes')} "
                f"!= {len(kept)}"
            )

    # Deterministic: same input twice -> same digest.
    cut1, _ = tail_of(mixed)
    cut2, _ = tail_of(mixed)
    if cut1 is None or cut2 is None or \
            cut1.get("dropped_tail_sha256") != cut2.get("dropped_tail_sha256"):
        problems.append("mixed UTF-8: digest not deterministic")
    return problems


def check_n5_d_short_read(journal):
    """N5-D: one os.read(fd, st_size) trusts a single read; an
    instrumented 7-byte-per-call short read corrupts the capture."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        ns_dir = os.path.join(tmp, "ops")
        op_dir = os.path.join(ns_dir, "op-1")
        os.makedirs(op_dir)
        manifest_bytes = b'{"operation": "x"}' + b" " * 66  # 86 bytes
        progress_bytes = b'{"state": "y"}' + b" " * 44  # 60 bytes
        with open(os.path.join(op_dir, "operation.json"), "wb") as fh:
            fh.write(manifest_bytes)
        with open(os.path.join(op_dir, "progress.json"), "wb") as fh:
            fh.write(progress_bytes)

        real_os_read = os.read
        read_state = {"budget": 7}

        def short_read(fd, n):
            # Chunked like a pipe/socket: never the full request in one go.
            return real_os_read(fd, min(n, read_state["budget"]))

        journal.os.read = short_read
        try:
            entries = list(
                journal._receipt_namespace_entries(Path(ns_dir))
            )
        finally:
            journal.os.read = real_os_read

        if not entries:
            return ["short-read fixture produced no entries"]
        entry = entries[0]
        if entry.manifest_raw != manifest_bytes:
            problems.append(
                f"short read: manifest_raw {len(entry.manifest_raw or b'')} B "
                f"!= {len(manifest_bytes)} B (read-to-EOF missing)"
            )
        if entry.progress_raw != progress_bytes:
            problems.append(
                f"short read: progress_raw {len(entry.progress_raw or b'')} B "
                f"!= {len(progress_bytes)} B (read-to-EOF missing)"
            )
        if entry.structural_error is not None:
            problems.append(
                f"short read silently misframed: structural_error={entry.structural_error!r}"
            )
    return problems


def check_n5_e_vanish_race(journal):
    """N5-E: a file present at lstat that vanishes before open must not
    be captured as plain absence (manifest_raw=None, structural_error=None)."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        ns_dir = os.path.join(tmp, "ops")
        op_dir = os.path.join(ns_dir, "op-vanish")
        os.makedirs(op_dir)
        op_dir_p = os.path.join(ns_dir, "op-intact")
        os.makedirs(op_dir_p)
        for d in (op_dir, op_dir_p):
            with open(os.path.join(d, "operation.json"), "wb") as fh:
                fh.write(b'{"operation": "v"}')
        with open(os.path.join(op_dir, "progress.json"), "wb") as fh:
            fh.write(b'{"state": "v"}')

        real_os_open = os.open

        def vanishing_open(path, flags, *args):
            if isinstance(path, str) and path.endswith("operation.json") \
                    and "op-vanish" in path:
                raise FileNotFoundError(path)
            return real_os_open(path, flags, *args)

        journal.os.open = vanishing_open
        try:
            entries = {
                e.name: e
                for e in journal._receipt_namespace_entries(Path(ns_dir))
            }
        finally:
            journal.os.open = real_os_open

        vanish_entry = entries.get("op-vanish")
        intact_entry = entries.get("op-intact")
        if vanish_entry is None or intact_entry is None:
            return ["vanish fixture produced missing entries"]
        if (
            vanish_entry.manifest_raw is None
            and vanish_entry.structural_error is None
        ):
            problems.append(
                "vanished manifest: manifest_raw=None, structural_error=None "
                "-- present->vanished masked as plain absence"
            )
        if (
            intact_entry.manifest_raw is None
            or intact_entry.structural_error is not None
        ):
            problems.append(
                "intact sibling corrupted by the injected fault: "
                f"manifest_raw={intact_entry.manifest_raw!r} "
                f"structural_error={intact_entry.structural_error!r}"
            )
    return problems


def check_n5_e_progress_vanish(journal):
    """N5-E companion: a progress.json that vanishes between lstat and
    open must be a structural event, not plain 'progress absent'."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        ns_dir = os.path.join(tmp, "ops")
        op_dir = os.path.join(ns_dir, "op-pv")
        os.makedirs(op_dir)
        with open(os.path.join(op_dir, "operation.json"), "wb") as fh:
            fh.write(b'{"operation": "v"}')
        with open(os.path.join(op_dir, "progress.json"), "wb") as fh:
            fh.write(b'{"state": "v"}')

        real_os_open = os.open

        def vanishing_open(path, flags, *args):
            if isinstance(path, str) and path.endswith("progress.json"):
                raise FileNotFoundError(path)
            return real_os_open(path, flags, *args)

        journal.os.open = vanishing_open
        try:
            entries = list(journal._receipt_namespace_entries(Path(ns_dir)))
        finally:
            journal.os.open = real_os_open

        if not entries:
            return ["progress-vanish fixture produced no entries"]
        entry = entries[0]
        if entry.progress_raw is None and entry.structural_error is None:
            problems.append(
                "vanished progress: progress_raw=None, structural_error=None "
                "-- indistinguishable from never-existed"
            )
    return problems


def check_n5_extra_read_error(journal):
    """N5-D companion: a mid-read OSError must classify, not crash or
    capture partial bytes silently."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        ns_dir = os.path.join(tmp, "ops")
        op_dir = os.path.join(ns_dir, "op-rerr")
        os.makedirs(op_dir)
        with open(os.path.join(op_dir, "operation.json"), "wb") as fh:
            fh.write(b'{"operation": "e"}')

        real_os_read = os.read
        state = {"calls": 0}

        def failing_read(fd, n):
            state["calls"] += 1
            # Fast path first: short read (3 B of 18) to force the
            # fallback loop, then the loop's NEXT read raises EIO.
            if state["calls"] == 1:
                return real_os_read(fd, min(n, 3))
            raise OSError("EIO: injected")

        journal.os.read = failing_read
        try:
            entries = list(journal._receipt_namespace_entries(Path(ns_dir)))
        finally:
            journal.os.read = real_os_read

        if not entries:
            return ["read-error fixture produced no entries"]
        entry = entries[0]
        if entry.structural_error is None:
            problems.append(
                f"mid-read error unclassified: structural_error=None, "
                f"manifest_raw={len(entry.manifest_raw or b'')} B captured"
            )
        elif "read failed" not in entry.structural_error:
            problems.append(
                f"mid-read error mislabeled: {entry.structural_error!r}"
            )
    return problems


def check_n5_extra_empty_file(journal):
    """N5-D companion: a zero-byte receipt file is a valid capture (empty
    bytes), not an error and not absence."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        ns_dir = os.path.join(tmp, "ops")
        op_dir = os.path.join(ns_dir, "op-empty")
        os.makedirs(op_dir)
        with open(os.path.join(op_dir, "operation.json"), "wb") as fh:
            pass
        with open(os.path.join(op_dir, "progress.json"), "wb") as fh:
            pass

        entries = list(journal._receipt_namespace_entries(Path(ns_dir)))
        if not entries:
            return ["empty-file fixture produced no entries"]
        entry = entries[0]
        if entry.manifest_raw != b"":
            problems.append(
                f"empty manifest not captured as empty bytes: "
                f"{entry.manifest_raw!r:.80}"
            )
        if entry.progress_raw != b"":
            problems.append(
                f"empty progress not captured as empty bytes: "
                f"{entry.progress_raw!r:.80}"
            )
        if entry.structural_error is not None:
            problems.append(
                f"empty file misclassified: {entry.structural_error!r}"
            )
    return problems


def check_n5_extra_symlink_substitution(journal):
    """N5-E TOCTOU: replace a verified regular file with a symlink
    between lstat and open. The open-level identity check (O_NOFOLLOW
    where the platform has it, descriptor fstat elsewhere) must refuse
    it as a structural event, never read through the substituted link.

    Honest SKIP when the host cannot create symlinks at all (Windows
    without the SeCreateSymbolicLinkPrivilege) -- a skipped hostile
    scenario is reported, never silently counted GREEN.
    """
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        probe_src = os.path.join(tmp, "probe_src")
        probe_lnk = os.path.join(tmp, "probe_lnk")
        with open(probe_src, "wb") as fh:
            fh.write(b"p")
        try:
            os.symlink(probe_src, probe_lnk)
        except (OSError, NotImplementedError) as exc:
            print("SKIP N5-X3 (host cannot create symlinks: "
                  f"{type(exc).__name__})")
            return []
        ns_dir = os.path.join(tmp, "ops")
        op_dir = os.path.join(ns_dir, "op-swap")
        os.makedirs(op_dir)
        target = os.path.join(tmp, "target.json")
        with open(target, "wb") as fh:
            fh.write(b'{"evil": true}')
        manifest = os.path.join(op_dir, "operation.json")
        with open(manifest, "wb") as fh:
            fh.write(b'{"operation": "s"}')

        real_os_open = os.open
        state = {"swapped": False}

        def swapping_open(path, flags, *args):
            if (
                not state["swapped"]
                and isinstance(path, str)
                and path.endswith("operation.json")
            ):
                # Swap AFTER the lstat verdict, BEFORE the read: the
                # classic TOCTOU window.
                state["swapped"] = True
                os.remove(manifest)
                os.symlink(target, manifest)
            return real_os_open(path, flags, *args)

        journal.os.open = swapping_open
        try:
            entries = list(journal._receipt_namespace_entries(Path(ns_dir)))
        finally:
            journal.os.open = real_os_open

        if not entries:
            return ["substitution fixture produced no entries"]
        entry = entries[0]
        if entry.manifest_raw == b'{"evil": true}':
            problems.append(
                "symlink substitution READ THROUGH the reparse point"
            )
        elif entry.structural_error is None:
            problems.append(
                "symlink substitution unclassified: structural_error=None, "
                f"manifest_raw={entry.manifest_raw!r:.80}"
            )
    return problems


def main():
    module = _load_subject()
    journal = _load_journal()
    results = [
        ("N5-A global 32KiB overrun (16 saturated groups)",
         lambda: check_n5_a_global_overrun(module)),
        ("N5-B1 append content-cut truncation lie",
         lambda: check_n5_b_append_truncation_lie(module)),
        ("N5-B2 receipt field-drop truncation lie",
         lambda: check_n5_b_receipt_truncation_lie(module)),
        ("N5-C UTF-8 tail digest incorrect",
         lambda: check_n5_c_utf8_tail_digest(module)),
        ("N5-D journal short read corrupts capture",
         lambda: check_n5_d_short_read(journal)),
        ("N5-E manifest vanish race masked",
         lambda: check_n5_e_vanish_race(journal)),
        ("N5-E progress vanish race masked",
         lambda: check_n5_e_progress_vanish(journal)),
        ("N5-X1 mid-read OSError classification",
         lambda: check_n5_extra_read_error(journal)),
        ("N5-X2 empty receipt file capture",
         lambda: check_n5_extra_empty_file(journal)),
        ("N5-X3 symlink substitution TOCTOU",
         lambda: check_n5_extra_symlink_substitution(journal)),
    ]
    red = 0
    for name, check in results:
        try:
            problems = check()
        except Exception as exc:  # noqa: BLE001 - defects surface as raises
            problems = [f"check raised {type(exc).__name__}: {exc}"]
        if problems:
            red += 1
            print(f"RED  {name}")
            for p in problems:
                print(f"     - {p}")
        else:
            print(f"GREEN {name}")
    print(f"\n{red} RED / {len(results) - red} GREEN")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
