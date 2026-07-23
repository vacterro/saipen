# Behavioral Test: MARKHUNT Dry Record Only

This is a behavioral assertion, not a structural validation. The `saipen markhunt` command MUST perform a dry audit only:
1. It MUST NOT fix or delete any findings it uncovers, unlike the `HUNT` phase.
2. It MUST NOT stop at a predefined cap (e.g., 5 findings), unlike `HUNT`.
3. It MUST append its findings to the `## BLOCKED` section of `BOARD.md` (tagged `[MARKHUNT]`), never to `## TODO`.

An agent that modifies code directly during `MARKHUNT` or places unvetted audit findings in `## TODO` fails conformance.
