// Controlled process-spawn reproduction using the installed host's own Bun.
// Only `pwd` is executed in the foreign project. No source or lifecycle writes.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const crypto = require('crypto');
const outputDir = __dirname;
const bundle = 'C:/Users/vac34/AppData/Local/Programs/@codebufffreebuff-desktop/resources/orchestrator/orchestrator.js';
const history = JSON.parse(fs.readFileSync(path.join(outputDir, 'incident-history.json'), 'utf8'));
const first = history.records.find(r => r.seq === 82);
const failed = first.tools.find(t => t.input.command === 'saipen continue --json');
const root = first.project_path;
const inputCwd = failed.input.cwd;
const bash = 'C:\\Program Files\\Git\\bin\\bash.exe';
const resolvedWrong = path.resolve(root, inputCwd); // installed executeTool line 134738
const translated = `${inputCwd[1].toUpperCase()}:\\${inputCwd.slice(3).replace(/\//g, '\\')}`;
function run(cwd) {
 const r = spawnSync(bash, ['-c', 'pwd'], {cwd, env: process.env, windowsHide: true, encoding: 'utf8', timeout: 10000});
 return { cwd, cwdExists: fs.existsSync(cwd), status: r.status, stdout: r.stdout, stderr: r.stderr,
  error: r.error ? {code: r.error.code, syscall: r.error.syscall, path: r.error.path, message: r.error.message} : null };
}
const report = {
 observedUtc: new Date().toISOString(), runtime: { executable: process.execPath, version: process.version, bun: process.versions.bun },
 bundle: { path: bundle, sha256: crypto.createHash('sha256').update(fs.readFileSync(bundle)).digest('hex') },
 sourceMessage: {seq: first.seq, thread: first.thread_id, inputCwd, root},
 bash: { path: bash, exists: fs.existsSync(bash), sha256: crypto.createHash('sha256').update(fs.readFileSync(bash)).digest('hex') },
 native: run(root), incident: run(resolvedWrong), supportedTranslation: run(translated)
};
report.pass = report.native.status === 0 && report.incident.error?.code === 'ENOENT' && !report.incident.cwdExists && report.supportedTranslation.status === 0 && path.normalize(translated) === path.normalize(root);
fs.writeFileSync(path.join(outputDir, 'windows-spawn-probe.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
if (!report.pass) process.exitCode = 1;
