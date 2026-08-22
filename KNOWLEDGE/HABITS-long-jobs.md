# HABITS: long-running shell commands -- never let the agent tool call hang

Two distinct failure classes get misread as "the shell hung". They need
different countermeasures, and both are fully avoidable at call time.

## Class 1: pipe-holding daemons (real hang)

A child process keeps the stdout/stderr pipe handles open after the CLI
itself printed its result. The tool call blocks indefinitely; hard timeouts
and detached launches do NOT reliably fix it. Reproduced three times in one
day with `playwright-cli`.

Offenders: `playwright-cli open|goto|attach|snapshot` (browser daemon),
dev servers (`npm run dev`, `python -m http.server`), watch modes,
`opencode serve`, SSE/stream tails, any long-lived listener spawned from the
agent shell.

Rule: **never spawn a daemon from the agent shell tool.** Verify UI work via
API probes, typecheck/unit/build, non-interactive HTTP inspection. If a real
browser check is required, it runs OUTSIDE the session (separate terminal /
CI) and the agent only reads the artifacts it wrote. If a call already
printed output but the session is stuck, the daemon is alive: kill it in a
SEPARATE bounded call (`playwright-cli kill-all`, `Stop-Process -Id <pid>`),
then resume with non-browser verification. Full write-up:
`HABITS-browser-hang.md`.

## Class 2: silent long batch jobs (fake hang)

Not hung -- just minutes-to-tens-of-minutes of work with NO streaming output,
because stdout was redirected to a file for later grepping. From outside,
silence for 20 minutes is indistinguishable from death. Observed with the
full `tools/run_scenarios.py` conformance suite (hundreds of subprocess
probes) on a fast machine: well past ten minutes per full run.

Rules:

1. **Never wait silently inside one call.** A command expected to run longer
   than ~3-5 minutes must either stream progress or be detached.
2. **Stream when practical**: keep stdout live (filter through `rg`/`Select-String`
   instead of redirecting everything), or print an unbuffered progress line
   per probe group. Silence = perceived hang.
3. **Detach + poll when not**: launch detached, then poll in separate short calls:

   ```powershell
   $p = Start-Process -FilePath python -ArgumentList "tools/run_scenarios.py" `
       -WorkingDirectory "V:\...\_SAIPEN" `
       -RedirectStandardOutput "V:\_TEMP_\opencode\scen.log" `
       -RedirectStandardError  "V:\_TEMP_\opencode\scen.err" `
       -PassThru -WindowStyle Hidden
   $p.Id | Set-Content "V:\_TEMP_\opencode\scen.pid"
   ```

   Then separate calls: `Get-Process -Id (Get-Content ...pid)` for liveness;
   `Get-Content scen.log -Tail 20` for progress; final verdict from the log
   tail / exit marker line. The initiating call returns in under a second.
4. **Prefer scoped runs over full runs while iterating**: the suite's probe
   groups are individually callable (`run_crew_probes`, `run_saicrew_probes`,
   `continuity_probes.main`, ...). Full-suite runs belong to pre-ship
   verification only, and even then detached per rule 3.
5. **Always set the explicit timeout parameter** on shell calls that execute
   anything (default timeouts are too generous to help perception). A bounded
   call that dies cleanly can be retried; a wedged session cannot.
6. **Exit-marker discipline**: long jobs must end with a greppable terminal
   line (the suite already prints its summary last); polling reads look for
   that line instead of guessing completion from process absence alone.

## Quick triage when a call seems stuck

1. Did it ever print anything? Yes -> probably Class 2 (keep waiting or kill
   by PID); No -> suspect Class 1.
2. Is there a child process holding pipes? Check from a separate call.
3. Kill via separate bounded call, never inside the wedged one.
4. Resume with the non-interactive verification path; re-run the killed job
   detached per Class 2 rule 3 if it was a batch.
