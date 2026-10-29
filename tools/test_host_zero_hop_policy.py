"""Exercise both prediction and broker proof on synthetic observed process chains.

No host, hook, service, user profile or authority is started or modified.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from saipen_engine import host_authority_broker as broker
from saipen_engine import host_authority_client as client
from saipen_engine import host_authority_process as process
from saipen_engine.host_authority_transport import Peer


class ZeroHopPolicyTests(unittest.TestCase):
    def decide(self, *, shell=False, bridge=False, signer='FixturePublisher',
               host='zaicode', current=True, limits=0):
        artifact = '/fixture/guard.py'
        argv = ('python.exe', artifact, '--host', host, '--saipen-root', '/fixture')
        chain = [process.ProcessFact(30, 20, '/python.exe', 'python.exe', argv, 30)]
        if shell:
            command = subprocess.list2cmdline(argv)
            chain.append(process.ProcessFact(20, 10, '/cmd.exe', 'cmd.exe',
                                            ('cmd.exe', '/c', command), 20))
        if bridge:
            chain.append(process.ProcessFact(20, 10, '/bridge.exe', 'bridge.exe', ('bridge.exe',), 20))
        chain.append(process.ProcessFact(10, 1, '/zaicode.exe', 'zaicode.exe', ('zaicode.exe',), 10))
        config = dict(host_images=['claude.exe'], host_signers=['FixturePublisher'],
                      hosts={'zaicode': dict(host_images=['zaicode.exe'], max_shells=limits,
                                             bridge_images=['bridge.exe'], max_bridges=limits)})
        settings = broker.settings
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(broker, 'settings', side_effect=lambda policy=None, **kw: settings(config if policy is None else policy, **kw)), \
             patch.object(broker, 'hook_artifacts', return_value=(artifact,)), \
             patch.object(process, 'ancestry', return_value=chain), \
             patch.object(process, 'platform_supported', return_value=True), \
             patch.object(process, 'signing_supported', return_value=True), \
             patch.object(process, 'image_signer', return_value=signer), \
             patch.object(broker.Broker, '_artifact_current', return_value=lambda path: current):
            prediction = client.hook_invocation('zaicode', Path(tmp))
            owner = broker.Broker(config=config, runtime=Path(tmp))
            accepted, code, detail = owner.identify(Peer('synthetic-test', 30), 'zaicode', tmp)
        return prediction, accepted, code, detail

    def test_direct_hook_is_accepted_by_both_paths(self):
        predicted, accepted, code, _ = self.decide()
        self.assertTrue(predicted['ok'], predicted)
        self.assertTrue(accepted, code)

    def test_zero_shell_limit_rejects_a_shell_on_both_paths(self):
        predicted, accepted, _, detail = self.decide(shell=True)
        self.assertFalse(predicted['ok'])
        self.assertFalse(accepted, detail)

    def test_zero_bridge_limit_rejects_an_intermediary_on_both_paths(self):
        predicted, accepted, _, detail = self.decide(bridge=True)
        self.assertFalse(predicted['ok'])
        self.assertFalse(accepted, detail)

    def test_positive_shell_limit_still_accepts_exact_hook_command(self):
        predicted, accepted, code, _ = self.decide(shell=True, limits=1)
        self.assertTrue(predicted['ok'], predicted)
        self.assertTrue(accepted, code)

    def test_positive_bridge_limit_still_accepts_named_intermediary(self):
        predicted, accepted, code, _ = self.decide(bridge=True, limits=1)
        self.assertTrue(predicted['ok'], predicted)
        self.assertTrue(accepted, code)

    def test_prediction_does_not_grant_signer_authority(self):
        predicted, accepted, _, detail = self.decide(signer='UntrustedPublisher')
        self.assertTrue(predicted['ok'], predicted)
        self.assertFalse(accepted, detail)

    def test_stale_hook_bytes_are_refused_by_owner(self):
        predicted, accepted, _, detail = self.decide(current=False)
        self.assertTrue(predicted['ok'], predicted)
        self.assertFalse(accepted, detail)

    def test_hook_cannot_claim_a_different_host(self):
        predicted, accepted, _, detail = self.decide(host='claude')
        self.assertFalse(predicted['ok'])
        self.assertFalse(accepted, detail)


if __name__ == '__main__':
    unittest.main()
