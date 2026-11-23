# Historical evidence ownership notice

This directory was the durable output of the T-1317 OpenCode native smoke.
During T-1320 verification, the then-current reusable smoke test still used
this literal T-1317 directory and overwrote its manifest and proof. The two
JSON files now describe build `T-1320-opencode-fleet-recovery-20260913.2`, not
the T-1317 generation. They must not be cited as original T-1317 native-smoke
evidence. Their SHA256 hashes after the last legacy write were:

- `MANIFEST-opencode-native-smoke-T-1317.json`:
  `49473c96b617f16d285fd78b96c8d587a47c3dadcab84e56d3354c4317706f7c`
- `native-smoke-proof.json`:
  `fc1b23e2ac0025a5edcc9917cbc437808f65de6c47ab3162b8be7926b5e3fffe`

The original native-smoke bytes were not recoverable from the current archive
or Git history (the directory is untracked). The separate
`T-1317-opencode-live-session/live-session-proof.json` remains present and
records its original T-1317 generation; it is a separate proof, not a
reconstruction of these files.

The reusable smoke now derives its ticket from the shipped build id and uses
a unique run directory under that ticket. A fresh T-1320 smoke is retained
under `T-1320-opencode-native-smoke/`. A later-ticket ownership regression and
byte comparison after a fresh smoke prove this T-1317 directory is no longer
modified by the test.
