# Performance Extension -- EXAMPLE, copy into your project

This file lives in the SAIPEN home as a template, same role as
`extensions/templates/`. Nothing reads this copy automatically -- copy this
folder into *your project's own* `.saipen/extensions/performance/` if you want the
hook (RFC § 1.9). Adjust the commands below to your actual toolchain.

This extension attaches to the `REVIEW` phase.

When an agent enters the `REVIEW` phase on a project that has its own
`.saipen/extensions/performance/` (or legacy root `extensions/performance/`), it MUST read that directory to discover any
performance benchmarking scripts it needs to run.

## Example Usage
- Run `npm run perf` and verify latency is under 50ms.
- Run Lighthouse checks.
- If performance degrades by more than 5%, transition to `BUILD` instead of `SHIP`.
