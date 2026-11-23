"""Night-shift-6 RED reproductions for the four independently-audited P0s.

Run from the repository root:

    python tools/regression_t2089/t2089_p0_night6.py

Each check prints RED (defect reproduced) or GREEN (defect fixed). The
suite exercises the live repo engine (`tools/saipen.py` loaded as a
module, `tools/saipen_engine/journal.py` via package import), never an
installed home. All fault injection happens on hermetic temporary
directories; real `.saipen/recovery` trees are never touched.

Handoff cases (SAIHANDOFF_SAIPEN_HYPERLEAN_NIGHT_SHIFT_6):

- N6-A  `_bound_string` multi-chunk tail hashing breaks byte ORDER:
        chunks after the first dropped block feed the SHA256 before the
        first dropped block, so `dropped_tail_sha256` hashes
        `later_chunks + first_tail` instead of the real tail bytes.
        Short Night-5 cases hid this: their whole tail fit one chunk.
- N6-B  a regular file REPLACED by another regular file between lstat
        and open passes the type checks -- identity is never compared,
        so the capture silently blesses the substituted bytes.
- N6-C  a file that GROWS after fstat is accepted from one exact-size
        read: `len(data) == size` is treated as EOF proof and the
        appended bytes vanish without a verdict.
- N6-D  the 256 MiB hard cap sits only in the fallback loop; the
        initial read allocates whatever st_size says, so a huge sparse
        file overruns the cap before any check runs.

Adversarial pairs (the same file, inverted expectation) live in
`t2089_p0_night6_green.py` and document the intended contracts:

- N6-A  for every input, dropped_tail_sha256 == sha256(original_utf8
        [kept_utf8_bytes:]) -- exact bytes, exact order.
- N6-B  identity (st_dev, st_ino) through the descriptor must match
        the pre-open observation, or the capture refuses fail-closed.
- N6-C  growth between fstat and EOF probe is a named structural
        refusal, never a silently truncated capture.
- N6-D  no execution path may request a read larger than the cap
        without a prior bound check.
"""

import hashlib
import importlib.util
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


def _authority_cut(module, value):
    """The next_action authority cut marker for one value, or None."""
    payload = {"ok": True, "next_action": value}
    view = module._agent_view_payload(payload)
    cuts = view.get("authority_text_truncation") or {}
    for cut in cuts.get("cuts") or ():
        if cut.get("key") == "next_action":
            return cut
    return None


def check_n6_a_multichunk_digest_order(module):
    """N6-A: multi-chunk tails must hash the dropped bytes IN ORDER."""
    problems = []
    cases = [
        # ~1.1 chunk of ASCII: the first tail chunk is distinctive.
        ("abc" * 35000, 512),
        # 2 chunks: order flip between two distinct tail blocks.
        ("x" * 32768 + "y" * 32768 + "z" * 100, 512),
        # 3 chunks: three distinct ordered blocks in the tail.
        ("a" * 32768 + "b" * 32768 + "c" * 32768 + "d" * 40, 512),
        # 10 chunks, alternating bytes: any reordering shows.
        ("ab" * 163840, 512),
        # Mixed ASCII/multibyte straddling chunk boundaries.
        ("A" * 32760 + "€é😀" * 12000, 512),
    ]
    for value, budget in cases:
        cut = _authority_cut(module, value)
        if cut is None:
            problems.append("cut marker missing")
            continue
        original = value.encode("utf-8")
        expected = hashlib.sha256(original[cut.get("kept_utf8_bytes", 0):]).hexdigest()
        if cut.get("dropped_tail_sha256") != expected:
            problems.append(
                f"len={len(original)} B: dropped-tail digest hashes the wrong "
                f"byte order: got {cut.get('dropped_tail_sha256')}, "
                f"expected {expected}"
            )
        if cut.get("dropped_tail_bytes") != len(original) - cut.get("kept_utf8_bytes", 0):
            problems.append(
                f"len={len(original)} B: dropped_tail_bytes="
                f"{cut.get('dropped_tail_bytes')} != "
                f"{len(original) - cut.get('kept_utf8_bytes', 0)}"
            )
    return problems


def check_n6_a_property_oracle(module):
    """N6-A property: seeded random strings, 1..10 chunks, honest oracle."""
    import random

    problems = []
    rng = random.Random(20261118)
    alphabet = "Aa€é😀\r\n\t"
    for trial in range(40):
        n = rng.randrange(1, 12) * 32768 + rng.randrange(0, 200)
        value = "".join(rng.choice(alphabet) for _ in range(n))
        cut = _authority_cut(module, value)
        if cut is None:
            problems.append(f"trial {trial}: cut marker missing")
            continue
        original = value.encode("utf-8")
        kept = cut.get("kept_utf8_bytes", 0)
        expected = hashlib.sha256(original[kept:]).hexdigest()
        if cut.get("dropped_tail_sha256") != expected:
            problems.append(
                f"trial {trial} ({n} chars): dropped-tail digest wrong"
            )
            if len(problems) > 3:
                break
    return problems


def _receipt_fixture(tmp, op_name, manifest_bytes):
    ns_dir = os.path.join(tmp, "ops")
    op_dir = os.path.join(ns_dir, op_name)
    os.makedirs(op_dir, exist_ok=True)
    manifest = os.path.join(op_dir, "operation.json")
    with open(manifest, "wb") as fh:
        fh.write(manifest_bytes)
    return ns_dir, op_dir, manifest


def check_n6_b_regular_file_substitution(journal):
    """N6-B: replacing the regular file between lstat and open with
    ANOTHER regular file must be refused, not blessed."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        ns_dir, _op_dir, manifest = _receipt_fixture(
            tmp, "op-swap", b"AAAA-ORIGINAL"
        )
        replacement = os.path.join(tmp, "operation.new")
        with open(replacement, "wb") as fh:
            fh.write(b"BBBB-REPLACED")

        real_os_open = os.open
        state = {"swapped": False}

        def swapping_open(path, flags, *args):
            if not state["swapped"] and isinstance(path, str) \
                    and path == manifest:
                state["swapped"] = True
                os.replace(replacement, manifest)
            return real_os_open(path, flags, *args)

        journal.os.open = swapping_open
        try:
            entries = {
                e.name: e for e in journal._receipt_namespace_entries(Path(ns_dir))
            }
        finally:
            journal.os.open = real_os_open

        entry = entries.get("op-swap")
        if entry is None:
            return ["substitution fixture produced no entry"]
        if entry.manifest_raw == b"BBBB-REPLACED" and entry.structural_error is None:
            problems.append(
                "regular-file substitution ACCEPTED: manifest_raw is the "
                "replacement's bytes with structural_error=None"
            )
        elif entry.structural_error is None:
            problems.append(
                "regular-file substitution unclassified: "
                f"manifest_raw={entry.manifest_raw!r:.60}"
            )
    return problems


def check_n6_c_growth_after_fstat(journal):
    """N6-C: a file that grows between fstat and read must not pass as
    a complete exact-byte capture."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        ns_dir, _op_dir, manifest = _receipt_fixture(
            tmp, "op-grow", b"12345678"
        )

        real_os_read = os.read
        state = {"grown": False}

        def growing_read(fd, n):
            if not state["grown"]:
                state["grown"] = True
                with open(manifest, "ab") as fh:
                    fh.write(b"APPENDED")
            return real_os_read(fd, n)

        journal.os.read = growing_read
        try:
            entries = {
                e.name: e for e in journal._receipt_namespace_entries(Path(ns_dir))
            }
        finally:
            journal.os.read = real_os_read

        entry = entries.get("op-grow")
        if entry is None:
            return ["growth fixture produced no entry"]
        if entry.manifest_raw == b"12345678" and entry.structural_error is None:
            problems.append(
                "growth after fstat: 8 of 16 bytes captured as a COMPLETE "
                "read with structural_error=None"
            )
    return problems


def check_n6_d_oversized_initial_read(journal):
    """N6-D: a 257 MiB (sparse) file must hit the cap BEFORE any read
    request of that size is issued."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        ns_dir, op_dir, manifest = _receipt_fixture(tmp, "op-cap", b"")
        cap = 257 * 1024 * 1024
        with open(manifest, "wb") as fh:
            fh.truncate(cap)
        with open(os.path.join(op_dir, "progress.json"), "wb") as fh:
            fh.write(b"{}")

        real_os_read = os.read
        biggest = {"n": 0}

        def capped_probe(fd, n):
            biggest["n"] = max(biggest["n"], n)
            # Serve a tiny slice without materializing 257 MiB.
            return real_os_read(fd, min(n, 4096))

        journal.os.read = capped_probe
        try:
            entries = {
                e.name: e for e in journal._receipt_namespace_entries(Path(ns_dir))
            }
        finally:
            journal.os.read = real_os_read

        entry = entries.get("op-cap")
        if entry is None:
            return ["cap fixture produced no entry"]
        # Acceptance: no execution path may REQUEST a read beyond the cap
        # without prior control -- the verdict alone is not the contract.
        if biggest["n"] > journal._RECEIPT_READ_HARD_CAP:
            problems.append(
                f"oversized file: os.read REQUESTED {biggest['n']} B "
                f"(> {journal._RECEIPT_READ_HARD_CAP}) -- the cap does "
                "not guard the initial read"
            )
        elif entry.structural_error is None:
            problems.append("oversized file: accepted without a cap verdict")
    return problems


def check_n6_extra_shrink_during_read(journal):
    """N6-X1: a file that shrinks mid-read must classify, not silently
    capture a hole."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        ns_dir, _op_dir, manifest = _receipt_fixture(
            tmp, "op-shrink", b"S" * 65536
        )

        real_os_read = os.read
        state = {"shrunk": False}

        def shrinking_read(fd, n):
            if not state["shrunk"]:
                state["shrunk"] = True
                with open(manifest, "r+b") as fh:
                    fh.truncate(1024)
            return real_os_read(fd, n)

        journal.os.read = shrinking_read
        try:
            entries = {
                e.name: e for e in journal._receipt_namespace_entries(Path(ns_dir))
            }
        finally:
            journal.os.read = real_os_read

        entry = entries.get("op-shrink")
        if entry is None:
            return ["shrink fixture produced no entry"]
        if entry.manifest_raw == b"S" * 1024 and entry.structural_error is None:
            problems.append(
                "shrink during read: 1024 B of a 64 KiB file captured as "
                "complete with structural_error=None"
            )
    return problems


def check_n6_base_immutable_capture(journal):
    """BASE: an untouched healthy receipt captures exact bytes with no
    verdict -- the fail-closed additions must not poison the healthy
    path (invariant I7)."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        manifest_bytes = b'{"operation": "n6-base"}'
        progress_bytes = b'{"state": "ok"}'
        ns_dir, op_dir, _manifest = _receipt_fixture(tmp, "op-base", manifest_bytes)
        with open(os.path.join(op_dir, "progress.json"), "wb") as fh:
            fh.write(progress_bytes)
        entries = {
            e.name: e for e in journal._receipt_namespace_entries(Path(ns_dir))
        }
        entry = entries.get("op-base")
        if entry is None:
            return ["base fixture produced no entry"]
        if entry.manifest_raw != manifest_bytes or entry.progress_raw != progress_bytes:
            problems.append(
                f"immutable capture changed: manifest={entry.manifest_raw!r:.40} "
                f"progress={entry.progress_raw!r:.40}"
            )
        if entry.structural_error is not None:
            problems.append(
                f"immutable capture refused: {entry.structural_error!r}"
            )
    return problems


def check_n6_base_growth_during_loop(journal):
    """BASE: growth that lands AFTER the fallback loop's EOF is a
    refusal (completeness), and the refusal is named, not a crash."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        ns_dir, _op_dir, manifest = _receipt_fixture(tmp, "op-loop", b"")
        # Force the fallback loop: first read returns short.
        real_os_read = os.read
        state = {"calls": 0}

        def short_then_append(fd, n):
            state["calls"] += 1
            if state["calls"] == 1:
                with open(manifest, "wb") as fh:
                    fh.write(b"FIRST")
                return real_os_read(fd, min(n, 4))
            if state["calls"] == 2:
                with open(manifest, "ab") as fh:
                    fh.write(b"APPENDED")
                return real_os_read(fd, min(n, 7))
            return real_os_read(fd, n)

        journal.os.read = short_then_append
        try:
            entries = {
                e.name: e for e in journal._receipt_namespace_entries(Path(ns_dir))
            }
        finally:
            journal.os.read = real_os_read

        entry = entries.get("op-loop")
        if entry is None:
            return ["loop fixture produced no entry"]
        if entry.structural_error is None:
            problems.append(
                "growth during the fallback loop captured silently: "
                f"manifest_raw={entry.manifest_raw!r:.40}"
            )
    return problems


def check_n6_base_shrink_before_read(journal):
    """BASE: a shrink that completes before the read is captured as the
    file's real current bytes -- the fstat inside the read window owns
    the size, so a stable smaller file is a lawful complete capture."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        manifest_bytes = b'{"operation": "small-now"}'
        ns_dir, _op_dir, manifest = _receipt_fixture(tmp, "op-small", b"S" * 65536)

        real_os_open = os.open
        state = {"shrunk": False}

        def shrinking_open(path, flags, *args):
            if not state["shrunk"] and isinstance(path, str) and path == manifest:
                state["shrunk"] = True
                with open(manifest, "r+b") as fh:
                    fh.truncate(0)
                    fh.write(manifest_bytes)
            return real_os_open(path, flags, *args)

        journal.os.open = shrinking_open
        try:
            entries = {
                e.name: e for e in journal._receipt_namespace_entries(Path(ns_dir))
            }
        finally:
            journal.os.open = real_os_open

        entry = entries.get("op-small")
        if entry is None:
            return ["shrink-before fixture produced no entry"]
        if entry.manifest_raw != manifest_bytes or entry.structural_error is not None:
            problems.append(
                f"shrink-before-read: expected exact new bytes with no "
                f"verdict, got manifest={entry.manifest_raw!r:.40} "
                f"error={entry.structural_error!r}"
            )
    return problems


def check_n6_extra_human_renderer_marker_rows(module):
    """N6-X2: the human `_emit` renderer must accept the bounded
    agent-view's truncation-marker rows in `waiting_on_you` -- a dict
    row carrying `text` crashed the string join (measured live:
    `status --view agent` exited rc=1 with TypeError). The human half
    renders the marker's text; the machine half stays unchanged."""
    import io
    import contextlib

    problems = []
    waits = [
        "T-1: plain row",
        {
            "byte_budget_exceeded": True,
            "original_utf8_bytes": 509,
            "kept_utf8_bytes": 240,
            "dropped_tail_bytes": 269,
            "dropped_tail_sha256": "ab" * 32,
            "full_value_ref": "saipen status --json",
            "text": "T-2084: WAIT_USER_DECISION -- bounded row text",
        },
    ]
    view = module._agent_view_payload({"ok": True, "waiting_on_you": waits})
    # The agent view itself must have kept both rows in a serializable form.
    rows = view.get("waiting_on_you")
    if not isinstance(rows, list) or len(rows) < 1:
        return ["agent view dropped waiting_on_you entirely"]
    # The human renderer consumes the PAYLOAD (as --view agent emits it
    # through _emit); a marker row must not crash it.
    payload = {"ok": True, "code": "STATUS_OK", "waiting_on_you": rows}
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            module._emit(payload, False)
    except TypeError as exc:
        problems.append(
            f"human renderer crashed on marker row: {type(exc).__name__}: {exc}"
        )
    out = buffer.getvalue()
    if "T-2084: WAIT_USER_DECISION -- bounded row text" not in out:
        problems.append("human renderer lost the marker row's text")
    if "T-1: plain row" not in out:
        problems.append("human renderer lost the plain row")
    return problems


def main():
    module = _load_subject()
    journal = _load_journal()
    results = [
        ("N6-A multi-chunk tail digest order",
         lambda: check_n6_a_multichunk_digest_order(module)),
        ("N6-A property oracle (seeded)",
         lambda: check_n6_a_property_oracle(module)),
        ("N6-B regular-file substitution accepted",
         lambda: check_n6_b_regular_file_substitution(journal)),
        ("N6-C growth after fstat misclassified",
         lambda: check_n6_c_growth_after_fstat(journal)),
        ("N6-D oversized initial read unguarded",
         lambda: check_n6_d_oversized_initial_read(journal)),
        ("N6-X1 shrink during read misclassified",
         lambda: check_n6_extra_shrink_during_read(journal)),
        ("N6-X2 human renderer marker rows",
         lambda: check_n6_extra_human_renderer_marker_rows(module)),
        ("N6-BASE immutable capture unchanged",
         lambda: check_n6_base_immutable_capture(journal)),
        ("N6-BASE growth during fallback loop",
         lambda: check_n6_base_growth_during_loop(journal)),
        ("N6-BASE shrink before read window",
         lambda: check_n6_base_shrink_before_read(journal)),
    ]
    red = 0
    for name, check in results:
        try:
            problems = check()
        except Exception as exc:
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
