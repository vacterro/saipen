# Performance Extension

This extension attaches to the `REVIEW` phase.

When an agent enters the `REVIEW` phase, it MUST read this directory to discover any performance benchmarking scripts it needs to run.

## Example Usage
- Run `npm run perf` and verify latency is under 50ms.
- Run Lighthouse checks.
- If performance degrades by more than 5%, transition to `BUILD` instead of `SHIP`.
