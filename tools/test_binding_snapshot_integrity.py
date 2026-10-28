"""Exercise the real publisher's snapshot functions on disposable bindings."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell')
sys.path.insert(0, str(ROOT / 'tools'))
HARNESS = r'''
$ErrorActionPreference = 'Stop'
$errors = $null; $tokens = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($env:SNAPSHOT_SUBJECT, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Publisher parse failed' }
$names = @('Get-BindingFiles', 'Backup-Bindings', 'Restore-Bindings')
$nodes = $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in $names}, $true)
if ($nodes.Count -ne 3) { throw 'Snapshot functions not found' }
foreach ($node in $nodes) { . ([scriptblock]::Create($node.Extent.Text)) }
function Write-Log([string]$message) { Write-Verbose $message }
$profileRoot = $env:USERPROFILE
$bin = Join-Path $profileRoot 'bin'
$localBin = Join-Path $profileRoot '.local\bin'
[IO.Directory]::CreateDirectory($bin) | Out-Null
[IO.Directory]::CreateDirectory($localBin) | Out-Null
$first = Join-Path $bin 'saipen.cmd'
$second = Join-Path $localBin 'saipen.cmd'
[IO.File]::WriteAllText($first, 'FIRST ORIGINAL')
[IO.File]::WriteAllText($second, 'SECOND ORIGINAL')
$backup = Join-Path $profileRoot 'snapshot'
if ($env:SNAPSHOT_CASE -eq 'locked') {
    $held = [IO.File]::Open($first, 'Open', 'ReadWrite', 'None')
    try { $manifest = Backup-Bindings @() $backup } finally { $held.Dispose() }
    if ($manifest) { [void](Restore-Bindings $manifest) }
    @{ refused = (-not $manifest); original = (Test-Path -LiteralPath $first) } | ConvertTo-Json -Compress
} else {
    $manifest = Backup-Bindings @() $backup
    if (-not $manifest) { throw 'Snapshot unexpectedly refused' }
    [IO.File]::WriteAllText($first, 'FIRST INJECTED')
    [IO.File]::WriteAllText($second, 'SECOND INJECTED')
    $newFile = Join-Path $localBin 'saipen'
    [IO.File]::WriteAllText($newFile, 'NEW INJECTED')
    $restored = Restore-Bindings $manifest
    @{ restored = $restored; first = [IO.File]::ReadAllText($first)
       second = [IO.File]::ReadAllText($second); absentRestored = (-not (Test-Path -LiteralPath $newFile)) } | ConvertTo-Json -Compress
}
'''


@unittest.skipUnless(os.name == 'nt' and POWERSHELL, 'Windows publisher bindings')
class BindingSnapshotIntegrityTests(unittest.TestCase):
    def run_case(self, name):
        with tempfile.TemporaryDirectory(prefix='saipen-binding-integrity-') as folder:
            env = dict(os.environ, USERPROFILE=folder, HOME=folder,
                APPDATA=str(Path(folder)/'AppData/Roaming'), LOCALAPPDATA=str(Path(folder)/'AppData/Local'),
                SNAPSHOT_CASE=name,
                SNAPSHOT_SUBJECT=os.environ.get('SAIPEN_BINDING_TEST_SUBJECT', str(ROOT/'bootstrap/schedule-run.ps1')))
            encoded = base64.b64encode(HARNESS.encode('utf-16-le')).decode('ascii')
            process = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            return json.loads(process.stdout)

    def test_distinct_launcher_directories_keep_their_own_bytes(self):
        result = self.run_case('restore')
        self.assertTrue(result['restored'])
        self.assertEqual(result['first'], 'FIRST ORIGINAL')
        self.assertEqual(result['second'], 'SECOND ORIGINAL')

    def test_a_previously_absent_binding_is_removed_on_rollback(self):
        self.assertTrue(self.run_case('restore')['absentRestored'])

    def test_an_unreadable_original_refuses_instead_of_becoming_absent(self):
        result = self.run_case('locked')
        self.assertTrue(result['refused'], 'An incomplete snapshot must not authorize publication')
        self.assertTrue(result['original'], 'Failed backup must never erase the original')


@unittest.skipUnless(os.name == 'nt' and POWERSHELL, 'Windows publisher bindings')
class PublisherSnapshotRefusalTests(unittest.TestCase):
    def test_locked_binding_refuses_before_the_source_or_consumers_change(self):
        from test_hermetic_env import isolate_host_session
        from test_t1613_publication_convergence import _Publisher, _DirectoryLock
        isolate_host_session()
        with tempfile.TemporaryDirectory(prefix='saipen-binding-refusal-') as folder:
            box = _Publisher(Path(folder))
            box.install()
            generation = box.published_generation()
            hook = box.home / '.gemini/hooks/saipen-guard.py'
            before = hook.read_bytes()
            box.bump_generation()
            old_log = box.log_text()
            with _DirectoryLock(hook, asks_delete=False):
                run = box.publish()
            delta = box.log_text()[len(old_log):]
            self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(box.published_generation(), generation)
            self.assertEqual(hook.read_bytes(), before)
            self.assertIn('Binding snapshot failed; publication not started', delta)
            self.assertNotIn('inject: head=', delta)


if __name__ == '__main__':
    unittest.main()
