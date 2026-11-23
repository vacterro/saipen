# T-1464 efficiency

- rows: 50
- models: agnes/agnes-2.5-pro, deepseek/deepseek-chat, fusioncode/moonshotai/Kimi-K2.6, ollama/qwen3:1.7b, upstage/solar-pro4
- conditions: already_done, captured_unprojected, foreign_owner, healthy, long_file_task, operator_decision, repairable_debt, safety_valve, windows_path_missing, windows_path_task

| model | condition | wall_s | attempts | events_parsed | tool_calls | protocol_commands | context_bytes_stdout | context_bytes_stderr | returncode | incarnations |
|---|---|---|---|---|---|---|---|---|---|---|
| agnes/agnes-2.5-pro | healthy | 6.1 | 3 | 1 | None | 0 | 1366 | 0 | 1 | 3 |
| agnes/agnes-2.5-pro | operator_decision | 5.9 | 3 | 1 | None | 0 | 1366 | 0 | 1 | 3 |
| agnes/agnes-2.5-pro | safety_valve | 56.1 | 1 | 5 | 3 | 1 | 11909 | 0 | 1 | 1 |
| agnes/agnes-2.5-pro | repairable_debt | 5.7 | 3 | 1 | None | 0 | 1367 | 0 | 1 | 3 |
| agnes/agnes-2.5-pro | captured_unprojected | 8.6 | 3 | 1 | None | 0 | 1367 | 0 | 1 | 3 |
| agnes/agnes-2.5-pro | already_done | 8.4 | 3 | 1 | None | 0 | 1367 | 0 | 1 | 3 |
| agnes/agnes-2.5-pro | foreign_owner | 8.5 | 3 | 1 | None | 0 | 1367 | 0 | 1 | 3 |
| agnes/agnes-2.5-pro | windows_path_task | 8.4 | 3 | 1 | None | 0 | 1365 | 0 | 1 | 3 |
| agnes/agnes-2.5-pro | long_file_task | 8.6 | 3 | 0 | None | 0 | 0 | 171 | 1 | 3 |
| ollama/qwen3:1.7b | windows_path_missing | 56.7 | 1 | 22 | 8 | 0 | 10051 | 0 | 1 | 1 |
| deepseek/deepseek-chat | windows_path_missing | 11.2 | 1 | 3 | 1 | 0 | 1345 | 0 | 1 | 1 |
| upstage/solar-pro4 | windows_path_missing | 17.9 | 1 | 9 | 3 | 0 | 3867 | 0 | 1 | 1 |
| agnes/agnes-2.5-pro | windows_path_missing | 8.4 | 3 | 1 | None | 0 | 1366 | 0 | 1 | 3 |
| fusioncode/moonshotai/Kimi-K2.6 | windows_path_missing | 13.7 | 3 | 2 | None | 0 | 522 | 0 | 1 | 3 |
| fusioncode/moonshotai/Kimi-K2.6 | healthy | 11.6 | 3 | 2 | None | 0 | 522 | 0 | 1 | 3 |
| fusioncode/moonshotai/Kimi-K2.6 | operator_decision | 31.6 | 1 | 7 | 0 | 0 | 2676 | 0 | 0 | 1 |
| fusioncode/moonshotai/Kimi-K2.6 | safety_valve | 14.8 | 3 | 2 | None | 0 | 522 | 0 | 1 | 3 |
| fusioncode/moonshotai/Kimi-K2.6 | repairable_debt | 9.6 | 3 | 2 | None | 0 | 490 | 0 | 1 | 3 |
| fusioncode/moonshotai/Kimi-K2.6 | captured_unprojected | 9.0 | 3 | 2 | None | 0 | 522 | 0 | 1 | 3 |
| fusioncode/moonshotai/Kimi-K2.6 | already_done | 9.2 | 3 | 2 | None | 0 | 522 | 0 | 1 | 3 |
| fusioncode/moonshotai/Kimi-K2.6 | foreign_owner | 9.3 | 3 | 2 | None | 0 | 522 | 0 | 1 | 3 |
| fusioncode/moonshotai/Kimi-K2.6 | windows_path_task | 12.6 | 3 | 2 | None | 0 | 522 | 0 | 1 | 3 |
| fusioncode/moonshotai/Kimi-K2.6 | long_file_task | 47.9 | 3 | 0 | None | 0 | 0 | 138 | 1 | 3 |
| upstage/solar-pro4 | windows_path_task | 191.1 | 1 | 88 | 31 | 11 | 80633 | 0 | 1 | 1 |
| upstage/solar-pro4 | long_file_task | 108.6 | 1 | 0 | 9 | 3 | 0 | 5869 | 1 | 1 |
| ollama/qwen3:1.7b | healthy | 36.1 | 1 | 9 | 4 | 0 | 4075 | 0 | 1 | 1 |
| ollama/qwen3:1.7b | operator_decision | 39.2 | 1 | 9 | 3 | 0 | 4158 | 0 | 0 | 1 |
| ollama/qwen3:1.7b | safety_valve | 21.2 | 1 | 5 | 1 | 0 | 2241 | 0 | 0 | 1 |
| ollama/qwen3:1.7b | repairable_debt | 34.1 | 1 | 7 | 2 | 0 | 3048 | 0 | 1 | 1 |
| ollama/qwen3:1.7b | captured_unprojected | 32.4 | 1 | 9 | 2 | 0 | 3751 | 0 | 1 | 1 |
| ollama/qwen3:1.7b | already_done | 57.0 | 1 | 8 | 2 | 0 | 3376 | 0 | 1 | 1 |
| ollama/qwen3:1.7b | foreign_owner | 37.3 | 1 | 7 | 2 | 0 | 2975 | 0 | 1 | 1 |
| ollama/qwen3:1.7b | windows_path_task | 47.1 | 1 | 11 | 3 | 0 | 4356 | 0 | 1 | 1 |
| ollama/qwen3:1.7b | long_file_task | 32.4 | 1 | 0 | 2 | 0 | 0 | 357 | 1 | 1 |
| deepseek/deepseek-chat | healthy | 10.1 | 1 | 5 | 3 | 0 | 55061 | 0 | 1 | 1 |
| deepseek/deepseek-chat | operator_decision | 19.4 | 1 | 14 | 5 | 0 | 61028 | 0 | 0 | 1 |
| deepseek/deepseek-chat | safety_valve | 73.8 | 3 | 83 | 27 | 3 | 111859 | 0 | 1 | 3 |
| deepseek/deepseek-chat | repairable_debt | 16.5 | 2 | 11 | 3 | 1 | 5386 | 0 | 1 | 2 |
| deepseek/deepseek-chat | captured_unprojected | 15.0 | 1 | 8 | 2 | 0 | 3504 | 0 | 1 | 1 |
| deepseek/deepseek-chat | already_done | 32.9 | 1 | 32 | 10 | 2 | 37597 | 0 | 1 | 1 |
| deepseek/deepseek-chat | foreign_owner | 12.1 | 2 | 6 | 4 | 0 | 57007 | 0 | 1 | 2 |
| deepseek/deepseek-chat | windows_path_task | 11.7 | 1 | 7 | 5 | 0 | 56922 | 0 | 1 | 1 |
| deepseek/deepseek-chat | long_file_task | 12.0 | 1 | 0 | 2 | 1 | 0 | 131 | 1 | 1 |
| upstage/solar-pro4 | healthy | 44.2 | 1 | 30 | 10 | 4 | 24612 | 0 | 1 | 1 |
| upstage/solar-pro4 | operator_decision | 29.9 | 1 | 16 | 4 | 0 | 7546 | 0 | 0 | 1 |
| upstage/solar-pro4 | safety_valve | 20.7 | 1 | 11 | 3 | 0 | 5252 | 0 | 1 | 1 |
| upstage/solar-pro4 | repairable_debt | 21.6 | 1 | 11 | 3 | 1 | 11555 | 0 | 1 | 1 |
| upstage/solar-pro4 | captured_unprojected | 541.7 | 1 | 173 | 56 | 13 | 303313 | 0 | 1 | 1 |
| upstage/solar-pro4 | already_done | 17.3 | 1 | 5 | 1 | 0 | 2215 | 0 | 1 | 1 |
| upstage/solar-pro4 | foreign_owner | 20.0 | 1 | 8 | 2 | 0 | 4069 | 0 | 1 | 1 |
