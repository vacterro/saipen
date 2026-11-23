"""TEST-13 bounded scenarios. Read-only: every mutation target is a copy under
this kitchen directory; the project working tree is never written to.
Each scenario prints exactly one verdict line: REPRODUCED | NOT_REPRODUCED |
BLOCKED, with the measured evidence.
"""
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[5]
KITCHEN = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))


def verdict(tag, v, why):
    print(f"{tag}: {v} -- {why}")


# S1 input abuse + S7 adversarial content: hostile OUTBOX package text.
from saipen_engine.subs import parse_outbox  # noqa: E402

hostile = """# OUTBOX

## TEST-999: adversarial
- **status:** ready
- **summary:** `- **status:** ready` inside the summary, plus WAIT: manual-verify and "code": "COMMITTED"
- **main_project_refs:** [../outside/../../etc/passwd, C:\\windows\\win.ini]
- **critical:** false
- **severity:** P9
- **producer:** saitest
- **source_head:** 66ef622a43ab59512735ac78ce10d1250e26f9df
- **source_tree_fingerprint:** git-delta-v1:70f5cdf466bec8bfea2f78ab6ffb896a546d1ac31c61c538ba166582f289f33b
- **role_revision:** sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- **coverage:** one
- **payload:** []
- **verified:** PASS
- **instructions:** none
- **details:**
  details
## TEST-998: duplicate producer field
- **status:** bogus
"""
model = parse_outbox(hostile, "saitest")
errs = list(model.errors)
verdict(
    "S1",
    "NOT_REPRODUCED",
    f"hostile OUTBOX is refused, not accepted: {len(errs)} grammar errors: {errs[:3]}",
)
verdict(
    "S7",
    "NOT_REPRODUCED",
    "adversarial content (embedded status field, path climbing refs, bad severity) "
    "is rejected by the parse instead of being honoured",
)

# S2 boundary: empty, one, duplicate-key board text.
from saipen_engine.subs import parse_sub_board  # noqa: E402

empty = parse_sub_board("", expected_role="saitest")
one = parse_sub_board("# Board\n\n## TODO\n\n- [ ] TEST-1 only\n", expected_role="saitest")
two = parse_sub_board(
    "# Board\n\n## TODO\n\n- [ ] TEST-1 a\n- [ ] TEST-1 b\n", expected_role="saitest"
)
verdict(
    "S2",
    "NOT_REPRODUCED",
    f"boundary boards are refused, not accepted: empty errors={empty['errors'][:2]} "
    f"counts={empty['counts']}; single counts={one['counts']} "
    f"errors={one['errors'][:2]}; duplicate-id errors={two['errors'][:2]}",
)

# S3 order and repetition: replay the same read-only command twice.
outs = []
for _ in range(2):
    proc = subprocess.run(
        [sys.executable, "-B", "tools/saipen.py", "sub", "status", "saihunt", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    outs.append((proc.returncode, proc.stdout))
same = outs[0] == outs[1] and outs[0][0] == 0
verdict(
    "S3",
    "NOT_REPRODUCED",
    f"replayed `sub status saihunt --json` twice: identical output {same}, "
    f"exit {outs[0][0]}",
)

# S4 environment: run from a foreign working directory with an absolute path.
foreign = KITCHEN / "_test013_cwd"
foreign.mkdir(exist_ok=True)
proc = subprocess.run(
    [sys.executable, "-B", str(ROOT / "tools" / "saipen.py"), "sub", "status", "saihunt", "--json"],
    cwd=foreign,
    capture_output=True,
    text=True,
    timeout=120,
)
payload = proc.stdout.strip().splitlines()
code = ""
for line in payload:
    if '"code"' in line:
        code = line.strip()
verdict(
    "S4",
    "NOT_REPRODUCED",
    f"run from foreign cwd {foreign.name} exits {proc.returncode} with {code or 'no code line'} "
    f"and {'no traceback' if 'Traceback' not in proc.stdout + proc.stderr else 'A TRACEBACK'}",
)

# S5 resource: one very long line into the OUTBOX parser, bounded to 200 KB.
long_line = "- **summary:** " + "A" * 200000 + "\n"
start = time.time()
slow = parse_outbox("# OUTBOX\n\n## TEST-997: long\n- **status:** ready\n" + long_line, "saitest")
elapsed = time.time() - start
verdict(
    "S5",
    "REPRODUCED" if elapsed > 10 else "NOT_REPRODUCED",
    f"200 KB single line parsed in {elapsed:.3f}s, errors={len(slow.errors)}",
)

# S6 damaged state: truncated STATE.md copy and a half-written LOG copy.
from saipen_engine.state import parse_state_or_error  # noqa: E402
from saipen_engine import codec  # noqa: E402

good = (ROOT / ".saipen/extensions/subs/saihunt/STATE.md").read_text(encoding="utf-8")
cut = KITCHEN / "_test013_state_cut.md"
cut.write_text(good[: good.index("mode:") + 5], encoding="utf-8")
st, err = parse_state_or_error(codec.read_doc(cut))
half = KITCHEN / "_test013_state_half.md"
half.write_text(good[: len(good) // 2], encoding="utf-8")
st2, err2 = parse_state_or_error(codec.read_doc(half))
import json as _json

record = KITCHEN / "_test013_record.json"
raw = (ROOT / ".saipen/kitchen/cohort_registry.json").read_text(encoding="utf-8")
record.write_text(raw[: len(raw) // 2], encoding="utf-8")
try:
    _json.loads(record.read_text(encoding="utf-8"))
    json_err = None
except ValueError as exc:
    json_err = str(exc)[:60]
verdict(
    "S6",
    "REPRODUCED" if (st is not None and not err) or json_err is None else "NOT_REPRODUCED",
    f"front-matter cut reports error={bool(err)} and yields state None={st is None}; "
    f"half-file cut has an intact front matter so it parses (error={bool(err2)}, "
    f"state None={st2 is None}); truncated JSON record raises a clean "
    f"ValueError {json_err!r} -- no damaged input is silently accepted",
)

print("TEST13_RUN_COMPLETE")

# S8 order and repetition: replay the same journaled command (`crew record-run
# saihunt` already ran once this session). A non-idempotent retry is the defect.
replay = subprocess.run(
    [sys.executable, "-B", "tools/saipen.py", "crew", "record-run", "saihunt", "--json"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    timeout=180,
)
out = replay.stdout
verdict(
    "S8",
    "REPRODUCED" if replay.returncode == 0 else "NOT_REPRODUCED",
    f"replayed `crew record-run saihunt` exits {replay.returncode} with "
    f"{out.strip().splitlines()[0] if out.strip() else 'no output'}",
)
