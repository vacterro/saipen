<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN 指南 (中文)

[TRANSLATED ZH]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** 就是一个放在项目 `.saipen/` 目录里的硬核笔记本。

## 快速开始

## 命令

## 须知
- 回来时发现有未提交的更改？这很正常——SAIPEN 只在 `ship` 时提交，不是每一步都提交。代理会先确认这些改动是谁的，再采取行动。
- 想让它记住真正的架构决策？把它放进 `.saipen/KNOWLEDGE/`，可以是一个 `decisions.md` 文件，也可以是编号的 `ADR-001.md` 文件。
- 这台机器没有 git 或 shell？代理会直说（`mode`、`WAIT: <category> -- <问题>`），而不是瞎猜（类别是七种之一：`manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`；它告诉什么样的回答可以解除阻塞）。
- 想要个安全网？运行 `python <saipen克隆目录>/tools/install_hook.py` 安装提交前检查。