<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN 指南 (中文)

听着，新手。问题很简单：你的 AI 代理记忆只有金鱼水平。

**SAIPEN** 就是一个放在项目 `.saipen/` 目录里的硬核笔记本。

**快捷键:** `cc` 继续正在运行的 Goal Mode，`sss` 在不触碰代码的情况下报告状态，`ss` 保存检查点并停止。[查看完整的 14 键快捷键地图](../saipen/RFC.md#110-command-surface)。西里尔字母的同型键也可用：`сс`、`ссс`、`аа`、`ее`、`еее`、`рр`。

## 快速开始

1. **每台机器安装一次:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **在项目中启动:**
> `saipen set`

3. **工作:**
> `saipen`

## 命令

| 命令 | 操作 |
|---|---|
| `saipen set` | 初始化记忆文件夹 `.saipen/` |
| `saipen continue` | 从笔记恢复工作 |
| `saipen stop` | 保存进度并停止 |
| `saipen status` | 读取看板和状态 |
| `saipen goal <text>` | 转向新目标 |
| `saipen clean` | 深度清理仓库 |
| `saipen translate` | 隔离的32种语言翻译构建 |
| `saipen markhunt` | 深度无上限审计 -- 只记录发现，不修复 |
| `saipen prepare` | 打包工作，交接给下一个代理 |
| `saipen ship` | 触发发布流程 |

## 须知
- 回来时发现有未提交的更改？这很正常——SAIPEN 只在 `ship` 时提交，不是每一步都提交。代理会先确认这些改动是谁的，再采取行动。
- 想让它记住真正的架构决策？把它放进 `.saipen/KNOWLEDGE/`，可以是一个 `decisions.md` 文件，也可以是编号的 `ADR-001.md` 文件。
- 这台机器没有 git 或 shell？代理会直说（`mode`、`WAIT: <category> -- <问题>`），而不是瞎猜（类别是七种之一：`manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`；它告诉什么样的回答可以解除阻塞）。
- 想要个安全网？运行 `python <saipen克隆目录>/tools/install_hook.py` 安装提交前检查。

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
