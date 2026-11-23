#!/usr/bin/env python3
"""Pure decision engine for SAISPIN, the orphan CPU watchdog.

No Windows API, no process enumeration, no termination, no tray, no scheduler.
It answers exactly one question about data somebody else collected: given this
process's hot/cold history and the current sample, IGNORE, ALERT or KILL?

Keeping the answer here is the whole point. The rules below were written from
two real incidents and one counterexample, and every one of them is a rule
where being wrong is invisible until it kills the wrong process:

* one CPU spike is not evidence. Only a CONSECUTIVE hot streak counts, so a
  compiler that pegs a core for twenty seconds never registers;
* an orphan is not a kill target. The orphaned ``pytest`` processes that
  started this design were sleeping at ~0% CPU -- the majority case;
* a spinning process with a live parent is never killed automatically. It is
  usually a compiler, an encoder, an indexer or a test run doing its job;
* PID is not identity. PID + StartTime is, so a reused PID starts from zero
  instead of inheriting a dead process's strikes;
* missing or untrusted information biases toward NOT killing.

The engine is the same code the watcher runs and the tests exercise, so the
safety logic can be proven without spawning a single real spinning process:

    python tests/test_saispin.py

The watcher feeds it one JSON sweep per invocation on stdin and reads the
decisions plus the next state back out on stdout:

    ... | python Scripts/saispin_logic.py --sweep
"""

from __future__ import annotations

import dataclasses
import json
import copy
import math
import os
import sys
from datetime import datetime, timezone

# A sample above this share of ONE logical core is "hot". 80% leaves room for a
# busy-but-useful process to breathe while still catching a real spin loop,
# which sits at ~100% of one core by definition.
HOT_CPU_PERCENT = 80.0

# Sustained spin needs BOTH: enough consecutive hot samples AND enough wall
# clock. Hits alone would trip on a watcher that ran six times in a minute;
# elapsed time alone would trip on one hot sample half an hour after another.
SUSTAINED_HITS = 6
SUSTAINED_SECONDS = 30 * 60

# The watcher sweeps every five minutes, so two hot samples further apart than
# this were not consecutive OBSERVATIONS of anything: the machine slept, the task
# was disabled, or the watcher was off. The process could have been idle for the
# entire gap and nobody was watching, which is exactly the "stale history" a kill
# may not come from. Such a sample starts a fresh streak instead of extending an
# old one. Six times the cadence, so an ordinary late or skipped run is tolerated.
STALE_GAP_SECONDS = 30 * 60

# The sampling window the watcher uses between its two CPU readings.
SAMPLE_SECONDS = 3

# Command lines are unbounded and balloon tips are not. The full text belongs
# in the structured log; this is what the notification and state file carry.
CMDLINE_LIMIT = 200

IGNORE = "IGNORE"
ALERT = "ALERT"
KILL = "KILL"

# Classification constants (Phase 7)
CLASSIFICATION_PROTECTED_ACTIVE = "PROTECTED_ACTIVE"
CLASSIFICATION_PROTECTED_SYSTEM = "PROTECTED_SYSTEM"
CLASSIFICATION_PROTECTED_USER = "PROTECTED_USER"
CLASSIFICATION_OBSERVE_ONLY = "OBSERVE_ONLY"
CLASSIFICATION_SUSPECTED_STALL = "SUSPECTED_STALL"
CLASSIFICATION_RECOVERY_ELIGIBLE = "RECOVERY_ELIGIBLE"
CLASSIFICATION_UNKNOWN = "UNKNOWN"

# Killing any of these is a reboot, not a fix. Compared case-insensitively.
# "System Idle Process" is the name Windows actually reports for PID 0, and it
# is not an idle-looking name by accident: the Idle process accumulates CPU for
# every cycle NOBODY used, so on a quiet machine it reads as a permanent 100%
# spin with no parent. It belongs here, and PID_FLOOR below is the real guard.
NEVER_KILL = frozenset(
    {
        "system",
        "system idle process",
        "idle",
        "registry",
        "memory compression",
        "smss.exe",
        "csrss.exe",
        "wininit.exe",
        "services.exe",
        "lsass.exe",
        "winlogon.exe",
        # Windows desktop & system infrastructure
        "dwm.exe",
        "explorer.exe",
        "fontdrvhost.exe",
        "sihost.exe",
        "svchost.exe",
        "taskhostw.exe",
        "ctfmon.exe",
        "runtimebroker.exe",
        "shellexperiencehost.exe",
        "startmenuexperiencehost.exe",
        "searchapp.exe",
        "searchhost.exe",
        "searchindexer.exe",
        "spoolsv.exe",
        "audiodg.exe",
        "conhost.exe",
        "openconsole.exe",
        "windowsterminal.exe",
        # Security & Defender
        "securityhealthservice.exe",
        "securityhealthsystray.exe",
        "msmpeng.exe",
        "nissrv.exe",
        "smartscreen.exe",
        "mpcmdrun.exe",
        # Compilers & builders
        "csc.exe",
        "vbc.exe",
        "cl.exe",
        "link.exe",
        "msbuild.exe",
        "javac.exe",
        "rustc.exe",
        "cargo.exe",
        "go.exe",
        "gcc.exe",
        "g++.exe",
        "clang.exe",
        "clang++.exe",
        "cmake.exe",
        "ninja.exe",
        # Agents & task runners
        "antigravity.exe",
        "agy.exe",
        "claude.exe",
        "opencode.exe",
        # Media & encoders
        "obs64.exe",
        "obs32.exe",
        "obs.exe",
    }
)

# PIDs 0 and 4 are the Idle and System processes. They have no real parent, so
# every orphan test says orphan, and Idle accumulates CPU for every cycle NOBODY
# used -- on a quiet machine it reads as a permanent 100% spin. Found on the
# first live dry-run: PID 0 "System Idle Process" was the only tracked process
# on the whole machine, and left alone it would have produced a balloon every
# five minutes forever, which is how a useful alert becomes one nobody reads.
#
# Identity by number rather than by name, because the name is localized: on a
# Russian Windows PID 0 is "Бездействие системы" and no name list would match.
KERNEL_PIDS = frozenset({0, 4})
PID_FLOOR = 4

# Images whose ROOT process is protected while its children are not. VS Code
# spawns renderer, extension-host and language-server children that are fair
# game; killing the one process that owns the window is not. "Main" is decided
# by the caller (no live ancestor of the same image), because that is a
# process-tree fact, not something a name can carry.
MAIN_PROCESS_GUARDED = frozenset({"code.exe"})

# One validated settings model feeds the watcher, task installer, GUI and this
# engine. These defaults intentionally match the pre-settings constants below;
# a fresh install therefore behaves exactly like the old watchdog.
DEFAULT_SETTINGS = {
    "schema_version": 1,
    "thresholds": {
        "cpu_percent": 80.0,
        "required_hits": 6,
        "minimum_hot_minutes": 30,
    },
    "timing": {
        "sample_seconds": 3,
        "sweep_interval_minutes": 5,
        "stale_gap_minutes": 30,
    },
    "notifications": {"enabled": True, "reminder_minutes": 60},
    "allowlist": [],
    "process_rules": {},
}


def default_settings() -> dict:
    """Return an independent copy of the safe built-in settings."""
    return copy.deepcopy(DEFAULT_SETTINGS)


def _bounded_number(value, field, minimum, maximum, *, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("%s must be a number" % field)
    number = float(value)
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise ValueError("%s must be between %s and %s" % (field, minimum, maximum))
    if integer:
        if number != int(number):
            raise ValueError("%s must be a whole number" % field)
        return int(number)
    return number


def _process_image(value, field):
    if not isinstance(value, str):
        raise ValueError("%s image name must be text" % field)
    name = value.strip().lower()
    if (not name or len(name) > 255 or "\\" in name or "/" in name
            or "\x00" in name):
        raise ValueError("%s image name must be a file name" % field)
    return name


def normalize_settings(raw):
    """Validate the complete policy or fail closed to unchanged defaults.

    Legacy ``Allowlist``/``SampleSeconds`` config files remain readable. A
    malformed or future schema never gets partially applied. Per-process
    numeric overrides may only tighten the global thresholds; ``alert_only``
    is the sole mode override, so a rule can never disable a hard kill guard.
    Returns ``(settings, warning)``.
    """
    if raw is None:
        return default_settings(), None
    try:
        if not isinstance(raw, dict):
            raise ValueError("settings root must be an object")

        if "Allowlist" in raw or "SampleSeconds" in raw:
            legacy_allowed = {"Allowlist", "SampleSeconds"}
            if set(raw) - legacy_allowed:
                raise ValueError("legacy settings contain unknown fields")
            raw = {
                "schema_version": 1,
                "allowlist": raw.get("Allowlist", []),
                "timing": {"sample_seconds": raw.get("SampleSeconds", 3)},
            }

        allowed_root = {
            "schema_version", "thresholds", "timing", "notifications",
            "allowlist", "process_rules",
        }
        unknown_root = set(raw) - allowed_root
        if unknown_root:
            raise ValueError("unknown settings field: %s" % sorted(unknown_root)[0])
        version = raw.get("schema_version", 1)
        if isinstance(version, bool) or version != 1:
            raise ValueError("unsupported settings schema_version")

        result = default_settings()
        for group_name, allowed in (
            ("thresholds", {"cpu_percent", "required_hits", "minimum_hot_minutes"}),
            ("timing", {"sample_seconds", "sweep_interval_minutes", "stale_gap_minutes"}),
            ("notifications", {"enabled", "reminder_minutes"}),
        ):
            group = raw.get(group_name, {})
            if not isinstance(group, dict):
                raise ValueError("%s must be an object" % group_name)
            unknown = set(group) - allowed
            if unknown:
                raise ValueError("unknown %s field: %s" % (group_name, sorted(unknown)[0]))

        thresholds = raw.get("thresholds", {})
        result["thresholds"] = {
            "cpu_percent": _bounded_number(
                thresholds.get("cpu_percent", 80), "cpu_percent", 50, 100),
            "required_hits": _bounded_number(
                thresholds.get("required_hits", 6), "required_hits", 2, 60, integer=True),
            "minimum_hot_minutes": _bounded_number(
                thresholds.get("minimum_hot_minutes", 30), "minimum_hot_minutes", 5, 240, integer=True),
        }

        timing = raw.get("timing", {})
        result["timing"] = {
            "sample_seconds": _bounded_number(
                timing.get("sample_seconds", 3), "sample_seconds", 1, 30, integer=True),
            "sweep_interval_minutes": _bounded_number(
                timing.get("sweep_interval_minutes", 5), "sweep_interval_minutes", 1, 1440, integer=True),
            "stale_gap_minutes": _bounded_number(
                timing.get("stale_gap_minutes", 30), "stale_gap_minutes", 5, 1440, integer=True),
        }
        if result["timing"]["stale_gap_minutes"] < result["timing"]["sweep_interval_minutes"]:
            raise ValueError("stale_gap_minutes must be at least sweep_interval_minutes")

        notifications = raw.get("notifications", {})
        enabled = notifications.get("enabled", True)
        if type(enabled) is not bool:
            raise ValueError("notifications.enabled must be true or false")
        result["notifications"] = {
            "enabled": enabled,
            "reminder_minutes": _bounded_number(
                notifications.get("reminder_minutes", 60), "reminder_minutes", 5, 1440, integer=True),
        }

        allowlist = raw.get("allowlist", [])
        if not isinstance(allowlist, list) or len(allowlist) > 250:
            raise ValueError("allowlist must be a list of at most 250 image names")
        result["allowlist"] = sorted({_process_image(v, "allowlist") for v in allowlist})

        rules = raw.get("process_rules", {})
        if not isinstance(rules, dict) or len(rules) > 250:
            raise ValueError("process_rules must be an object of at most 250 image rules")
        normalized_rules = {}
        global_thresholds = result["thresholds"]
        allowed_rule = {"mode", "cpu_percent", "required_hits", "minimum_hot_minutes"}
        for image, rule in rules.items():
            key = _process_image(image, "process_rules")
            if not isinstance(rule, dict):
                raise ValueError("process rule for %s must be an object" % key)
            unknown = set(rule) - allowed_rule
            if unknown:
                raise ValueError("unknown process rule field: %s" % sorted(unknown)[0])
            mode = rule.get("mode", "default")
            if mode not in ("default", "alert_only"):
                raise ValueError("process rule mode must be default or alert_only")
            clean = {"mode": mode}
            bounds = (
                ("cpu_percent", 50, 100, False),
                ("required_hits", 2, 60, True),
                ("minimum_hot_minutes", 5, 240, True),
            )
            for name, minimum, maximum, integer in bounds:
                if name not in rule:
                    continue
                value = _bounded_number(rule[name], name, minimum, maximum, integer=integer)
                if value < global_thresholds[name]:
                    raise ValueError("process rule %s may not weaken %s" % (key, name))
                clean[name] = value
            normalized_rules[key] = clean
        result["process_rules"] = normalized_rules
        return result, None
    except (TypeError, ValueError) as exc:
        return default_settings(), str(exc)


def read_settings_file(path=None):
    """Read the JSON config for the CLI; missing files use old safe defaults."""
    if not path:
        return default_settings(), None
    if not os.path.isfile(path):
        return default_settings(), "settings file not found: %s" % path
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            raw = json.load(handle)
    except (OSError, ValueError) as exc:
        return default_settings(), "settings unreadable: %s" % exc
    return normalize_settings(raw)


def cpu_percent_core(
    cpu_before: float, cpu_after: float, sample_seconds: float = SAMPLE_SECONDS
) -> float:
    """Accumulated-CPU delta as a share of one logical core.

    A negative delta means the counter was re-read for a different process
    (PID reuse mid-sweep) or came back inconsistent. That is missing
    information, so it reads as 0.0 rather than as a large number.
    """
    if sample_seconds <= 0:
        return 0.0
    return max(0.0, (float(cpu_after) - float(cpu_before)) / float(sample_seconds) * 100.0)


def is_never_kill(
    name: str, *, is_main_process: bool = False, allowlist: object = (), pid: object = None
) -> bool:
    """Whether automatic termination is forbidden for this image.

    The allowlist blocks the KILL only. A suspicious allowlisted process is
    still worth an ALERT and a log line -- that is diagnostically useful, and
    silence would hide the one case where a system process really is spinning.
    """
    try:
        if pid is not None and int(pid) <= PID_FLOOR:
            return True
    except (TypeError, ValueError):
        return True  # an unreadable PID is missing information
    key = (name or "").strip().lower()
    if not key:
        # No name is missing information: bias toward not killing.
        return True
    extra = {str(item).strip().lower() for item in (allowlist or ())}
    if key in NEVER_KILL or key in extra:
        return True
    return is_main_process and key in MAIN_PROCESS_GUARDED


@dataclasses.dataclass(frozen=True)
class Sample:
    """One observation of one process, already collected by the watcher."""

    pid: int
    start_time: str  # ISO-8601; the other half of the process identity
    name: str
    cpu_percent: float
    orphan: bool
    observed_at: str  # ISO-8601 UTC
    cmdline: str = ""
    is_main_process: bool = False

    @property
    def key(self) -> str:
        """The process identity. Never the PID on its own."""
        return f"{self.pid}:{self.start_time}"

    @classmethod
    def from_dict(cls, raw: dict) -> "Sample":
        return cls(
            pid=int(raw["pid"]),
            start_time=str(raw["start_time"]),
            name=str(raw.get("name", "")),
            cpu_percent=float(raw.get("cpu_percent", 0.0)),
            orphan=bool(raw.get("orphan", False)),
            observed_at=str(raw["observed_at"]),
            cmdline=str(raw.get("cmdline", "")),
            is_main_process=bool(raw.get("is_main_process", False)),
        )


def classify_process(
    sample: Sample,
    *,
    allowlist: object = (),
    settings: object = None,
    decision: "Decision | None" = None,
) -> str:
    """Classify a process according to the Phase 7 safety model."""
    try:
        if sample.pid in KERNEL_PIDS or sample.pid <= PID_FLOOR:
            return CLASSIFICATION_PROTECTED_SYSTEM
    except (TypeError, ValueError):
        return CLASSIFICATION_UNKNOWN

    name = (sample.name or "").strip().lower()
    if not name:
        return CLASSIFICATION_UNKNOWN

    if name in NEVER_KILL:
        return CLASSIFICATION_PROTECTED_SYSTEM

    policy, _ = normalize_settings(settings)
    configured_allowlist = policy.get("allowlist", [])
    combined_allowlist = {str(x).strip().lower() for x in list(allowlist or ()) + list(configured_allowlist)}

    if name in combined_allowlist:
        return CLASSIFICATION_PROTECTED_USER

    if sample.is_main_process and name in MAIN_PROCESS_GUARDED:
        return CLASSIFICATION_PROTECTED_USER

    cmd = (sample.cmdline or "").lower()
    if any(pat in cmd for pat in ("-m pytest", "-m unittest", "pytest", "jest", "vitest", "playwright")):
        return CLASSIFICATION_PROTECTED_ACTIVE
    if "node" in cmd and "--test" in cmd:
        return CLASSIFICATION_PROTECTED_ACTIVE
    if name in ("pytest.exe", "vstest.console.exe", "testhost.exe", "antigravity.exe", "agy.exe", "claude.exe", "opencode.exe"):
        return CLASSIFICATION_PROTECTED_ACTIVE

    rule = policy.get("process_rules", {}).get(name, {})
    if rule.get("mode") == "alert_only":
        return CLASSIFICATION_OBSERVE_ONLY

    if decision is not None:
        if decision.action == KILL:
            # KILL only ever reaches here with a valid recovery lease (see
            # decide), so the strongest verdict means ownership was proven,
            # not merely that a name was absent from a denylist.
            return CLASSIFICATION_RECOVERY_ELIGIBLE
        if decision.hot and decision.orphan:
            return CLASSIFICATION_SUSPECTED_STALL

    if sample.cpu_percent > policy["thresholds"]["cpu_percent"] and sample.orphan:
        return CLASSIFICATION_SUSPECTED_STALL

    return CLASSIFICATION_OBSERVE_ONLY


@dataclasses.dataclass(frozen=True)
class Decision:
    """What to do about one sample, plus the facts that decided it."""

    action: str
    key: str
    hot: bool
    sustained: bool
    orphan: bool
    allowlisted: bool
    hits: int
    hot_seconds: int
    reason: str
    # Carried through from the sample so one log line can satisfy the whole
    # reporting contract without the caller re-joining decisions to samples.
    pid: int = 0
    start_time: str = ""
    name: str = ""
    cpu_percent: float = 0.0
    cmdline: str = ""
    # The state entry to persist for this identity. None means "drop it": the
    # process went cold, so its streak is over.
    record: "dict | None" = None
    threshold_cpu: float = 80.0
    classification: str = ""

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def parse_time(value: str) -> "datetime | None":
    """ISO-8601 to an aware datetime, or None when it cannot be trusted."""
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def _elapsed_seconds(first: str, last: str) -> int:
    """Seconds between two stamps; 0 when either one is unusable.

    Unparseable time is missing information, and 0 elapsed can never satisfy
    the sustained gate. Guessing a duration here would manufacture the exact
    evidence the kill decision requires.
    """
    start, end = parse_time(first), parse_time(last)
    if start is None or end is None:
        return 0
    return max(0, int((end - start).total_seconds()))


def _prior(history: object, sample: Sample) -> dict:
    """The stored streak for this exact identity, or an empty one.

    The key already carries PID + StartTime, but a hand-edited or partially
    recovered state file can hold an entry whose fields disagree with its key.
    Those fields are re-checked rather than trusted, so a mismatch starts a new
    streak instead of donating strikes to a different process.
    """
    if not isinstance(history, dict):
        return {}
    entry = history.get(sample.key)
    if not isinstance(entry, dict):
        return {}
    try:
        same_pid = int(entry.get("pid", -1)) == sample.pid
    except (TypeError, ValueError):
        return {}
    if not same_pid or str(entry.get("start_time", "")) != sample.start_time:
        return {}
    return entry


# Where recovery leases live. SAISPIN_LEASE_DIR overrides the per-user runtime
# directory so tests and the controlled-kill acceptance run isolated.
LEASE_ENV_DIR = "SAISPIN_LEASE_DIR"


def lease_directory() -> str:
    override = os.environ.get(LEASE_ENV_DIR)
    if override:
        return override
    data_root = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or "."
    return os.path.join(data_root, "SAITULS", "SAISPIN", "leases")


def lease_path_for(sample: "Sample") -> str:
    safe_start = sample.start_time.replace(":", "_").replace("/", "_")
    return os.path.join(lease_directory(), "%d_%s.json" % (sample.pid, safe_start))


def evaluate_recovery_lease(sample: "Sample") -> "tuple[bool, str]":
    """Positive proof that THIS process may be recovered.

    A command line is not an ownership token. The only thing that authorizes
    destructive recovery is a lease bound to the exact identity -- PID and
    creation time -- carrying an explicit authorization flag and an expiry
    that has not passed the sweep's observation time. A failed or expired
    lease therefore cannot authorize an unrelated PID, and a reused PID can
    never inherit a dead process's lease.

    Returns ``(eligible, reason)``. The reason is the refusal text on failure.
    """
    path = lease_path_for(sample)
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            lease = json.load(handle)
    except FileNotFoundError:
        return False, (
            "no recovery lease for this identity -- ownership unknown, "
            "observe and alert only"
        )
    except (OSError, ValueError):
        return False, "recovery lease unreadable -- ownership cannot be proven"

    if not isinstance(lease, dict):
        return False, "recovery lease malformed -- ownership cannot be proven"
    try:
        lease_pid = int(lease.get("pid", -1))
    except (TypeError, ValueError):
        return False, "recovery lease pid unreadable -- ownership cannot be proven"
    if lease_pid != sample.pid or str(lease.get("start_time", "")) != sample.start_time:
        return False, "recovery lease identity mismatch -- lease belongs to another process"
    if lease.get("authorized") is not True:
        return False, "recovery lease not authorized -- destructive recovery denied"
    expiry = parse_time(str(lease.get("expires_at", "")))
    observed = parse_time(sample.observed_at)
    if expiry is None or observed is None:
        return False, "recovery lease expiry unreadable -- ownership cannot be proven"
    if observed >= expiry:
        return False, "recovery lease expired -- authorization no longer valid"
    return True, ""


def decide(
    history: object,
    sample: Sample,
    auto_kill: bool = False,
    *,
    allowlist: object = (),
    history_trusted: bool = True,
    settings: object = None,
) -> Decision:
    """The whole safety decision for one process, as data in and data out.

    ``history`` is the full identity-keyed state mapping the watcher persists;
    ``history_trusted`` is False when that state was rebuilt after a corrupt
    read, which downgrades any KILL to an ALERT.
    """
    policy, _warning = normalize_settings(settings)
    configured_allowlist = policy["allowlist"]
    combined_allowlist = list(allowlist or ()) + configured_allowlist
    allowlisted = is_never_kill(
        sample.name,
        is_main_process=sample.is_main_process,
        allowlist=combined_allowlist,
        pid=sample.pid,
    )
    active_protected = False
    cmd_lower = (sample.cmdline or "").lower()
    if any(pat in cmd_lower for pat in ("-m pytest", "-m unittest", "pytest", "jest", "vitest", "playwright")):
        active_protected = True
    # node's built-in test runner is `node [flags] file --test` with the flag
    # anywhere after the script, so a fixed "node --test" substring misses it.
    if "node" in cmd_lower and "--test" in cmd_lower:
        active_protected = True
    if sample.name.lower() in ("pytest.exe", "vstest.console.exe", "testhost.exe", "antigravity.exe", "agy.exe", "claude.exe", "opencode.exe"):
        active_protected = True
    if active_protected:
        allowlisted = True

    rule = policy["process_rules"].get(sample.name.strip().lower(), {})
    thresholds = dict(policy["thresholds"])
    for name in ("cpu_percent", "required_hits", "minimum_hot_minutes"):
        if name in rule:
            thresholds[name] = rule[name]
    hot = sample.cpu_percent > thresholds["cpu_percent"]
    eff_threshold = float(thresholds["cpu_percent"])

    if sample.pid in KERNEL_PIDS:
        # Not even tracked. Idle is "hot" by definition on an idle machine and
        # has no parent to lose, so tracking it would mean an alert every five
        # minutes for the rest of time about the one process that is doing
        # nothing. It cannot be killed either, so there is nothing to report.
        return Decision(
            action=IGNORE,
            key=sample.key,
            hot=hot,
            sustained=False,
            orphan=sample.orphan,
            allowlisted=True,
            hits=0,
            hot_seconds=0,
            reason="kernel process (PID %d) -- never tracked, never killed" % sample.pid,
            pid=sample.pid,
            start_time=sample.start_time,
            name=sample.name,
            cpu_percent=sample.cpu_percent,
            cmdline=sample.cmdline[:CMDLINE_LIMIT],
            record=None,
            threshold_cpu=eff_threshold,
            classification=CLASSIFICATION_PROTECTED_SYSTEM,
        )

    if not hot:
        # A cold sample ends the streak. This is what keeps HOT HOT HOT COLD
        # HOT HOT HOT from adding up to six.
        return Decision(
            action=IGNORE,
            key=sample.key,
            hot=False,
            sustained=False,
            orphan=sample.orphan,
            allowlisted=allowlisted,
            hits=0,
            hot_seconds=0,
            reason="cold sample -- the hot streak restarts from zero",
            pid=sample.pid,
            start_time=sample.start_time,
            name=sample.name,
            cpu_percent=sample.cpu_percent,
            cmdline=sample.cmdline[:CMDLINE_LIMIT],
            record=None,
            threshold_cpu=eff_threshold,
            classification=classify_process(sample, allowlist=combined_allowlist, settings=policy),
        )

    prior = _prior(history, sample)

    # A gap longer than a few missed sweeps means nobody was observing. The
    # streak stored on the other side of it proves nothing about the interval,
    # so it is dropped rather than extended: a laptop that slept for two days
    # must not wake up holding five strikes against a process.
    if prior and _elapsed_seconds(
        str(prior.get("last_hot") or ""), sample.observed_at
    ) > policy["timing"]["stale_gap_minutes"] * 60:
        prior = {}

    first_hot = str(prior.get("first_hot") or sample.observed_at)
    try:
        hits = int(prior.get("hits", 0)) + 1
    except (TypeError, ValueError):
        hits = 1
    hot_seconds = _elapsed_seconds(first_hot, sample.observed_at)
    required_seconds = thresholds["minimum_hot_minutes"] * 60
    sustained = hits >= thresholds["required_hits"] and hot_seconds >= required_seconds

    record = {
        "pid": sample.pid,
        "start_time": sample.start_time,
        "first_hot": first_hot,
        "last_hot": sample.observed_at,
        "hits": hits,
        "name": sample.name,
        "cmdline": sample.cmdline[:CMDLINE_LIMIT],
    }

    def verdict(action: str, reason: str) -> Decision:
        temp_dec = Decision(
            action=action,
            key=sample.key,
            hot=True,
            sustained=sustained,
            orphan=sample.orphan,
            allowlisted=allowlisted,
            hits=hits,
            hot_seconds=hot_seconds,
            reason=reason,
            pid=sample.pid,
            start_time=sample.start_time,
            name=sample.name,
            cpu_percent=sample.cpu_percent,
            cmdline=sample.cmdline[:CMDLINE_LIMIT],
            record=record,
            threshold_cpu=eff_threshold,
            classification="",
        )
        cls_val = classify_process(
            sample,
            allowlist=combined_allowlist,
            settings=policy,
            decision=temp_dec,
        )
        return Decision(
            action=action,
            key=sample.key,
            hot=True,
            sustained=sustained,
            orphan=sample.orphan,
            allowlisted=allowlisted,
            hits=hits,
            hot_seconds=hot_seconds,
            reason=reason,
            pid=sample.pid,
            start_time=sample.start_time,
            name=sample.name,
            cpu_percent=sample.cpu_percent,
            cmdline=sample.cmdline[:CMDLINE_LIMIT],
            record=record,
            threshold_cpu=eff_threshold,
            classification=cls_val,
        )

    if not sustained:
        return verdict(
            IGNORE,
            "hot but not sustained: %d/%d consecutive hot samples over %dm/%dm"
            % (hits, thresholds["required_hits"], hot_seconds // 60,
               thresholds["minimum_hot_minutes"]),
        )
    if not sample.orphan:
        return verdict(
            ALERT,
            "sustained spin with a live parent -- reported, never auto-killed",
        )
    if rule.get("mode") == "alert_only":
        return verdict(ALERT, "process rule is alert-only -- never auto-killed")
    if not auto_kill:
        return verdict(
            ALERT, "orphan sustained spin -- auto-kill is off, nothing terminated"
        )
    if allowlisted:
        reason_msg = "orphan sustained spin on a never-kill process -- reported only"
        if active_protected:
            reason_msg = "active protected work (test runner, compiler, or agent) -- reported only"
        return verdict(ALERT, reason_msg)
    if not history_trusted:
        return verdict(
            ALERT,
            "orphan sustained spin, but the history was rebuilt after a bad "
            "state read -- no kill from evidence that cannot be trusted",
        )
    # P0-1: CPU heat + orphanhood never proves recoverability. A kill needs a
    # positive ownership token: a recovery lease bound to this exact identity
    # (PID + creation time), explicitly authorized and still unexpired. Without
    # one the verdict stops at SUSPECTED_STALL -- detected, alerted, evidenced,
    # never force-terminated on heuristic uncertainty.
    lease_ok, lease_why = evaluate_recovery_lease(sample)
    if not lease_ok:
        return verdict(ALERT, lease_why)
    return verdict(
        KILL,
        "orphan sustained spin, auto-kill enabled, identity matched, not allowlisted, "
        "recovery lease valid -- ownership positively proven",
    )


def sweep(
    history: object,
    samples: object,
    auto_kill: bool = False,
    *,
    allowlist: object = (),
    history_trusted: bool = True,
    settings: object = None,
) -> "tuple[list[Decision], dict]":
    """Decide a whole enumeration and return the state to persist.

    The next state is rebuilt from the decisions rather than edited in place,
    so a process that disappeared between sweeps drops out by simply not being
    in ``samples`` -- no separate prune pass to forget to run.
    """
    policy, _warning = normalize_settings(settings)
    decisions = [
        decide(
            history,
            item if isinstance(item, Sample) else Sample.from_dict(item),
            auto_kill,
            allowlist=allowlist,
            history_trusted=history_trusted,
            settings=policy,
        )
        for item in (samples or ())
    ]
    next_history = {d.key: d.record for d in decisions if d.record is not None}
    return decisions, next_history


def _read_stdin() -> str:
    """The watcher's payload, as UTF-8, whatever the console says.

    Windows PowerShell 5.1 can prepend a UTF-8 BOM when it pipes a string to a
    native command (seen from a nested powershell.exe, even with
    $OutputEncoding set to UTF-8 without BOM), and sys.stdin decodes with the
    console code page, not UTF-8. Reading the bytes and decoding utf-8-sig
    takes both out of the equation.
    """
    buf = getattr(sys.stdin, "buffer", None)
    if buf is None:
        return sys.stdin.read()
    return buf.read().decode("utf-8-sig")


def main(argv: "list[str] | None" = None) -> int:
    """JSON sweep on stdin, decisions plus next state on stdout.

    The adapter is deliberately thin: it moves data, and every rule that can
    end a process lives in the pure functions above where the tests can reach
    it without a real process tree.
    """
    args = list(argv if argv is not None else sys.argv[1:])
    if args and args[0] == "--normalize-settings":
        if len(args) > 2:
            sys.stderr.write("usage: saispin_logic.py --normalize-settings [settings.json|--defaults]\n")
            return 2
        if len(args) == 2 and args[1] == "--defaults":
            settings, warning = default_settings(), None
        elif len(args) == 2:
            settings, warning = read_settings_file(args[1])
        else:
            try:
                settings, warning = normalize_settings(json.loads(_read_stdin() or "null"))
            except ValueError as exc:
                settings, warning = default_settings(), "settings JSON unreadable: %s" % exc
        json.dump({"settings": settings, "warning": warning}, sys.stdout)
        sys.stdout.write("\n")
        return 0
    for flag in args:
        if flag not in ("--sweep",):
            sys.stderr.write("usage: saispin_logic.py [--sweep] < payload.json\n")
            return 2
    try:
        payload = json.loads(_read_stdin() or "{}")
    except ValueError as exc:
        sys.stderr.write("bad payload: %s\n" % exc)
        return 2

    decisions, next_history = sweep(
        payload.get("history") or {},
        payload.get("samples") or [],
        bool(payload.get("auto_kill", False)),
        allowlist=payload.get("allowlist") or (),
        history_trusted=bool(payload.get("history_trusted", True)),
        settings=payload.get("settings"),
    )
    json.dump(
        {
            "decisions": [d.as_dict() for d in decisions],
            "history": next_history,
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
