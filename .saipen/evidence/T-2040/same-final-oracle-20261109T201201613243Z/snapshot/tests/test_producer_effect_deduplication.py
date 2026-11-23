"""Regression tests for producer effect deduplication, zero-delta handling,
publication-state classification, and unauthorized goal projection.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_fixture_support import CURRENT_STYLE_CONTRACT
from saipen_engine import producer as P
from saipen_engine import intent
from saipen_engine import goal_authority
from saipen_engine import operations
from saipen_engine import subs
from freshness import compute_source_identity


def wf(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class ProducerEffectDeduplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="eff_"))
        self.root = self.tmp / "project"
        self.root.mkdir()
        subprocess.run(["git", "init", str(self.root)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.com"], check=True)
        wf(self.root, ".gitignore", "kitchen/\n")
        wf(self.root, "src/core.py", "def core():\n    return 1\n")
        wf(self.root, "src/wiki.md", "# Wiki Source\n")
        wf(self.root, ".saipen/IDENTITY.md", "---\nproject_lineage: lineage-b512942bac884a8691f6c98afcd6ddb9\n---\n")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-m", "init"], check=True, stdout=subprocess.DEVNULL)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _publish_pkg(self, ns: Path, producer: str, scope: str, content: str):
        read_paths = ["src/wiki.md"]
        write_paths = ["kitchen/wiki/index.md"]
        read_set = P.read_set_from(self.root, read_paths)
        write_set = P.write_set_before(self.root, write_paths)
        epoch = P.ProducerEpoch.current(ns)
        source_id = compute_source_identity(self.root)
        try:
            role_rev = subs.current_local_role_revision(self.root, producer) or "sha256:rev1"
        except Exception:
            role_rev = "sha256:rev1"
        pkg = P.ProducerPackage(
            producer=producer,
            role_revision=role_rev,
            base_source_head=source_id.source_head,
            base_source_tree_fingerprint=source_id.source_tree_fingerprint,
            base_discovery_model=source_id.discovery_model,
            scope=scope,
            read_set=read_set,
            write_set=write_set,
            epoch=epoch,
        )
        gen = P.StagingGeneration(ns, producer).begin()
        gen.set_package(pkg)
        gen.add_payload("kitchen/wiki/index.md", content)
        pub = gen.publish()
        self.assertTrue(pub["ok"])
        ready, errors = P.StagingGeneration.scan_ready(ns)
        self.assertEqual(errors, [])
        matching = [p for p in ready if p.package_identity == pkg.package_identity]
        self.assertEqual(len(matching), 1)
        return matching[0]

    def test_three_packages_with_different_scopes_detects_no_effect(self) -> None:
        """P0-01 Reproduction:
        Three consecutive packages with identical source, deps, targets, and payload bytes,
        differing only in scope prose and epoch.
        Package 1: integrates normally (wrote=True).
        Package 2 & 3: MUST return NO_EFFECT (wrote=False) instead of re-integrating and
        creating fake work/receipts.
        """
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)

        # Package 1: initial integration
        pkg1 = self._publish_pkg(ns, "saiwiki", "Initial wiki docs", "# Wiki Content V1\n")
        res1 = P.integrate_packages_core([pkg1], self.root, agent="producer-test")
        self.assertEqual(res1["results"][0]["result"], "INTEGRATED")
        self.assertTrue(res1["results"][0]["wrote"])
        self.assertEqual((self.root / "kitchen/wiki/index.md").read_text(), "# Wiki Content V1\n")

        # Package 2: different scope prose, identical payload
        P.ProducerEpoch.claim(ns)
        pkg2 = self._publish_pkg(ns, "saiwiki", "Updated wording for wiki docs", "# Wiki Content V1\n")
        self.assertNotEqual(pkg1.package_identity, pkg2.package_identity)
        # But effect identities must match!
        self.assertTrue(hasattr(P, "package_effect_identity"))
        eff1 = P.package_effect_identity(pkg1)
        eff2 = P.package_effect_identity(pkg2)
        self.assertEqual(eff1, eff2)

        res2 = P.integrate_packages_core([pkg2], self.root, agent="producer-test")
        # Must report NO_EFFECT / ALREADY_CURRENT and wrote=False
        item2 = res2["results"][0]
        self.assertIn(item2["code"], ("NO_EFFECT", "ALREADY_CURRENT", "ALREADY_APPLIED"))
        self.assertFalse(item2.get("wrote", True))

        # Package 3: yet another scope prose, identical payload
        P.ProducerEpoch.claim(ns)
        pkg3 = self._publish_pkg(ns, "saiwiki", "Third phrasing of wiki docs", "# Wiki Content V1\n")
        eff3 = P.package_effect_identity(pkg3)
        self.assertEqual(eff1, eff3)

        res3 = P.integrate_packages_core([pkg3], self.root, agent="producer-test")
        item3 = res3["results"][0]
        self.assertIn(item3["code"], ("NO_EFFECT", "ALREADY_CURRENT", "ALREADY_APPLIED"))
        self.assertFalse(item3.get("wrote", True))

    def test_changed_payload_triggers_new_work(self) -> None:
        """When payload bytes actually change, integration must write and succeed."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)

        pkg1 = self._publish_pkg(ns, "saiwiki", "Scope 1", "# Original\n")
        res1 = P.integrate_packages_core([pkg1], self.root, agent="producer-test")
        self.assertTrue(res1["results"][0]["wrote"])

        P.ProducerEpoch.claim(ns)
        pkg2 = self._publish_pkg(ns, "saiwiki", "Scope 2", "# Changed Bytes\n")
        eff1 = P.package_effect_identity(pkg1)
        eff2 = P.package_effect_identity(pkg2)
        self.assertNotEqual(eff1, eff2)

        res2 = P.integrate_packages_core([pkg2], self.root, agent="producer-test")
        self.assertTrue(res2["results"][0]["wrote"])
        self.assertEqual((self.root / "kitchen/wiki/index.md").read_text(), "# Changed Bytes\n")

    def test_collect_and_ship_producer_no_effect_skips_ticket_add(self) -> None:
        """When an effect is already current or zero delta, collect_and_ship_producer
        retires READY and returns NO_EFFECT without adding duplicate tickets to BOARD.
        """
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)

        # First integration writes and succeeds
        pkg1 = self._publish_pkg(ns, "saiwiki", "Initial scope", "# Wiki Content V1\n")
        res1 = P.integrate_packages_core([pkg1], self.root, agent="producer-test")
        self.assertTrue(res1["results"][0]["wrote"])

        # Second package with same content published to READY
        P.ProducerEpoch.claim(ns)
        pkg2 = self._publish_pkg(ns, "saiwiki", "Different wording", "# Wiki Content V1\n")

        # collect_and_ship_producer should detect NO_EFFECT and retire READY without ticket_add
        st = f"""---
phase: DONE
task: none
next_action: "saipen continue"
blocker: ""
transition_from: SHIP
saipen_version: 8
schema_version: 3
last_event: 1
style_contract: {CURRENT_STYLE_CONTRACT}
saipen_home: "{ROOT.as_posix()}"
agent: test-agent
mode: full
updated: "2026-11-07T05:00:52Z"
execution_intent: normal
---
"""
        wf(self.root, ".saipen/STATE.md", st)
        wf(self.root, ".saipen/BOARD.md", "## DOING\n## TODO\n## DONE\n## BLOCKED\n")
        wf(self.root, ".saipen/LOG.md", "# Log\n- 14.09.26 00:00 [E-0001] [agent: test-agent] [op: transition-" + "a" * 32 + "] RUN: transition to DONE\n")

        from unittest import mock

        with mock.patch.object(subs, "current_local_role_revision", return_value="sha256:rev1"):
            ship_res = intent.collect_and_ship_producer(self.root, "saiwiki")
        self.assertTrue(ship_res["ok"])
        self.assertEqual(ship_res["code"], "NO_EFFECT")
        self.assertFalse(ship_res.get("wrote", True))
        # Ensure READY was retired
        ready, _ = P.StagingGeneration.scan_ready(ns)
        self.assertEqual(ready, [])
        # Ensure no ticket was added to BOARD
        board_text = (self.root / ".saipen/BOARD.md").read_text()
        self.assertNotIn("T-", board_text)

    def test_ignored_output_publication_state_empty(self) -> None:
        """Git-ignored files do not receive publication_state: pending."""
        ns = P.producer_namespace(self.root, "saiwiki")
        P.ProducerEpoch.claim(ns)
        pkg = self._publish_pkg(ns, "saiwiki", "Wiki docs", "# Content\n")
        res = P.integrate_packages_core([pkg], self.root, agent="producer-test", ticket_id="T-999")
        self.assertTrue(res["results"][0]["wrote"])

        pub_state = operations._closure_publication_state(self.root, "T-999")
        self.assertEqual(pub_state, "")

    def test_protected_goal_request_refused_for_model_supplied(self) -> None:
        """Model-supplied input imitating a maintenance goal is refused and linked to blocker."""
        wf(
            self.root,
            ".saipen/goals/self-maintenance-core.json",
            json.dumps({
                "goal_id": "self-maintenance-core",
                "current_status": "ACTIVE",
                "authorization_scope": "MAINTENANCE",
                "objective": "Autonomously discover, evaluate, and repair verified regressions",
                "paused": False,
                "title": "Self Maintenance",
            }),
        )
        st = f"""---
phase: DONE
task: none
next_action: "saipen continue"
blocker: ""
transition_from: SHIP
saipen_version: 8
schema_version: 3
last_event: 1
style_contract: {CURRENT_STYLE_CONTRACT}
saipen_home: "{ROOT.as_posix()}"
agent: test-agent
mode: full
updated: "2026-11-07T05:00:52Z"
execution_intent: normal
---
"""
        wf(self.root, ".saipen/STATE.md", st)
        wf(
            self.root,
            ".saipen/BOARD.md",
            "## DOING\n## TODO\n## DONE\n## BLOCKED\n- [ ] T-2028 [P2] authorize the current self-maintenance PersistentGoal | blocker: requires genuine operator goal entry\n",
        )
        wf(
            self.root,
            ".saipen/LOG.md",
            "# Log\n- 14.09.26 00:00 [E-0001] [agent: test-agent] [op: transition-" + "a" * 32 + "] RUN: transition to DONE\n",
        )

        # Attempt to submit model-supplied request with the exact objective
        res = operations.user_request(
            self.root,
            "test-agent",
            "Autonomously discover, evaluate, and repair verified regressions",
            priority="P2",
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.code, "PROTECTED_OPERATION_BLOCKED")
        self.assertEqual(res.data.get("ticket"), "T-2028")
        # Ensure no new ticket was created on BOARD
        board_text = (self.root / ".saipen/BOARD.md").read_text()
        self.assertNotIn("T-2029", board_text)

    def test_progress_classification_distinguishes_no_effect(self) -> None:
        """campaign._verify_progress_evidence respects ProgressClass and refuses zero delta or unattributed source deltas."""
        from saipen_engine import campaign

        # Zero delta / NO_EFFECT
        res_no_eff = {"code": "NO_EFFECT", "wrote": False, "zero_delta": True}
        ver_no_eff = campaign.CampaignController(self.root)._verify_progress_evidence(
            res_no_eff, observation={"before_event": "E-1", "after_event": "E-2"}
        )
        self.assertFalse(ver_no_eff["made_progress"])
        self.assertEqual(ver_no_eff["progress_class"], campaign.ProgressClass.NO_EFFECT.value)

        # Unattributed source delta without canonical mutation is UNVERIFIED_EFFECT, not made_progress
        res_unattr = {"progress_class": campaign.ProgressClass.SOURCE_CHANGED.value}
        ver_unattr = campaign.CampaignController(self.root)._verify_progress_evidence(
            res_unattr, observation={"before_event": "E-1", "after_event": "E-2", "source_delta": True}
        )
        self.assertFalse(ver_unattr["made_progress"])
        self.assertEqual(ver_unattr["progress_class"], "UNVERIFIED_EFFECT")

        # Positive control: Genuinely current-worker-bound COMMITTED mutation proves SOURCE_CHANGED
        from saipen_engine.journal import _hash_file
        import datetime
        attempt = {
            "attempt_id": "attempt-dedup-1",
            "campaign_id": "CAMP-DEDUP-TEST",
            "generation": 1,
            "started_at": "2026-11-07T09:00:00Z",
        }
        target_path = self.root / "src" / "dedup_mutation.txt"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("dedup mutation\n", encoding="utf-8")
        op_id = "op-dedup-00000001"
        op_dir = self.root / ".saipen" / "recovery" / "ops" / op_id
        op_dir.mkdir(parents=True, exist_ok=True)
        rec = {
            "op_id": op_id,
            "status": "COMMITTED",
            "operation": "worker_mutation",
            "semantic_payload_hash": "sha256:0",
            "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent": "test-agent",
            "project_identity": "test-project",
            "project_lineage": "lineage-b512942bac884a8691f6c98afcd6ddb9",
            "progress_index": 0,
            "targets": [{
                "path": "src/dedup_mutation.txt",
                "role": "generic",
                "action": "write",
                "applied": True,
                "before_hash": "",
                "after_hash": _hash_file(target_path),
            }],
            "receipt_metadata": {
                "attempt_id": "attempt-dedup-1",
                "campaign_id": "CAMP-DEDUP-TEST",
                "worker_generation": 1,
            },
        }
        (op_dir / "operation.json").write_text(json.dumps(rec), encoding="utf-8")
        res_prog = {
            "progress_class": campaign.ProgressClass.SOURCE_CHANGED.value,
            "ok": True,
            "wrote": True,
            "op_id": op_id,
        }
        ver_prog = campaign.CampaignController(self.root)._verify_progress_evidence(
            res_prog,
            observation={"before_event": "E-1", "after_event": "E-2", "source_delta": True},
            attempt=attempt,
        )
        self.assertTrue(ver_prog["made_progress"])
        self.assertEqual(ver_prog["progress_class"], campaign.ProgressClass.SOURCE_CHANGED.value)


if __name__ == "__main__":
    unittest.main()
