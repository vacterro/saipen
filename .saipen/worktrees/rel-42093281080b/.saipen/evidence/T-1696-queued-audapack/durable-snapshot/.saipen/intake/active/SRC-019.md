# T05 — EVENT-DRIVEN DISPATCH REFRESH

Priority: P0
Depends on: T03

## Current state

Audit file changes already use a generation watcher.

BrowserDispatcher also already writes:
`browser_dispatch_generation.json`

Project Room currently relies largely on a 10-second runtime poll for dispatch transitions.

## Work

1. Add a public helper for the dispatcher generation path.
2. Watch it with `QFileSystemWatcher`.
3. Debounce file changes.
4. Refresh:
   - affected project when project_id is available;
   - worker summary when relevant.
5. Keep slow HTTP polling as a fallback only.

Recommended fallback:
15-30 seconds.

## UI target

Normal visible state transitions should appear almost immediately:
`WAITING -> ATTACHING -> STARTING -> AUDIT -> SAVING -> READY`

without waiting up to ten seconds.

## Robustness

Watcher may lose file after atomic replace.
Re-add the watched path just like existing audit generation handling.

Do not introduce sub-second HTTP polling.
