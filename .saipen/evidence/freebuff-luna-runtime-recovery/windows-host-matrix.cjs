// Execute unchanged installed SDK functions in a bounded harness, never the server entrypoint.
const fs = require('fs');
const path = require('path');
const os = require('os');
const cp = require('child_process');
const crypto = require('crypto');
const {stripVTControlCharacters} = require('util');
const bundlePath = 'C:/Users/vac34/AppData/Local/Programs/@codebufffreebuff-desktop/resources/orchestrator/orchestrator.js';
const bundle = fs.readFileSync(bundlePath, 'utf8');
const evidence = __dirname;
const fixture = JSON.parse(fs.readFileSync(path.join(evidence, 'cold-fixture.json'), 'utf8'));
const sourceRoot = path.resolve(evidence, '../../..');
const section = bundle.slice(bundle.indexOf('// ../sdk/src/tools/windows-bash.ts'), bundle.indexOf('// ../sdk/src/tools/path-utils.ts\nfunction escapesProject'));
if (!section.startsWith('// ../sdk/src/tools/windows-bash.ts') || !section.includes('function findWindowsBash')) throw Error('Unexpected host source shape');
const loadable = section
 .replace('import { spawnSync } from "child_process";', 'const { spawnSync } = require("child_process");')
 .replace('import * as fs11 from "fs";', 'const fs11 = require("fs");')
 .replace('import * as path15 from "path";', 'const path15 = require("path");');
const bashFunctions = new Function('require', 'getSystemProcessEnv', loadable + '; return {findWindowsBash,translateGitBashPath,createWindowsBashNotFoundError};')(require, () => process.env);
const runStart = bundle.indexOf('var COMMAND_OUTPUT_LIMIT =', bundle.indexOf('// ../sdk/src/tools/run-terminal-command.ts'));
const runEnd = bundle.indexOf('var backgroundCommands =', runStart);
const terminalSection = bundle.slice(runStart, runEnd);
const run = new Function('spawn3','spawnSync2','os7','path23','findWindowsBash','createWindowsBashNotFoundError','getSystemProcessEnv','stripColors', terminalSection + '; return runTerminalCommand;')(
 cp.spawn, cp.spawnSync, os, path, bashFunctions.findWindowsBash, bashFunctions.createWindowsBashNotFoundError, () => process.env, stripVTControlCharacters);
const noBashEnv = {...process.env};
for (const key of Object.keys(noBashEnv)) {
 if (/^(path|programfiles|programw6432|programfiles\(x86\)|localappdata|userprofile|scoop|scoop_global|systemdrive|codebuff_git_bash_path)$/i.test(key)) noBashEnv[key] = '';
}
noBashEnv.PATH = path.join(process.env.SystemRoot || 'C:/Windows', 'System32');
noBashEnv.CODEBUFF_GIT_BASH_PATH = path.join(evidence, 'intentionally-absent-Git', 'bin', 'bash.exe');
async function call(args) {
 try {return {ok: true, result: await run({command: 'pwd', process_type: 'SYNC', cwd: fixture.project_root, timeout_seconds: 10, ...args})};}
 catch (e) {return {ok: false, error: e.message};}
}
(async () => {
 const cases = {};
 cases.A = await call({});
 const foundWithoutConfiguredPath = bashFunctions.findWindowsBash({...process.env, CODEBUFF_GIT_BASH_PATH: noBashEnv.CODEBUFF_GIT_BASH_PATH}, () => null);
 cases.B_discovery = {configuredPathExists: fs.existsSync(noBashEnv.CODEBUFF_GIT_BASH_PATH), resolvedBash: foundWithoutConfiguredPath};
 cases.C = await call({env: noBashEnv});
 const launcher = path.join(sourceRoot, 'bin', 'saipen.cmd');
 const native = cp.spawnSync(path.join(process.env.SystemRoot || 'C:/Windows', 'System32', 'cmd.exe'),
  ['/d','/c',launcher,'host','bootstrap','--host','freebuff','--project-root',sourceRoot,'--json'],
  {cwd: sourceRoot, env: noBashEnv, encoding: 'utf8', windowsHide: true, timeout: 20000});
 let answer;
 try {answer = JSON.parse(native.stdout);} catch {answer = {parseError: true, stdout: native.stdout, stderr: native.stderr};}
 cases.B_native = {status: native.status, error: native.error?.message, code: answer.code, project_root: answer.project_root, launcher: answer.launcher, command: [launcher,'host','bootstrap','--host','freebuff','--project-root',sourceRoot,'--json']};
 const report = {runtime: process.execPath, bundle: {path: bundlePath, sha256: crypto.createHash('sha256').update(bundle).digest('hex')},
  exactSDKSections: {windowsBashSha256: crypto.createHash('sha256').update(section).digest('hex'), terminalSha256: crypto.createHash('sha256').update(terminalSection).digest('hex')},
  scope: 'Windows harness of installed SDK; this is not a running-host or model receipt', cases};
 report.pass = cases.A.ok && cases.A.result[0].value.exitCode === 0 && !cases.B_discovery.configuredPathExists && !!cases.B_discovery.resolvedBash && !cases.C.ok && cases.C.error.includes('Bash is required') && native.status === 0 && answer.code === 'HOST_BOOTSTRAP_BOUND' && answer.project_root === sourceRoot;
 fs.writeFileSync(path.join(evidence, 'windows-host-matrix.json'), JSON.stringify(report, null, 2));
 fs.writeFileSync(path.join(evidence, 'host-windows-bash.excerpt.txt'), section);
 fs.writeFileSync(path.join(evidence, 'host-run-terminal.excerpt.txt'), terminalSection);
 console.log(JSON.stringify(report, null, 2));
 if (!report.pass) process.exitCode = 1;
})().catch(e => {console.error(e.message);process.exitCode=1;});
