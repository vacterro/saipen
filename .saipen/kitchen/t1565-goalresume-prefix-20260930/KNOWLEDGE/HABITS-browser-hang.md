# HABITS — playwright-cli / long-lived pipe hang (Windows)

Observed 2026-08-11 (three times in one day): an agent ran

    Invoke-Expression "$env:PW open http://127.0.0.1:18765" 2>&1 | Select-Object -Last 2

and the session froze hard (up to ~1 hour) even though the CLI printed its
snapshot. The user had to intervene each time.

## Root cause

The Windows shell tool waits for the process tree to release the stdout/stderr
pipe handles. `playwright-cli open/goto/attach` spawn a browser daemon that
outlives the CLI and keeps a handle on the pipe, so the tool never sees EOF.

## What was tried and still failed

1. Plain call with pipe — hang.
2. Hard `timeout` on the shell tool call (30s) — STILL hung: the timeout kills
   the top-level process but not the daemon holding the pipe.
3. Detached launch (`Start-Process -RedirectStandardOutput file`) — the tool
   returned, but the session still froze afterward.

Conclusion: **browser automation through the agent shell tool is not reliable
on this setup, no matter the invocation.** Stop attempting it from the agent.

## The rule (enforced)

1. NEVER run playwright-cli (or any browser/daemon-launching command) from the
   agent's shell tool. Do not pipe it, do not bound it with a timeout, do not
   detach it — all three have failed in practice.
2. Verify UI work WITHOUT a live browser:
   - API data path: `Invoke-WebRequest` / `Invoke-RestMethod` against the
     server routes (works, returns cleanly).
   - Rendering/compile: the package's own typecheck + unit tests + production
     build.
   - The running app's state: non-interactive HTTP probes.
3. If a real browser check is genuinely required, it must run OUTSIDE the agent
   session (a separate terminal the user runs, or a CI job), and the agent
   reads the artifacts it writes (screenshots, snapshot files) — never drives
   it live from the tool loop.
4. If a browser call ever printed output but the session is stuck, the daemon
   is alive: `playwright-cli kill-all` in a separate bounded call, then resume
   with non-browser verification.

Same rule applies to any command that spawns a long-lived daemon (dev servers,
`opencode serve`, watch mode, SSE streams) when its lifetime outlives the tool
call.

## Copies

- Global: C:\Users\vac34\.config\opencode\AGENTS.md
- Project: V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIWORK\CodeNomad\AGENTS.md
