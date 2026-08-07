done: v7.211.0 -- the HUNT->ADD routing and the valve resume key are now intent-aware (T-539): under converge a clean HUNT routes to CLEAN/finalization, never ADD; the converge valve pause reads `run 'cc'`, never `run 'saipen goal'`. Shipped f14a3ec, tag v7.211.0
remaining: T-540 -- end the HUNT/CLEAN ownership duplication (hunt.md detect-only, clean.md owns every hygiene mutation)
awaiting: nothing
