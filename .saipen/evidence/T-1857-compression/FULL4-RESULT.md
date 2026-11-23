# Full-family attempt 4: completed but not citable here

PID 9100 terminated on 2026-10-23 at about 11:46 Europe/Tallinn. Its output was `{"ok": false, "detail": "verification result does not match its requested immutable identity"}`. No CORE-UNIT-EVIDENCE citation was appended to T-1857.

The final record `.saipen/evidence/core-unit/59fb1c80c5ecd09b-20261023T084621946874Z.json` reports PASS, 7,427 tests, zero red, exit 0 and a 1,864.1-second second pass. The current source fingerprint equals the record's full `59fb1c80c5ecd09b808da34aa692da37d40b9455bc8059fd27637e433fdd2103`. The first pass also reported PASS but was invalidated by a concurrent root file change.

Replay under the present session is refused by `reusable_record`: the prior verifier identity used `C:/Users/vac34/.codex/` while this session uses `C:/Users/vac34/.codex-account2/`; captured Git/Bash tool locations and the environment digest also differ. The exact check returned `reusable: False` even with the matching source fingerprint and six jobs. Do not cite either PASS as current-environment VERIFY evidence or change the verifier identity by hand. Run one current-environment full family and retain all records.
