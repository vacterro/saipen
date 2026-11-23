# Freebuff Desktop: Windows terminal CWD and cold-start routing

Priority: P1. Status: independently scoped handoff; host source NOT changed.
SAIPEN intake: SRC-254 / T-1794, appended to SRC-253. This receipt authorizes
SAIPEN investigation, not implementation in Freebuff, SAIPAL or the consumer.

## Proven failure owner

Classification **G: independently demonstrated Windows CWD conversion defect**.
Owner: Freebuff Desktop's SDK `executeTool` / `runTerminalCommand` boundary.
Affected consumer: `V:\___VAC\__K\__CODE\_PLUG_SCRIPT\_FREEBUFF_SAI`.
The consumer's name does not make it the owner of Freebuff Desktop's SDK.

Installed host: Freebuff Desktop 0.0.173. Evidence carrier:
`C:\Users\vac34\AppData\Local\Programs\@codebufffreebuff-desktop\resources\orchestrator\orchestrator.js`
SHA-256 `0a4cc44933681c9bcb87804c435d96bff331f72dfae0d7c2db4d539abf64b66d`.
Bundled execution runtime: `resources\bun\bun.exe`, Bun 1.4.2.

The original thread is `96ba4e8c-ef79-47c2-9e91-d2aad7c7096d`, GPT-6 Luna
(`m-5a5d0e255e`). Read-only SQLite evidence binds it to that consumer:
`incident-history.json`, messages 81-86, notably assistant message 82.
The database was opened `mode=ro` with `query_only=ON`; no host engine was
invoked to recover or mutate that history.

Message 82's first terminal call uses `cwd: "."` and successfully starts Bash,
returning `/v/___VAC/__K/__CODE/_PLUG_SCRIPT/_FREEBUFF_SAI`. Its final Git
command exits 128 because the consumer is not a Git repository; this is NOT
a process-spawn failure. Subsequent calls supply that POSIX path as tool CWD.
Four calls in message 82, two in message 84 and one in message 86 fail before
SAIPEN starts. Their actual error is:

```
Failed to spawn command: ENOENT: no such file or directory,
uv_spawn 'C:\Program Files\Git\bin\bash.exe'
```

The failing transformation is installed `executeTool`, line 134738:

```js
cwd: path24.resolve(resolvedCwd, input.cwd ?? ".")
```

On Windows, with the original project root, that becomes
`V:\v\___VAC\__K\__CODE\_PLUG_SCRIPT\_FREEBUFF_SAI`, which does not exist.
`runTerminalCommand` subsequently applies `path23.resolve(cwd)` and passes
it to spawn (lines 133883-133899).

**Bash is present and functional.** The original first call proves it worked
in the failing session. A controlled reproduction with the installed Bun,
same Bash and exact two-stage Windows CWD semantics reproduces the identical
`uv_spawn` ENOENT for the nonexistent CWD. The native CWD and correctly
translated CWD both return `pwd` successfully. See `windows-spawn-probe.json`.
This is not evidence of a missing Git installation or denied executable.
`SAIPEN_HOST_RUNTIME_UNAVAILABLE` appears in the model's final prose, not as
the output of a SAIPEN process in those failed calls.

## Existing reuse points and required host correction

1. Admit this defect in Freebuff Desktop's actual source project, under its
   own live owner and operator authorization. Establish that root independently;
   do not patch the installed bundle or the consumer from SAIPEN authority.
2. Correct the existing CWD resolver before Windows `path.resolve`. Reuse
   `translateGitBashPath` from the shipped `windows-bash.ts`/`path-utils.ts`
   boundary (installed lines 131962-131975), which already understands `/v/...`,
   uses existing cygpath where applicable, and preserves native paths.
3. Preserve explicit project binding and the host's existing CWD fences.
   A genuinely missing directory must remain a refusal. Do not silently replace
   an invalid CWD with a different project, and do not weaken sponsored grants.
4. Diagnose spawn prerequisites separately: requested and resolved CWD,
   directory accessibility, selected executable, executable accessibility and
   original OS error. ENOENT alone cannot prove which prerequisite is missing.
   Do not recommend installing Bash when the executable worked and CWD is wrong.
5. Suppress unchanged retries of an established missing prerequisite. One
   corrected, authorized route may be attempted after the condition changes;
   preserve the original request and binding, and report its actual outcome.

The source excerpts and hashes in `host-windows-bash.excerpt.txt`,
`host-run-terminal.excerpt.txt` and `windows-host-matrix.json` make the installed
code used by the controlled checks independently reviewable.

## Shell availability and safe native continuation

The selected `C:\Program Files\Git\bin\bash.exe` path originates in Freebuff's
`windowsBashCandidates`: `ProgramFiles`/other registered Git roots joined with
`bin\bash.exe` (lines 131832-131900). It is a discovered candidate, not a
SAIPEN-generated launcher and not a single literal hardcoded fallback.
`CODEBUFF_GIT_BASH_PATH`, PATH candidates and Git registry lookup also exist.
A missing configured override correctly falls through to an available Git Bash
in the controlled installed-source check.

The ordinary `run_terminal_command` schema (line 109222) promises Bash syntax;
its Windows branch (133868-133880) requires Bash. It exposes no per-call native
shell selector. When all Bash candidates are absent, it refuses before SAIPEN.
Changing its executable to PowerShell would change arbitrary POSIX behavior.

SAIPEN already has supported `.cmd` and POSIX launchers. A child environment
with no discoverable Bash still starts the trusted native `.cmd` through
Windows cmd and returns `HOST_BOOTSTRAP_BOUND` for the exact SAIPEN root.
The ProgramData runtime's own native diagnostic also returns
`MACHINE_RUNTIME_READY`, proving its registered generation and ACLs.
Its installed generation is older than the current SAIPEN working tree; this
does not mean its executable is missing. No refresh, installation, PATH edit
or privilege escalation was performed.

Freebuff's sponsored Windows broker has an existing PowerShell route
(`windowsPowerShellPath`, `sponsoredWindowsFloorLaunch`, `ownsShell`, installed
137938-138000). That is evidence for that granted broker only. It does NOT
authorize a normal Luna thread to switch brokers or bypass its policy.

For a host-owned native-SAIPEN improvement, reuse a supported existing direct
argv/broker transport only when the ordinary host explicitly exposes and admits
it. Preserve the Windows shell contract and the original project/Work. If none
is supported, report the Freebuff-owned transport limitation accurately.
Add no SAIPEN shell shim, runtime manager, registry, installer loop or guessed
interpreter. The actual incident is recoverable by supplying the correct CWD.

## Real cold-start failure requiring separate routing repair

A new real GPT-6 Luna thread, `587918ed-22b5-46c3-82e3-9c926ea84f3c`, received
exactly `cc` in a disposable read-only project with no lifecycle authority.
Its mission mode was OFF. Artifacts: `luna-cold-dispatch.json`,
`luna-cold-observation.json`, `luna-cold-stop.json`, `cold-fixture.json`.

Acceptance FAIL: the model loaded an active account SAIPAL skill that still
advertises `cc`, read SAIPAL's protocol, and later used a POSIX tool CWD,
reproducing Bash ENOENT in the running host. It did reach the genuine
`NOT_SAIPEN_PROJECT` refusal, but then investigated another project. The owned
test was stopped and reached idle; no SAIPAL command was executed, no fixture
lifecycle was created, and SAIPEN's lifecycle remained at E-15775 during it.
The fixture's instruction and README bytes were unchanged.

The stale skill is the host-loaded account artifact:
`C:\Users\vac34\.config\freebuff-desktop\account-skills\6813fa020ad454e3e6235dc0074ae431d8c490e74c44ffffa46d1f347a22ba20\b643a3203740a538fba292c0c39dff09923fac697951c5b03705f9ae6a2ba7e3\saipal\SKILL.md`.
It says `/saipal cc` and `cc`. Current SAIPAL source uses `pal`.
Use the supported account skill synchronization/import owner to refresh it;
do not hand-edit a content-addressed cache or patch SAIPAL from SAIPEN authority.
The installed SAIPEN activation block in `C:\Users\vac34\.AGENTS.md` is also
stale: it names nonexistent `_SAIPEN\saipen\bin` launchers. Current SAIPEN
activation resolves the runtime home from STATE and has a first-action gate.
Its normal deployment remains governed by the existing distribution/publication
contract (T-1644); do not bypass dirty-source protection to make a test green.

## Regression and acceptance required in Freebuff's own Work

- Original `/v/...` CWD, native `V:/...` and `V:\...`, omitted and relative CWD,
  directory names with spaces/Unicode, and supported cygpath forms.
- Real missing CWD, missing executable, denied CWD/executable and ambiguous
  spawn errors remain distinct. No silent project substitution or retry loop.
- Git Bash present: existing POSIX commands still work unchanged.
- Configured Bash path missing: supported discovery still works; a supported
  native SAIPEN route may run only under its existing host authorization.
- All Bash absent, native SAIPEN present: ordinary Bash-only tool gives an
  accurate host-owned limitation until an admitted native route exists.
- Missing/tampered/untrusted machine runtime: safe refusal, no public clone or
  untrusted interpreter fallback. No authority: runtime starts, mutations refuse.
- Fresh real Luna `cc`: first operational call is canonical SAIPEN, no SAIPAL
  collision, no repeated spawn error, original project identity retained, genuine
  action or authoritative refusal. Unit/harness success is not this acceptance.
- Validate ordinary and sponsored execution boundaries independently.

## T-52 preservation and exact resumption boundary

Consumer lineage: `lineage-fe5afd6d81564116bfdc3b0184adc0ec`.
Current observed STATE: BUILD / T-52 / E-685; BOARD owner `saipen`;
source SRC-020 digest
`2b4aa7a7752be916763a004e0b3af8e4cbccd55c79adbf69aec46c9dff4fc85e`.
Native `host entry --host freebuff` resolves the exact root and trusted runtime.
Admission status is DEGRADED/permitted but **verified:false**, because Freebuff
has advisory enforcement and no admission evidence channel. This is not a new
operator grant, a live claim for this SAIPEN agent, or proof of T-52 conformance.
The read-before-lock race is still unverified and unresolved here.

An independently authorized consumer executor can use the existing ordinary
tool with the native absolute CWD below, or omit CWD when that tool is already
bound to this exact project. First revalidate target identity, live ownership,
admission, task applicability and conformance through the canonical runtime.
Then continue the ORIGINAL T-52 only if those gates authorize it:

```json
{
  "command": "saipen continue --json",
  "process_type": "SYNC",
  "cwd": "V:/___VAC/__K/__CODE/_PLUG_SCRIPT/_FREEBUFF_SAI"
}
```

This is a supported command/CWD form, not evidence that T-52 was resumed or
repaired. No forced claim, replacement ticket or manual lifecycle change.
No Git Bash installation or system PATH change is required for this incident.
