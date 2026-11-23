"""Night-shift-4 RED reproductions for `_agent_view_payload`.

Run from the repository root:

    python tools/regression_t2089/t2089_p0_night4.py

Each check prints RED (defect reproduced) or GREEN (defect fixed). The
script exercises the live `tools/saipen.py` module directly, exactly like
`t2089_p0_repro.py` and `t2089_p0_stress.py`.

Handoff cases (SAIHANDOFF_SAIPEN_HYPERLEAN_NIGHT_SHIFT_4):
- N4-A  JSONDecodeError on a long root ID (truncated-JSON round-trip);
- N4-B  nested `distribution` (1 MB), nested `conformance_status` (200 KB)
        and a 200 000-char `shared_blocker_id` all bypass the byte budget
        while `truncated` stays false;
- N4-C  the projection deep-copies kept structures via
        json.loads(json.dumps(value)) -- measured serialized work on input
        bytes far beyond the envelope budget;
- N4-E  `_cap_digest` joins values with "\n" -- ambiguous encoding:
        ["a\\nb", "c"] and ["a", "b\\nc"] hash identically;
- N4-D  dead `for group in groups: pass` loop (source scan).
"""

import importlib.util
import json
import os
import sys

SUBJECT = os.path.join("tools", "saipen.py")
HARD_BUDGET_BYTES = 32 * 1024


def _load_subject():
    sys.path.insert(0, "tools")
    spec = importlib.util.spec_from_file_location("saipen", SUBJECT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["saipen"] = module
    spec.loader.exec_module(module)
    return module


def _group(i, roots=2, deps=1, root_len=None, blocker_len=None):
    roots_list = [f"T-{i}-{j}" for j in range(roots)] if root_len is None \
        else ["R" * root_len]
    return {
        "shared_blocker_id": ("EX-%06d" % i) if blocker_len is None
        else "B" * blocker_len,
        "blocker_class": "WAIT_USER_DECISION",
        "cause": f"cause {i}",
        "owner": "saipen-cli",
        "root_tickets": roots_list,
        "dependent_tickets": [f"T-dep-{i}-{j}" for j in range(deps)],
        "recovery_internally_authorized": False,
        "external_input_required": True,
        "read_only_work_may_proceed": True,
    }


def check_n4_a_long_root_id(module):
    """N4-A: a ~5000-char root ID must not raise; counts stay exact."""
    payload = {
        "ok": True,
        "code": "STATUS_OK",
        "blocker_projection": {
            "groups": [_group(0, roots=1, root_len=5000)],
            "items": ["T-item-0"],
        },
    }
    try:
        view = module._agent_view_payload(payload)
    except Exception as exc:  # noqa: BLE001 - the defect IS an exception
        return [f"long root ID raised {type(exc).__name__}: {exc}"]
    groups = view.get("blocker_groups") or []
    if not groups or groups[0].get("root_ticket_count") != 1:
        return [f"root_ticket_count lost: {groups!r:.400}"]
    return []


def check_n4_b_nested_byte_budget(module):
    """N4-B: nested 1 MB distribution / 200 KB conformance / 200 KB blocker
    id must keep the serialized view under 32 KiB with honest truncation."""
    problems = []

    def run(payload, label):
        view = module._agent_view_payload(payload)
        blob = json.dumps(view, ensure_ascii=False).encode("utf-8")
        if len(blob) > HARD_BUDGET_BYTES:
            problems.append(f"{label}: serialized view {len(blob)} B > 32 KiB")
        if not view.get("truncated"):
            problems.append(f"{label}: truncated=false while bytes were cut")

    run(
        {"ok": True, "code": "STATUS_OK",
         "distribution": {"payload": "X" * 1_000_000}},
        "nested distribution 1MB",
    )
    run(
        {"ok": True, "code": "STATUS_OK",
         "conformance_status": {"side": "Y" * 200_000}},
        "nested conformance_status 200KB",
    )
    run(
        {"ok": True, "code": "STATUS_OK",
         "blocker_projection": {
             "groups": [_group(0, blocker_len=200_000)],
             "items": ["T-item-0"],
         }},
        "shared_blocker_id 200KB",
    )
    return problems


def check_n4_c_projection_cost(module):
    """N4-C: building a <=32 KiB view must not serialize megabytes of input
    through the json.loads(json.dumps()) copy path."""
    big = "Z" * 1_000_000
    payload = {
        "ok": True,
        "code": "STATUS_OK",
        "distribution": {"payload": big},
        "convergence": {"notes": big},
    }
    import tracemalloc

    tracemalloc.start()
    view = module._agent_view_payload(payload)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    blob = json.dumps(view, ensure_ascii=False).encode("utf-8")
    problems = []
    if len(blob) > HARD_BUDGET_BYTES:
        problems.append(f"view {len(blob)} B > 32 KiB budget")
    # The bounded envelope is ~<=32 KiB; a deep-copy implementation peaks at
    # the full kept-bytes volume (>= 1 MB here). Guard at 8x budget headroom
    # so only copy-volume blowups trip it, not ordinary small allocs.
    if peak > 8 * HARD_BUDGET_BYTES:
        problems.append(
            f"projection peak memory {peak} B for a {len(blob)} B view "
            "(deep-copy cost, not a bounded build)"
        )
    return problems


def check_n4_e_digest_ambiguity(module):
    """N4-E: the cap digest must be an unambiguous encoding of its items.

    Root-ticket overflow digests ["a\\nb", "c"] vs ["a", "b\\nc"]: a
    newline-joined preimage collides; a length-framed one cannot. Also:
    the same list must digest identically on repeated runs, and an empty
    or missing list must never crash the digest path.
    """
    problems = []

    def overflow_digest(overflow_tail):
        # 40 short roots force the bounded (slow) path; the ambiguity pair
        # rides in the overflow region past the 8 kept rows.
        roots = [f"T-short-{i}" for i in range(38)] + overflow_tail
        group = {
            "shared_blocker_id": "EX-000000",
            "blocker_class": "WAIT_USER_DECISION",
            "cause": "cause 0",
            "owner": "saipen-cli",
            "root_tickets": roots,
            "dependent_tickets": [],
            "recovery_internally_authorized": False,
            "external_input_required": True,
            "read_only_work_may_proceed": True,
        }
        payload = {
            "ok": True,
            "code": "STATUS_OK",
            "blocker_projection": {"groups": [group], "items": []},
        }
        view = module._agent_view_payload(payload)
        g = (view.get("blocker_groups") or [{}])[0]
        roots_out = g.get("root_tickets") or []
        marker = next((r for r in roots_out if isinstance(r, dict)), None)
        return marker

    marker_a = overflow_digest(["a\nb", "c"])
    marker_b = overflow_digest(["a", "b\nc"])
    if marker_a is None or marker_b is None:
        problems.append("root overflow digest marker missing")
    else:
        if marker_a.get("overflow_sha256") == marker_b.get("overflow_sha256"):
            problems.append(
                "digest ambiguous across element splits: "
                f"{marker_a.get('overflow_sha256')} == "
                f"{marker_b.get('overflow_sha256')}"
            )
        if marker_a.get("overflow_count") != 32:
            problems.append(
                f"overflow_count={marker_a.get('overflow_count')}, expected 32"
            )
    # Same input twice -> identical digest (stable framing, stable order).
    m1 = overflow_digest(["a\nb", "c"])
    m2 = overflow_digest(["a\nb", "c"])
    if m1 is None or m2 is None or m1.get("overflow_sha256") != m2.get("overflow_sha256"):
        problems.append("digest unstable across identical inputs")
    # Empty/missing lists must never crash.
    try:
        module._agent_view_payload(
            {"ok": True, "code": "STATUS_OK",
             "blocker_projection": {"groups": [], "items": []}}
        )
        module._agent_view_payload({"ok": True, "code": "STATUS_OK"})
    except Exception as exc:  # noqa: BLE001
        problems.append(f"empty projection raised {type(exc).__name__}: {exc}")
    return problems


def check_n4_d_dead_loop(module):
    """N4-D: no empty placeholder loop over blocker groups may remain."""
    with open(SUBJECT, "r", encoding="utf-8") as fh:
        source = fh.read()
    marker = "for group in groups:\n"
    idx = source.find(marker)
    while idx != -1:
        chunk = source[idx: idx + len(marker) + 80]
        body = chunk[len(marker):].lstrip()
        if body.startswith("pass"):
            return [f"dead loop at byte {idx}: {chunk.splitlines()[1].strip()!r}"]
        idx = source.find(marker, idx + 1)
    return []


def main():
    module = _load_subject()
    results = [
        ("N4-A long root ID", check_n4_a_long_root_id),
        ("N4-B nested byte budget", check_n4_b_nested_byte_budget),
        ("N4-C projection cost", check_n4_c_projection_cost),
        ("N4-D dead loop", check_n4_d_dead_loop),
        ("N4-E digest ambiguity", check_n4_e_digest_ambiguity),
    ]
    red = 0
    for name, check in results:
        try:
            problems = check(module)
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
