"""T-2011 / SRC-382 P0-01, P0-02: staged host acceptance and a read-only probe.

The controls below are the independent source-level red controls for the two
verified production defects:

* P0-01 -- the probe treated a HOST_ACCEPTED dispatch as LIVE_ACCEPTANCE. Host
  acceptance is the host saying "I took the request"; it is not TURN_STARTED,
  not TURN_COMPLETED, and not a successor turn. A staged report must keep those
  apart, and LIVE_ACCEPTANCE must require broker-authenticated turn lifecycle
  evidence actually present in the project's own dispatch ledger.
* P0-02 -- the probe was documented as read-only yet dispatched a synthetic
  next_turn request into whatever project_root it was given. Capability
  inspection must leave the supplied tree byte-identical, and the mutating
  dispatch test must run in a disposable fixture.

Every receipt these controls inject is a *simulation*; broker authentication is
mocked only where the control asserts the stage boundary itself. One control
still runs the real broker (`verify_record` unmocked) and requires a synthetic
receipt to be refused. None of this proves an installed host accepted a turn.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import installed_host_acceptance as probe  # noqa: E402
from saipen_engine import campaign, continuation_assessment as ca, host_authority_client, host_dispatch  # noqa: E402

#: Self-contained campaign fixture: this module must not import a test that
#: reads repo memory, or the regression sandbox (which copies only declared
#: context) cannot import it.
_FIXTURE_STATE = (
    "---\n"
    "phase: BUILD\n"
    "task: T-100\n"
    'next_action: "PHASE BUILD T-100"\n'
    "blocker: none\n"
    "transition_from: SCOUT\n"
    "saipen_version: 8\n"
    "schema_version: 3\n"
    "agent: fixture\n"
    "mode: full\n"
    "updated: 2026-01-01T00:00:00Z\n"
    "execution_intent: goal\n"
    "goal_tickets: 5\n"
    "goal_waves: 0\n"
    "---\n"
)


def _fixture_project() -> Path:
    from campaign_test_support import write_scoped_fixture_grant

    root = Path(tempfile.mkdtemp(prefix="t2011-camp-"))
    (root / ".saipen").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "STATE.md").write_text(_FIXTURE_STATE, encoding="utf-8")
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n- [/] T-100 [P1] fixture\n## TODO\n## BLOCKED\n## DONE\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "LOG.md").write_text("# LOG\n", encoding="utf-8")
    (root / ".saipen" / "IDENTITY.md").write_text(
        "---\nproject_lineage: lineage-0123456789abcdef0123456789abcdef\n---\n",
        encoding="utf-8",
    )
    write_scoped_fixture_grant(root)
    return root


def _receipt(payload: dict, status: str) -> dict:
    return {
        "schema_version": host_dispatch.ACCEPTANCE_SCHEMA_VERSION,
        "status": status,
        "campaign_id": payload["campaign_id"],
        "iteration_id": payload["iteration_id"],
        "worker_generation": payload["worker_generation"],
        "idempotency_key": payload["idempotency_key"],
        "accepting_host": "simulated-host",
        "project_lineage": payload["project_lineage"],
        "accepted_request_digest": payload["idempotency_key"],
        "goal_binding": payload.get("goal_binding")
        or {"path": "STATE.md",
            "fingerprint": f"goal-{payload['project_lineage'][:8]}"},
    }


def _transport_script(status: str = host_dispatch.HOST_ACCEPTED) -> str:
    """A host command that returns one receipt built from the request it got."""
    code = (
        "import json,sys;"
        "p=json.loads(sys.argv[1]);"
        f"print(json.dumps({{'schema_version':1,'status':%r,"
        "'campaign_id':p['campaign_id'],'iteration_id':p['iteration_id'],"
        "'worker_generation':p['worker_generation'],"
        "'idempotency_key':p['idempotency_key'],"
        "'accepting_host':'simulated-host',"
        "'project_lineage':p['project_lineage'],"
        "'accepted_request_digest':p['idempotency_key']}))" % status
    )
    # Native Windows path on purpose: argv splitting must not mangle it.
    return f"{sys.executable} -c {json.dumps(code)}"


def _tree(root: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root)).replace("\\", "/")
        snapshot[rel] = path.read_bytes() if path.is_file() else b"<dir>"
    return snapshot


class RecordedStagingSurvivalTests(unittest.TestCase):
    """T-2011 / SHIP gate: a release hold protects recorded CONTENT, not pointers.

    Measured 2026-11-03: four live-index oracles went red against a 1238-entry
    index while all 864 recorded blobs were still present -- ten entries had
    legitimately moved (SRC-349/350 retired to the archive, two T-1975 evidence
    files unstaged but on disk) and fifteen of this project's own modules had
    been revised by later work. The repair asks the durable question; these
    controls keep it honest in BOTH directions.
    """

    def _repo(self, root: Path) -> None:
        for args in (
            ["init", "-b", "main"],
            ["config", "user.name", "T"],
            ["config", "user.email", "t@example.com"],
        ):
            subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
        (root / "kept.txt").write_text("kept\n", encoding="utf-8")
        (root / "moved.txt").write_text("moved\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-m", "init"], check=True, capture_output=True
        )

    def _blob(self, root: Path, path: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", f"HEAD:{path}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

    def test_moved_entry_with_live_content_is_not_a_loss(self) -> None:
        """Retiring a recorded entry keeps its bytes -> survival, not failure."""
        from saipen_engine import isolated_release

        with tempfile.TemporaryDirectory(prefix="t2011-surv-") as tmp:
            root = Path(tmp)
            self._repo(root)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {"entries": [
                        {"path": "kept.txt", "status": "M", "blob_sha": self._blob(root, "kept.txt")},
                        {"path": "moved.txt", "status": "A", "blob_sha": self._blob(root, "moved.txt")},
                    ]}
                ),
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(root), "mv", "moved.txt", "archived.txt"],
                           check=True, capture_output=True)
            (root / "kept.txt").write_text("kept v2\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "kept.txt"],
                           check=True, capture_output=True)

            res = isolated_release.recorded_staging_survival(root, manifest)
            self.assertTrue(res["recorded_content_survives"], res)
            self.assertEqual(res["content_lost_paths"], [])
            self.assertIn("moved.txt", res["relocated_paths"])
            self.assertIn("kept.txt", [m["path"] for m in res["revised_in_place"]])

    def test_a_truly_missing_blob_is_reported_as_loss(self) -> None:
        """RED CONTROL: a recorded blob that no longer exists must fail the check."""
        from saipen_engine import isolated_release

        with tempfile.TemporaryDirectory(prefix="t2011-loss-") as tmp:
            root = Path(tmp)
            self._repo(root)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {"entries": [
                        {"path": "gone.txt", "status": "A", "blob_sha": "deadbeefdeadbeef"},
                    ]}
                ),
                encoding="utf-8",
            )
            res = isolated_release.recorded_staging_survival(root, manifest)
            self.assertFalse(res["recorded_content_survives"])
            self.assertEqual(res["content_lost_paths"], ["gone.txt"])

    def test_the_live_manifest_survives_and_its_recorded_count_is_stable(self) -> None:
        """The live capture can only shrink by real loss, never by movement."""
        from saipen_engine import isolated_release

        repo_root = Path(__file__).resolve().parents[1]
        rel = ".saipen/evidence/index-forensics/staged_manifest_20261102.json"
        if not (repo_root / rel).is_file():
            # A regression sandbox copies only the declared context; this
            # assertion is about the LIVE tree, so it has nothing to measure
            # where the capture is not present.
            self.skipTest("live capture not present in this sandbox")
        res = isolated_release.recorded_staging_survival(repo_root, rel)
        self.assertEqual(res["recorded_count"], 864)
        self.assertTrue(res["recorded_content_survives"], res["content_lost_paths"][:5])


class ReadOnlyProbeTests(unittest.TestCase):
    """P0-02: inspecting capability must not create project state."""

    def test_probe_leaves_the_supplied_project_untouched(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t2011-ro-") as tmp:
            root = Path(tmp)
            before = _tree(root)
            probe.probe(project_root=root)
            self.assertEqual(_tree(root), before, "the diagnostic probe wrote to the project")

    def test_probe_does_not_write_a_next_turn_request(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t2011-nt-") as tmp:
            root = Path(tmp)
            campaign = root / ".saipen" / "campaign"
            campaign.mkdir(parents=True)
            (campaign / "next_turn.json").write_text('{"existing": true}\n', encoding="utf-8")
            before = _tree(root)
            probe.probe(project_root=root)
            self.assertEqual(_tree(root), before)
            self.assertEqual(
                json.loads((campaign / "next_turn.json").read_text(encoding="utf-8")),
                {"existing": True},
                "a diagnostic probe overwrote the live campaign's next turn",
            )

    def test_the_dispatch_test_never_targets_a_supplied_live_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t2011-live-") as tmp:
            root = Path(tmp)
            before = _tree(root)
            result = probe.authorized_dispatch_test(live_root=root)
            self.assertEqual(_tree(root), before, "the dispatch test wrote to the live root")
            self.assertNotEqual(
                Path(result["fixture_root"]).resolve(), root.resolve(),
                "the dispatch test used the live project as its fixture",
            )


class StagedAcceptanceTests(unittest.TestCase):
    """P0-01: host acceptance is not execution and not continuation."""

    def test_host_accepted_alone_is_not_live_acceptance(self) -> None:
        """A real HOST_ACCEPTED transport receipt stages, never upgrades.

        The acceptance event is produced by the actual dispatch path (fixture
        root, registered command transport, broker authentication simulated) --
        the same boundary a live host would cross -- then probed read-only.
        """
        with tempfile.TemporaryDirectory(prefix="t2011-stage-") as tmp:
            root = Path(tmp)
            with mock.patch.object(host_authority_client, "verify_record", lambda *a, **k: True), \
                 mock.patch.dict(os.environ, {"HOST_SCHEDULER_DISPATCH_CMD": _transport_script()}):
                dispatched = probe.authorized_dispatch_test()
                self.assertIs(dispatched["dispatched"], True, dispatched)
                result = probe.probe(project_root=Path(dispatched["fixture_root"]))
            self.assertNotEqual(result["verdict"], probe.LIVE_ACCEPTANCE)
            self.assertFalse(result["ok"])
            self.assertIs(result["stages"]["host_accepted"], True)
            self.assertIs(result["stages"]["turn_started"], False)
            self.assertIs(result["stages"]["turn_completed"], False)
            self.assertEqual(result["stages"]["multi_turn_continuation"], 0)

    def test_unsigned_transport_receipt_is_never_acceptance(self) -> None:
        """Real broker, no mock: a receipt the broker did not write is refused."""
        with tempfile.TemporaryDirectory(prefix="t2011-forge-") as tmp:
            root = Path(tmp)
            with mock.patch.dict(os.environ, {"HOST_SCHEDULER_DISPATCH_CMD": _transport_script()}):
                result = probe.probe(project_root=root)
            self.assertFalse(result["stages"]["host_accepted"])
            self.assertNotEqual(result["verdict"], probe.LIVE_ACCEPTANCE)
            self.assertNotEqual(result["verdict"], probe.SCHEDULER_AVAILABLE)

    def test_live_acceptance_requires_authenticated_turn_lifecycle(self) -> None:
        """Positive control: the gate must be satisfiable, not just refusing.

        SRC-387 finding D: a ledger pair is HISTORICAL evidence, not current
        readiness. With no bound session, no granted authority and no
        supported scheduler this machine is not ready now, so the verdict is
        HISTORICAL_ACCEPTANCE_NOT_READY while ``verified_history`` stays true.
        LIVE_ACCEPTANCE requires BOTH the authenticated pair AND current
        readiness, supplied here explicitly so the reachable-verdict half of
        the control still runs.
        """
        with tempfile.TemporaryDirectory(prefix="t2011-live-ev-") as tmp:
            root = Path(tmp)
            campaign = root / ".saipen" / "campaign"
            campaign.mkdir(parents=True)
            payload = host_dispatch.build_dispatch_payload(root, campaign_id="c-lifecycle")
            transitions = [
                ("started", _receipt(payload, host_dispatch.TURN_STARTED)),
                ("completed", _receipt(payload, host_dispatch.TURN_COMPLETED)),
            ]
            with open(campaign / host_dispatch.DISPATCH_LEDGER_JOURNAL, "a", encoding="utf-8") as fh:
                for key, receipt in transitions:
                    record = {"status": receipt["status"], "receipt": receipt}
                    fh.write(json.dumps({"key": key, "record": record}, sort_keys=True) + "\n")
            with mock.patch.object(host_authority_client, "verify_record", lambda *a, **k: True):
                result = probe.probe(project_root=root)
            self.assertIs(result["verified_history"], True)
            self.assertIs(result["stages"]["turn_started"], True)
            self.assertIs(result["stages"]["turn_completed"], True)
            # History without current readiness is exactly this honest state,
            # never LIVE_ACCEPTANCE.
            self.assertEqual(result["verdict"], probe.HISTORICAL_ACCEPTANCE_NOT_READY)

    def test_live_acceptance_is_reachable_when_current_readiness_holds(self) -> None:
        """Regression 8/11: the top verdict must still be satisfiable.

        A historical pair alone cannot reach LIVE_ACCEPTANCE, but the same pair
        plus current readiness (bound session, granted authority, registered
        transport, live broker, supported scheduler) must -- otherwise the
        repair would have made the verdict unreachable instead of honest.
        """
        with tempfile.TemporaryDirectory(prefix="t2011-ready-") as tmp:
            root = Path(tmp)
            campaign = root / ".saipen" / "campaign"
            campaign.mkdir(parents=True)
            payload = host_dispatch.build_dispatch_payload(root, campaign_id="c-ready")
            transitions = [
                ("started", _receipt(payload, host_dispatch.TURN_STARTED)),
                ("completed", _receipt(payload, host_dispatch.TURN_COMPLETED)),
            ]
            with open(campaign / host_dispatch.DISPATCH_LEDGER_JOURNAL, "a", encoding="utf-8") as fh:
                for key, receipt in transitions:
                    fh.write(
                        json.dumps(
                            {"key": key, "record": {"status": receipt["status"], "receipt": receipt}},
                            sort_keys=True,
                        )
                        + "\n"
                    )
            ready_facts = {
                "installed_adapters": ["zaicode"],
                "scheduler_supported": True,
            }
            with mock.patch.object(host_authority_client, "verify_record", lambda *a, **k: True), \
                 mock.patch.object(probe, "_broker_alive", lambda: True), \
                 mock.patch.object(probe, "_host_installation", lambda: ready_facts), \
                 mock.patch.object(
                     probe, "_session_and_authority", lambda _root: (True, "GRANTED")
                 ), \
                 mock.patch.dict(os.environ, {"HOST_SCHEDULER_DISPATCH_CMD": "host-cmd"}):
                result = probe.probe(project_root=root)
            self.assertIs(result["verified_history"], True)
            self.assertIs(result["ready_now"], True)
            self.assertEqual(result["verdict"], probe.LIVE_ACCEPTANCE)
            self.assertIs(result["ok"], True)

    def test_uncertain_dispatch_is_not_acceptance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t2011-timeout-") as tmp:
            root = Path(tmp)
            payload = host_dispatch.build_dispatch_payload(root, campaign_id="c-timeout")
            payload["host_deadline_s"] = 0.01

            def _stall(_payload: dict) -> dict:
                import time

                time.sleep(0.4)
                return _receipt(payload, host_dispatch.TURN_STARTED)

            result = host_dispatch.dispatch_next_turn(root, payload, host_hook=_stall, print_advisory=False)
            self.assertEqual(result["status"], host_dispatch.DISPATCH_TIMEOUT)
            self.assertIs(result["dispatched"], False)
            self.assertIs(result["outcome"], host_dispatch.UNKNOWN_OUTCOME)


_NO_GOAL = object()  # explicit omission, for the fail-closed controls


def _lifecycle_receipt(campaign_id: str, *, status: str, gen: int, it: int,
                       lineage: str = "lineage-1", host: str = "h-1",
                       goal=_NO_GOAL) -> dict:
    receipt = {
        "schema_version": host_dispatch.ACCEPTANCE_SCHEMA_VERSION,
        "status": status,
        "campaign_id": campaign_id,
        "iteration_id": it,
        "worker_generation": gen,
        "idempotency_key": f"{campaign_id}-{gen}-{it}",
        "accepting_host": host,
        "project_lineage": lineage,
        "accepted_request_digest": f"{campaign_id}-{gen}-{it}",
    }
    if goal is not _NO_GOAL:
        # A real dispatch receipt always carries a goal binding; the controls
        # below omit it explicitly to prove the verifier fails closed.
        receipt["goal_binding"] = goal
    else:
        receipt["goal_binding"] = {
            "path": "STATE.md",
            "fingerprint": f"goal-{lineage[:8]}",
        }
    return receipt


def _write_ledger(campaign_dir: Path, records: list[tuple[str, dict]]) -> None:
    campaign_dir.mkdir(parents=True, exist_ok=True)
    with open(campaign_dir / host_dispatch.DISPATCH_LEDGER_JOURNAL, "a", encoding="utf-8") as fh:
        for key, record in records:
            fh.write(json.dumps({"key": key, "record": record}, sort_keys=True) + "\n")


class CrossCampaignLifecycleTests(unittest.TestCase):
    """SRC-385 finding A: a lifecycle pair binds to ONE campaign.

    The old probe counted a TURN_STARTED in any campaign and a TURN_COMPLETED in
    any OTHER campaign as a live lifecycle and reported LIVE_ACCEPTANCE, so two
    unrelated single events from two projects forged an acceptance that never
    happened. This class is the RED control for that exact defect.
    """

    def test_started_in_one_campaign_never_pairs_with_completed_in_another(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t2011-xcamp-") as tmp:
            root = Path(tmp)
            campaign_dir = root / ".saipen" / "campaign"
            _write_ledger(campaign_dir, [
                ("a-started", {"status": host_dispatch.TURN_STARTED,
                               "receipt": _lifecycle_receipt("camp-A", status=host_dispatch.TURN_STARTED, gen=1, it=1)}),
                ("b-completed", {"status": host_dispatch.TURN_COMPLETED,
                                 "receipt": _lifecycle_receipt("camp-B", status=host_dispatch.TURN_COMPLETED, gen=1, it=1)}),
            ])
            with mock.patch.object(host_authority_client, "verify_record", lambda *a, **k: True):
                result = probe.probe(project_root=root)
            self.assertNotEqual(result["verdict"], probe.LIVE_ACCEPTANCE,
                                "two different campaigns' events forged a lifecycle")
            self.assertIs(result["stages"]["paired_campaign"], False)
            self.assertIsNone(result["stages"]["acceptance_tier"])

    def test_distinct_lineage_or_host_also_keeps_events_apart(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t2011-xline-") as tmp:
            root = Path(tmp)
            campaign_dir = root / ".saipen" / "campaign"
            _write_ledger(campaign_dir, [
                ("l1", {"status": host_dispatch.TURN_STARTED,
                        "receipt": _lifecycle_receipt("camp-A", status=host_dispatch.TURN_STARTED, gen=1, it=1, lineage="lin-1")}),
                ("l2", {"status": host_dispatch.TURN_COMPLETED,
                        "receipt": _lifecycle_receipt("camp-A", status=host_dispatch.TURN_COMPLETED, gen=1, it=1, lineage="lin-2")}),
            ])
            with mock.patch.object(host_authority_client, "verify_record", lambda *a, **k: True):
                stages = probe._authenticated_lifecycle(campaign_dir)
            self.assertIs(stages["paired_campaign"], False)
            self.assertIsNone(stages["acceptance_tier"])

    def test_one_completed_turn_is_single_turn_tier_not_continuation(self) -> None:
        """A single turn is not autonomous continuation (the OVERNIGHT claim)."""
        with tempfile.TemporaryDirectory(prefix="t2011-one-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"
            _write_ledger(campaign_dir, [
                ("s1", {"status": host_dispatch.TURN_STARTED,
                        "receipt": _lifecycle_receipt("camp-A", status=host_dispatch.TURN_STARTED, gen=1, it=1)}),
                ("c1", {"status": host_dispatch.TURN_COMPLETED,
                        "receipt": _lifecycle_receipt("camp-A", status=host_dispatch.TURN_COMPLETED, gen=1, it=1)}),
            ])
            with mock.patch.object(host_authority_client, "verify_record", lambda *a, **k: True):
                stages = probe._authenticated_lifecycle(campaign_dir)
            self.assertIs(stages["paired_campaign"], True)
            self.assertEqual(stages["multi_turn_continuation"], 0)
            self.assertEqual(stages["acceptance_tier"], probe.SINGLE_TURN_COMPLETED)

    def test_genuine_same_campaign_continuation_reaches_over_tiers(self) -> None:
        """Positive control: sustained same-campaign turns grade upward."""
        with tempfile.TemporaryDirectory(prefix="t2011-multi-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"
            records = []
            for i in range(1, 4):
                records.append((f"s{i}", {"status": host_dispatch.TURN_STARTED,
                                          "receipt": _lifecycle_receipt("camp-A", status=host_dispatch.TURN_STARTED, gen=1, it=i)}))
                records.append((f"c{i}", {"status": host_dispatch.TURN_COMPLETED,
                                          "receipt": _lifecycle_receipt("camp-A", status=host_dispatch.TURN_COMPLETED, gen=1, it=i)}))
            _write_ledger(campaign_dir, records)
            with mock.patch.object(host_authority_client, "verify_record", lambda *a, **k: True):
                stages = probe._authenticated_lifecycle(campaign_dir)
            self.assertEqual(stages["multi_turn_continuation"], 2)
            self.assertIs(stages["successor_turn_started"], True)
            self.assertEqual(stages["acceptance_tier"], probe.OVERNIGHT_PRODUCTION_ACCEPTANCE)

    def test_unauthenticated_records_never_form_a_campaign(self) -> None:
        """Broker authentication gates the pair, not just the verdict."""
        with tempfile.TemporaryDirectory(prefix="t2011-unauth-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"
            _write_ledger(campaign_dir, [
                ("s1", {"status": host_dispatch.TURN_STARTED,
                        "receipt": _lifecycle_receipt("camp-A", status=host_dispatch.TURN_STARTED, gen=1, it=1)}),
                ("c1", {"status": host_dispatch.TURN_COMPLETED,
                        "receipt": _lifecycle_receipt("camp-A", status=host_dispatch.TURN_COMPLETED, gen=1, it=1)}),
            ])
            stages = probe._authenticated_lifecycle(campaign_dir)  # real broker, no mock
            self.assertIs(stages["paired_campaign"], False)
            self.assertIsNone(stages["acceptance_tier"])


class AuthorityPresenceIsNotAuthorizationTests(unittest.TestCase):
    """SRC-385 finding B: a declared authority field is not a granted one.

    The live project STATE carried `continuation_authority: operator_required`
    with `safety_valve_mode: hard_wait` -- the operator still owing an action --
    yet the old probe read any non-sentinel string as authority PRESENT and
    reported the authority link as satisfied. Presence must never be read as
    authorization.
    """

    def _root_with_state(self, extra: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix="t2011-auth-"))
        (root / ".saipen").mkdir(parents=True, exist_ok=True)
        # A structurally VALID STATE: parse_state rejects a corrupt one with a
        # bare {"phase": "CORRUPT"} dict, which would make every case "ABSENT"
        # and hide the classification this class tests.
        base = (
            "phase: BUILD\ntask: T-100\nnext_action: \"PHASE BUILD T-100\"\n"
            "blocker: none\ntransition_from: SCOUT\nsaipen_version: 8\n"
            "schema_version: 3\nagent: fixture\nmode: full\n"
            "updated: 2026-01-01T00:00:00Z\nexecution_intent: goal\n"
            "goal_tickets: 5\ngoal_waves: 0\n"
        )
        (root / ".saipen" / "STATE.md").write_text(
            "---\n" + base + extra + "---\n", encoding="utf-8"
        )
        return root

    def test_operator_required_is_declared_not_granted(self) -> None:
        root = self._root_with_state(
            "continuation_authority: operator_required\nauthority_source: E-1\n"
            "authority_until: budget\nsafety_valve_mode: hard_wait\n"
        )
        _session_bound, authority = probe._session_and_authority(root)
        self.assertEqual(authority, "DECLARED_NOT_GRANTED")

    def test_no_authority_field_at_all_is_absent(self) -> None:
        root = self._root_with_state("")
        _session_bound, authority = probe._session_and_authority(root)
        self.assertEqual(authority, "ABSENT")

    def test_a_foreign_grant_family_never_assembles_granted(self) -> None:
        """A well-shaped-but-unprovable declaration is still not authority."""
        root = self._root_with_state(
            "continuation_authority: operator_persistent\nauthority_source: E-999999\n"
            "authority_until: continuous_maintenance\nsafety_valve_mode: checkpoint\n"
            "goal_ingress: goal-0123456789abcdef\n"
        )
        _session_bound, authority = probe._session_and_authority(root)
        self.assertNotEqual(authority, "GRANTED")


class CampaignTransportGateTests(unittest.TestCase):
    """P0-03: the campaign driver must consult a registered native transport.

    Before the repair the gate required a Python `host_hook` the CLI never
    supplies, so the driver only ever persisted and a registered transport was
    never asked. The campaign is this module's own admitted fixture, driven one
    bounded step by a stub worker.
    """

    def setUp(self) -> None:
        from campaign_test_support import inspect_fixture_campaign

        self._patcher = mock.patch(
            "saipen_engine.host_authority_client.inspect_operator_campaign",
            side_effect=inspect_fixture_campaign,
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)
        self.root = _fixture_project()
        self.controller = campaign.CampaignController(self.root)
        admitted = self.controller.admit_campaign(
            campaign_id="CAMP-T2011",
            authority_proof_reference=".saipen/authority/grant.json",
        )
        self.assertTrue(admitted.get("ok"), admitted)

    @staticmethod
    def _worker(project_root, generation):
        return {"progress_verified": True, "mutated": True}

    def _run_one(self):
        running = mock.patch.object(
            ca, "assess_continuation",
            return_value={"classification": ca.ACTIVE_WORK, "next_action": "execute_work"},
        )
        with running:
            return self.controller.run(max_steps=1, worker_func=self._worker)

    def test_a_registered_transport_is_consulted(self) -> None:
        with mock.patch.dict(os.environ, {"HOST_SCHEDULER_DISPATCH_CMD": _transport_script()}):
            result = self._run_one()
        self.assertTrue(result["ok"], result.get("detail"))
        dispatch = result["steps"][0].get("dispatch")
        self.assertIsNotNone(dispatch, "a registered transport was never consulted")
        self.assertIn("status", dispatch)

    def test_no_transport_means_no_dispatch_attempt(self) -> None:
        for name in ("HOST_SCHEDULER_DISPATCH_CMD", "HOST_DISPATCH_ENDPOINT"):
            os.environ.pop(name, None)
        result = self._run_one()
        self.assertTrue(result["ok"], result.get("detail"))
        self.assertIsNone(result["steps"][0].get("dispatch"))


class WindowsTransportTests(unittest.TestCase):
    """P0-03: a registered env transport must actually be reachable."""

    def test_native_windows_command_path_is_split_without_mangling(self) -> None:
        tokens = host_dispatch.split_host_command(f'{sys.executable} -c "print(1)"')
        self.assertEqual(tokens[0], sys.executable)
        self.assertTrue(Path(tokens[0]).is_file(), f"argv[0] was mangled: {tokens[0]!r}")

    def test_a_registered_command_transport_reaches_the_host(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t2011-cmd-") as tmp:
            root = Path(tmp)
            payload = host_dispatch.build_dispatch_payload(root, campaign_id="c-cmd")
            with mock.patch.object(host_authority_client, "verify_record", lambda *a, **k: True), \
                 mock.patch.dict(os.environ, {"HOST_SCHEDULER_DISPATCH_CMD": _transport_script()}):
                result = host_dispatch.dispatch_next_turn(root, payload, print_advisory=False)
            self.assertIs(result["dispatched"], True)
            self.assertEqual(result["mode"], "host_command")
            self.assertEqual(result["status"], host_dispatch.HOST_ACCEPTED)


class TaxonomyTests(unittest.TestCase):
    """P0-03: every declared state must be reachable from a real fact.

    `_taxonomy` is a pure function of the facts the probe reads, so each state
    is exercised by supplying exactly the fact that produces it. A state that
    no fact can produce is a fabricated label, which is the defect this class
    exists to catch.
    """

    def _taxonomy(self, **overrides) -> str:
        facts = {
            "transport": {"host_scheduler_dispatch_cmd": False, "host_dispatch_endpoint": False},
            "broker_alive": False,
            "installation": {"installed_adapters": ["zaicode"], "scheduler_supported": False},
            "session_bound": True,
            # SRC-385 finding B: authority is a CLASSIFIED state, never a bare
            # presence boolean. GRANTED is the fully-authorized state the
            # downstream (scheduler) links are gated behind.
            "authority": "GRANTED",
        }
        facts.update(overrides)
        return probe._taxonomy(**facts)

    def test_no_installed_host_is_reported_as_not_installed(self) -> None:
        self.assertEqual(
            self._taxonomy(installation={"installed_adapters": [], "scheduler_supported": False}),
            probe.HOST_NOT_INSTALLED,
        )

    def test_installed_host_without_transport_is_transport_unregistered(self) -> None:
        self.assertEqual(self._taxonomy(), probe.HOST_INSTALLED_TRANSPORT_UNREGISTERED)

    def test_a_registered_transport_without_a_broker_is_broker_unavailable(self) -> None:
        self.assertEqual(
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": False},
                broker_alive=False,
            ),
            probe.BROKER_UNAVAILABLE,
        )

    def test_an_unbound_session_is_reported_as_unbound(self) -> None:
        self.assertEqual(
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": False},
                broker_alive=True,
                session_bound=False,
            ),
            probe.SESSION_UNBOUND,
        )

    def test_missing_continuation_authority_is_reported_as_missing(self) -> None:
        self.assertEqual(
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": False},
                broker_alive=True,
                authority="ABSENT",
            ),
            probe.AUTHORITY_MISSING,
        )

    def test_declared_but_ungranted_authority_is_not_missing_and_not_granted(self) -> None:
        """SRC-385 finding B: `operator_required` is a distinct, honest state.

        The old probe read any non-sentinel `continuation_authority` string as
        authority present, so an operator-owed action scored exactly like a
        granted campaign. A declaration that no operator grant backs must be
        its own outcome, never `AUTHORITY_MISSING` (which would understate a
        declared obligation) and never silently `SCHEDULER_AVAILABLE`.
        """
        self.assertEqual(
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": True},
                broker_alive=True,
                authority="DECLARED_NOT_GRANTED",
            ),
            probe.AUTHORITY_DECLARED_NOT_GRANTED,
        )

    def test_a_host_without_an_iteration_gate_is_scheduler_unsupported(self) -> None:
        self.assertEqual(
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": False},
                broker_alive=True,
                installation={"installed_adapters": ["zaicode"], "scheduler_supported": False},
            ),
            probe.SCHEDULER_UNSUPPORTED,
        )

    def test_all_links_present_is_scheduler_available(self) -> None:
        self.assertEqual(
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": False},
                broker_alive=True,
                installation={"installed_adapters": ["zaicode"], "scheduler_supported": True},
            ),
            probe.SCHEDULER_AVAILABLE,
        )

    def test_the_declared_vocabulary_is_exactly_these_eight_states(self) -> None:
        """RED CONTROL: a label with no producing fact is the original defect."""
        declared = {
            probe.HOST_NOT_INSTALLED,
            probe.HOST_INSTALLED_TRANSPORT_UNREGISTERED,
            probe.BROKER_UNAVAILABLE,
            probe.SESSION_UNBOUND,
            probe.AUTHORITY_MISSING,
            probe.AUTHORITY_DECLARED_NOT_GRANTED,
            probe.SCHEDULER_UNSUPPORTED,
            probe.SCHEDULER_AVAILABLE,
        }
        reachable = {
            self._taxonomy(installation={"installed_adapters": [], "scheduler_supported": False}),
            self._taxonomy(),
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": False}
            ),
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": True},
                broker_alive=True,
                session_bound=False,
            ),
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": True},
                broker_alive=True,
                authority="ABSENT",
            ),
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": True},
                broker_alive=True,
                authority="DECLARED_NOT_GRANTED",
            ),
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": True},
                broker_alive=True,
            ),
            self._taxonomy(
                transport={"host_scheduler_dispatch_cmd": True, "host_dispatch_endpoint": True},
                broker_alive=True,
                installation={"installed_adapters": ["zaicode"], "scheduler_supported": True},
            ),
        }
        self.assertEqual(len(declared), 8)
        self.assertEqual(reachable, declared, "a declared taxonomy state has no producing fact")

    def test_installation_facts_come_from_the_adapter_registry(self) -> None:
        """SRC-028:R008: no second handwritten host inventory in this module.

        The facts are supplied by a synthetic registry entry under a real
        existing directory, so the control proves the data flows from
        `admission.list_adapters` and fails the moment a hardcoded path
        replaces it.
        """
        from saipen_engine import admission

        with tempfile.TemporaryDirectory(prefix="t2011-reg-") as tmp:
            entry = {
                "id": "synthetic",
                "install": {"home": tmp},
                "hook_install_surface": None,
                "iteration_controller": {"enforcement": "BLOCKING -- gate installed"},
            }
            with mock.patch.object(admission, "list_adapters", lambda: [entry]):
                result = probe._host_installation()
        self.assertEqual(result["installed_adapters"], ["synthetic"])
        self.assertIs(result["scheduler_supported"], True)

    def test_the_shipped_zaicode_adapter_declares_no_iteration_gate(self) -> None:
        """The live P0-03 fact, read from the registry rather than hardcoded."""
        from saipen_engine import admission

        zaicode = admission.get_adapter("zaicode")
        self.assertIsNotNone(zaicode)
        enforcement = str((zaicode.get("iteration_controller") or {}).get("enforcement") or "")
        self.assertTrue(enforcement.upper().startswith("ADVISORY"), enforcement)


def _record(status: str, receipt: dict) -> dict:
    """One journal record: the wrapper status plus its nested receipt."""
    return {"status": status, "receipt": receipt}


def _op(campaign_id: str, status: str, *, gen: int = 1, it: int = 1,
        lineage: str = "lineage-1", host: str = "h-1", goal=_NO_GOAL) -> dict:
    """A lifecycle receipt in the shape the ledger stores."""
    return _lifecycle_receipt(
        campaign_id, status=status, gen=gen, it=it, lineage=lineage, host=host,
        goal=goal,
    )


class SRC387LifecyclePairingTests(unittest.TestCase):
    """SRC-387 findings A-D: pair per operation, bind the receipt, scan newest.

    Each control is a RED reproduction of one archived verifier defect. They
    are negative controls: the pre-repair algorithm returns acceptance, the
    repaired one refuses.
    """

    def _probe_stages(self, campaign_dir: Path) -> dict:
        with mock.patch.object(host_authority_client, "verify_record", lambda *a, **k: True):
            return probe._authenticated_lifecycle(campaign_dir)

    def test_unpaired_completions_never_form_a_lifecycle(self) -> None:
        """Finding A / regressions 1-2: START at it=1, COMPLETEs at 2,3,4.

        The archived algorithm counted distinct completed ordinals after
        finding any START, reporting OVERNIGHT_PRODUCTION_ACCEPTANCE from three
        completions that were never started. Matching per operation leaves
        every COMPLETE unmatched, so no pair and no tier exists.
        """
        with tempfile.TemporaryDirectory(prefix="t2017-unpaired-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"
            records = [("s1", _record(host_dispatch.TURN_STARTED,
                                      _op("camp-A", host_dispatch.TURN_STARTED, it=1)))]
            for it in (2, 3, 4):
                records.append((f"c{it}", _record(
                    host_dispatch.TURN_COMPLETED,
                    _op("camp-A", host_dispatch.TURN_COMPLETED, it=it),
                )))
            _write_ledger(campaign_dir, records)
            stages = self._probe_stages(campaign_dir)
            self.assertIs(stages["paired_campaign"], False)
            self.assertIsNone(stages["acceptance_tier"])
            self.assertEqual(stages["multi_turn_continuation"], 0)
            self.assertFalse(stages["turn_completed"])

    def test_a_completing_receipt_under_a_start_wrapper_is_refused(self) -> None:
        """Finding B / regression 3: wrapper COMPLETE over receipt START.

        The archived verifier authenticated the nested receipt but classified
        the event by the enclosing journal status, so a mutable wrapper
        promoted a broker-authenticated START to a completion. The wrapper now
        must agree with the receipt or the event is dropped.
        """
        with tempfile.TemporaryDirectory(prefix="t2017-wrapper-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"
            started = _op("camp-A", host_dispatch.TURN_STARTED, it=1)
            _write_ledger(campaign_dir, [
                ("s1", _record(host_dispatch.TURN_STARTED, started)),
                # The wrapper lies COMPLETE; the authenticated receipt says START.
                ("c1", _record(host_dispatch.TURN_COMPLETED, dict(started))),
            ])
            stages = self._probe_stages(campaign_dir)
            self.assertFalse(stages["turn_completed"])
            self.assertIs(stages["paired_campaign"], False)
            self.assertIsNone(stages["acceptance_tier"])

    def test_fifty_older_acceptances_do_not_hide_later_lifecycle(self) -> None:
        """Finding C / regressions 6-7: early records must not starve the scan.

        The archived loop verified the first 50 records and stopped, so a
        HOST_ACCEPTED backlog returned HOST_ACCEPTED_NOT_EXECUTION even with a
        real pair behind it. The newer pair must be found, and a scan that
        left records unverified must say so.
        """
        with tempfile.TemporaryDirectory(prefix="t2017-starvation-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"
            records = [
                (f"a{i}", _record(host_dispatch.HOST_ACCEPTED,
                                  _op("camp-A", host_dispatch.HOST_ACCEPTED, it=i)))
                for i in range(60)
            ]
            records.append(("s", _record(
                host_dispatch.TURN_STARTED, _op("camp-A", host_dispatch.TURN_STARTED, it=99))))
            records.append(("c", _record(
                host_dispatch.TURN_COMPLETED, _op("camp-A", host_dispatch.TURN_COMPLETED, it=99))))
            _write_ledger(campaign_dir, records)
            stages = self._probe_stages(campaign_dir)
            self.assertIs(stages["paired_campaign"], True)
            self.assertIs(stages["turn_completed"], True)
            self.assertEqual(stages["acceptance_tier"], probe.SINGLE_TURN_COMPLETED)
            self.assertGreater(stages["truncated_unverified"], 0,
                               "an incomplete bounded scan must be reported")

    def test_reordered_lifecycle_fails_closed(self) -> None:
        """Regression 5: a COMPLETE observed before its START is not a pair."""
        with tempfile.TemporaryDirectory(prefix="t2017-order-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"
            _write_ledger(campaign_dir, [
                ("c1", _record(host_dispatch.TURN_COMPLETED,
                               _op("camp-A", host_dispatch.TURN_COMPLETED, it=1))),
                ("s1", _record(host_dispatch.TURN_STARTED,
                               _op("camp-A", host_dispatch.TURN_STARTED, it=1))),
            ])
            stages = self._probe_stages(campaign_dir)
            self.assertIs(stages["paired_campaign"], False)
            self.assertIsNone(stages["acceptance_tier"])

    def test_duplicate_transition_for_one_operation_fails_closed(self) -> None:
        """Regression 5: one operation cannot START twice and count."""
        with tempfile.TemporaryDirectory(prefix="t2017-dup-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"
            rec = _op("camp-A", host_dispatch.TURN_STARTED, it=1)
            _write_ledger(campaign_dir, [
                ("s1", _record(host_dispatch.TURN_STARTED, rec)),
                ("s2", _record(host_dispatch.TURN_STARTED, dict(rec))),
                ("c1", _record(host_dispatch.TURN_COMPLETED,
                               _op("camp-A", host_dispatch.TURN_COMPLETED, it=1))),
            ])
            stages = self._probe_stages(campaign_dir)
            self.assertIs(stages["paired_campaign"], False)
            self.assertIsNone(stages["acceptance_tier"])

    def test_a_missing_operation_identity_never_joins_another_event(self) -> None:
        """Regression 4: an unidentified event fails closed, never pairs."""
        with tempfile.TemporaryDirectory(prefix="t2017-noid-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"

            def _bare(status: str) -> dict:
                # Identity fields but NO operation identity (no idempotency
                # key, no request id): the shape a migrated record can have.
                return {
                    "schema_version": host_dispatch.ACCEPTANCE_SCHEMA_VERSION,
                    "status": status,
                    "campaign_id": "camp-A",
                    "project_lineage": "lineage-1",
                    "accepting_host": "h-1",
                }

            _write_ledger(campaign_dir, [
                ("s1", _record(host_dispatch.TURN_STARTED, _bare(host_dispatch.TURN_STARTED))),
                ("c1", _record(host_dispatch.TURN_COMPLETED, _bare(host_dispatch.TURN_COMPLETED))),
            ])
            stages = self._probe_stages(campaign_dir)
            self.assertIs(stages["paired_campaign"], False)
            self.assertIsNone(stages["acceptance_tier"])

    def test_a_distinct_goal_binding_keeps_events_apart(self) -> None:
        """Regression 4: same campaign id under a different goal is not one run."""
        with tempfile.TemporaryDirectory(prefix="t2017-goal-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"
            s = _op("camp-A", host_dispatch.TURN_STARTED, it=1)
            s["goal_binding"] = {"path": "STATE.md", "fingerprint": "goal-a"}
            c = _op("camp-A", host_dispatch.TURN_COMPLETED, it=1)
            c["goal_binding"] = {"path": "STATE.md", "fingerprint": "goal-b"}
            _write_ledger(campaign_dir, [
                ("s1", _record(host_dispatch.TURN_STARTED, s)),
                ("c1", _record(host_dispatch.TURN_COMPLETED, c)),
            ])
            stages = self._probe_stages(campaign_dir)
            self.assertIs(stages["paired_campaign"], False)
            self.assertIsNone(stages["acceptance_tier"])

    def test_a_missing_goal_binding_never_pairs_anything(self) -> None:
        """Regression 4: a missing identity component fails closed.

        Two events that both omit goal_binding are two unrelated single
        events, never one campaign's lifecycle -- an absent field must never
        become a shared bucket.
        """
        with tempfile.TemporaryDirectory(prefix="t2017-nogoal-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"
            _write_ledger(campaign_dir, [
                ("s1", _record(host_dispatch.TURN_STARTED,
                               _op("camp-A", host_dispatch.TURN_STARTED, goal=None))),
                ("c1", _record(host_dispatch.TURN_COMPLETED,
                               _op("camp-A", host_dispatch.TURN_COMPLETED, goal=None))),
            ])
            stages = self._probe_stages(campaign_dir)
            self.assertIs(stages["paired_campaign"], False)
            self.assertIsNone(stages["acceptance_tier"])

    def test_a_missing_campaign_id_also_fails_closed(self) -> None:
        """Regression 4: the same fail-closed rule for the campaign component."""
        with tempfile.TemporaryDirectory(prefix="t2017-nocamp-") as tmp:
            campaign_dir = Path(tmp) / ".saipen" / "campaign"
            _write_ledger(campaign_dir, [
                ("s1", _record(host_dispatch.TURN_STARTED,
                               _op("", host_dispatch.TURN_STARTED))),
                ("c1", _record(host_dispatch.TURN_COMPLETED,
                               _op("", host_dispatch.TURN_COMPLETED))),
            ])
            stages = self._probe_stages(campaign_dir)
            self.assertIs(stages["paired_campaign"], False)
            self.assertIsNone(stages["acceptance_tier"])


if __name__ == "__main__":
    unittest.main()
