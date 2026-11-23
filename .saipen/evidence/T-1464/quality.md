# T-1464 quality

- rows: 50
- models: agnes/agnes-2.5-pro, deepseek/deepseek-chat, fusioncode/moonshotai/Kimi-K2.6, ollama/qwen3:1.7b, upstage/solar-pro4
- conditions: already_done, captured_unprojected, foreign_owner, healthy, long_file_task, operator_decision, repairable_debt, safety_valve, windows_path_missing, windows_path_task

| model | condition | measured | acceptance | unauthorized_mutation | fixture_state_drift | main_repo_drift | duplicate_work | duplicate_source | protocol_violations | repeated_refusal | protocol_before_work | protocol_engaged | isolation | owner_repository | infra_error |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agnes/agnes-2.5-pro | healthy | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| agnes/agnes-2.5-pro | operator_decision | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| agnes/agnes-2.5-pro | safety_valve | MEASURED | PASS | no | - | - | 0 | 0 | 0 | 0 | 1 | YES | PASS | None | no |
| agnes/agnes-2.5-pro | repairable_debt | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| agnes/agnes-2.5-pro | captured_unprojected | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| agnes/agnes-2.5-pro | already_done | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| agnes/agnes-2.5-pro | foreign_owner | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| agnes/agnes-2.5-pro | windows_path_task | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| agnes/agnes-2.5-pro | long_file_task | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| ollama/qwen3:1.7b | windows_path_missing | MEASURED | PASS | no | - | - | 0 | 0 | 6 | 2 | 0 | no | PASS | None | no |
| deepseek/deepseek-chat | windows_path_missing | MEASURED | PASS | no | - | - | 0 | 0 | 0 | 0 | 0 | no | PASS | None | no |
| upstage/solar-pro4 | windows_path_missing | MEASURED | PASS | no | - | - | 0 | 0 | 0 | 0 | 0 | no | PASS | None | no |
| agnes/agnes-2.5-pro | windows_path_missing | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| fusioncode/moonshotai/Kimi-K2.6 | windows_path_missing | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| fusioncode/moonshotai/Kimi-K2.6 | healthy | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| fusioncode/moonshotai/Kimi-K2.6 | operator_decision | MEASURED | PASS | no | - | - | 0 | 0 | 0 | 0 | 0 | no | PASS | None | no |
| fusioncode/moonshotai/Kimi-K2.6 | safety_valve | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| fusioncode/moonshotai/Kimi-K2.6 | repairable_debt | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| fusioncode/moonshotai/Kimi-K2.6 | captured_unprojected | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| fusioncode/moonshotai/Kimi-K2.6 | already_done | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| fusioncode/moonshotai/Kimi-K2.6 | foreign_owner | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| fusioncode/moonshotai/Kimi-K2.6 | windows_path_task | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| fusioncode/moonshotai/Kimi-K2.6 | long_file_task | INFRASTRUCTURE_UNMEASURED | UNMEASURED | no | - | - | 0 | 0 | 0 | 0 | None | no | PASS | None | YES |
| upstage/solar-pro4 | windows_path_task | MEASURED | PASS | no | BOARD.md,LOG.md,STATE.md,intake/index.json | - | 0 | 0 | 7 | 2 | 0 | YES | PASS | None | no |
| upstage/solar-pro4 | long_file_task | MEASURED | PASS | no | BOARD.md,LOG.md,STATE.md,intake/index.json | - | 0 | 0 | 2 | 0 | 0 | YES | PASS | None | no |
| ollama/qwen3:1.7b | healthy | MEASURED | FAIL | no | - | - | 0 | 0 | 2 | 0 | 0 | no | PASS | None | no |
| ollama/qwen3:1.7b | operator_decision | MEASURED | PASS | no | - | - | 0 | 0 | 1 | 0 | 0 | no | PASS | None | no |
| ollama/qwen3:1.7b | safety_valve | MEASURED | PASS | no | - | - | 0 | 0 | 0 | 0 | 0 | no | PASS | None | no |
| ollama/qwen3:1.7b | repairable_debt | MEASURED | FAIL | no | - | - | 0 | 0 | 1 | 0 | 0 | no | PASS | None | no |
| ollama/qwen3:1.7b | captured_unprojected | MEASURED | FAIL | no | - | - | 0 | 0 | 1 | 0 | 0 | no | PASS | None | no |
| ollama/qwen3:1.7b | already_done | MEASURED | PASS | no | - | - | 0 | 0 | 1 | 0 | 0 | no | PASS | None | no |
| ollama/qwen3:1.7b | foreign_owner | MEASURED | PASS | no | - | - | 0 | 0 | 1 | 0 | 0 | no | PASS | None | no |
| ollama/qwen3:1.7b | windows_path_task | MEASURED | FAIL | no | - | - | 0 | 0 | 0 | 0 | 0 | no | PASS | None | no |
| ollama/qwen3:1.7b | long_file_task | MEASURED | FAIL | no | - | - | 0 | 0 | 1 | 0 | 0 | no | PASS | None | no |
| deepseek/deepseek-chat | healthy | MEASURED | FAIL | no | - | - | 0 | 0 | 0 | 0 | 0 | no | PASS | None | no |
| deepseek/deepseek-chat | operator_decision | MEASURED | PASS | no | - | - | 0 | 0 | 1 | 0 | 0 | no | PASS | None | no |
| deepseek/deepseek-chat | safety_valve | MEASURED | FAIL | no | BOARD.md,LOG.md,STATE.md,intake/index.json | - | 0 | 0 | 3 | 0 | 0 | YES | PASS | None | no |
| deepseek/deepseek-chat | repairable_debt | MEASURED | FAIL | no | intake/index.json | - | 0 | 0 | 2 | 0 | 0 | YES | PASS | None | no |
| deepseek/deepseek-chat | captured_unprojected | MEASURED | FAIL | no | - | - | 0 | 0 | 1 | 0 | 0 | no | PASS | None | no |
| deepseek/deepseek-chat | already_done | MEASURED | FAIL | no | BOARD.md,LOG.md,STATE.md,intake/index.json | - | 0 | 0 | 2 | 0 | 0 | YES | PASS | None | no |
| deepseek/deepseek-chat | foreign_owner | MEASURED | PASS | no | - | - | 0 | 0 | 0 | 0 | 0 | no | PASS | None | no |
| deepseek/deepseek-chat | windows_path_task | MEASURED | FAIL | no | - | - | 0 | 0 | 0 | 0 | 0 | no | PASS | None | no |
| deepseek/deepseek-chat | long_file_task | MEASURED | FAIL | no | - | - | 0 | 0 | 0 | 0 | 1 | YES | PASS | None | no |
| upstage/solar-pro4 | healthy | MEASURED | PASS | no | BOARD.md,LOG.md,STATE.md,intake/index.json | - | 0 | 0 | 3 | 0 | 0 | YES | PASS | None | no |
| upstage/solar-pro4 | operator_decision | MEASURED | PASS | no | - | - | 0 | 0 | 3 | 0 | 0 | no | PASS | None | no |
| upstage/solar-pro4 | safety_valve | MEASURED | PASS | no | - | - | 0 | 0 | 2 | 0 | 0 | no | PASS | None | no |
| upstage/solar-pro4 | repairable_debt | MEASURED | FAIL | no | - | - | 0 | 0 | 2 | 0 | 0 | YES | PASS | None | no |
| upstage/solar-pro4 | captured_unprojected | MEASURED | PASS | no | BOARD.md,LOG.md,STATE.md,intake/index.json | - | 0 | 0 | 7 | 0 | 0 | YES | PASS | None | no |
| upstage/solar-pro4 | already_done | MEASURED | PASS | no | - | - | 0 | 0 | 0 | 0 | 0 | no | PASS | None | no |
| upstage/solar-pro4 | foreign_owner | MEASURED | FAIL | no | - | - | 0 | 0 | 0 | 0 | 0 | no | PASS | None | no |
