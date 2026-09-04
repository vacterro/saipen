<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
</p>

<div align="center">
  <h3><a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a></h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp;
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**AI编码代理的延续协议。**项目记忆存储在普通的
项目内的Markdown文件中(`.saipen/`)，因此任何兼容的冷代理——
无需聊天历史记录，无需会话记忆——都可以运行`/saipen continue`，读取
已持久化存储的`next_action`，并继续工作而无需用户重新解释
任何内容。状态属于项目，而不是某个模型供应商的内存。

**一个命令即可恢复。普通文件状态。机器验证的合同。**

仓库在每次推送时都会验证自身；安装、状态、检查和
卸载都是本地操作 —— 没有云服务，没有守护进程，没有数据库。

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.253.0** | [规范](SPEC.md) | [指南](GUIDE.md) | [核心](saipen/CORE.md) | [维护](saipen/MAINTENANCE.md) | [风格](saipen/STYLE.md) | [用户界面](saipen/UI.md) | [一致性](saipen/CONFORMANCE.md) |MIT

**快捷键:** `cc` 继续项目上下文直至收敛（如果设置了正在运行的目标，则恢复该目标），`sss` 在不触碰代码的情况下报告状态，`ss` 保存检查点并停止。[查看完整的 19 键快捷键地图](saipen/RFC.md#110-command-surface)。西里尔字母的同型键也可用：`сс`、`ссс`、`аа`、`ее`、`еее`、`рр`。 `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

```text
Project
  |
  +-- .saipen/STATE.md ------ what is happening right now (phase, ticket, mode, next_action)
  +-- .saipen/BOARD.md ------ what work exists (DOING / TODO / DONE / BLOCKED)
  +-- .saipen/LOG.md -------- why the project reached this state (event history)
  +-- .saipen/KNOWLEDGE/ ---- what durable facts must survive sessions
          |
          v
   /saipen continue
          |
          v
      cold agent
          |
          v
     next_action -> work -> checkpoint -> next ticket
```

## 什么持续存在

实时项目内存保存在`.saipen/`——你可以读取、比较的普通文件，
并提交到代码旁边。一个冷代理从文件中回答五个问题
单独：

|文件 / 字段|答案|
|---|---|
| `STATE.md` |此刻正在发生什么？(阶段，活动工单，操作模式，阻碍因素) |
| `BOARD.md` |存在哪些工作 / 哪些是正在进行的？(工单图：进行中，待处理，已完成，被阻塞) |
| `LOG.md` |为什么项目会达到这个状态？(仅追加事件图) |
| `KNOWLEDGE/` |哪些持久化的项目事实必须在会话之间存活？|
| `next_action` (在`STATE.md`) |下一个代理应执行的确切操作是什么？|

这是一个检查点合同，而不是设计建议：`saipen stop`以及每一个
工单转换按固定顺序写入文件，并由
验证器检查。没有任何内容存储在托管数据库中，当发生时，没有任何内容会丢失
会话结束。

## 快速入门

**1. 每台机器只需安装一次**— 教授 Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, 以及任何通用的`~/.agents/skills`读取器(FreeBuff 等。):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`将块添加到代理指令
你已有的文件(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— 将每个备份到`.bak`首先 —
并把协议复制到对应的技能文件夹中。这些之外的内容不处理
路径，无守护进程，无网络调用。</sub>

**2. 启动一个项目**— 在你的文件夹中打开一个代理，输入：

> `saipen set`

**无需安装？**将一行代码粘贴到任何代理中：

> 阅读&lt;克隆&gt;/saipen/BOOT.md 首先(冷启动内核)，然后&lt;克隆&gt;/saipen/INDEX.md +&lt;克隆&gt;/saipen/STYLE.md 并遵循它们。

**改变主意了吗？**一个命令可以将其恢复：

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

它仅删除标记的代码块(而保留文件的其余部分)，保存
a `.uninstalled.bak`先复制，然后删除技能文件夹。

## 为什么不直接使用聊天历史？

SAIPEN 针对一个特定的失败：一个会话结束后就忘记一切的AI编码代理。其他工具和习惯部分解决了这个问题：
方法

||它的用途|它不携带|
|---|---|---|
|聊天记录 / 模型记忆|方便，无需设置|会话和供应商相关；不与项目一起存储，因此冷代理永远不会看到它|
|静态`AGENTS.md`/ 指令文件|持久的站立规则和惯例|本身不表示实时任务状态`next_action`, 或恢复历史|
|问题 / TODO 跟踪器|任务和待办事项管理|本身并不定义代理延续语义 —— 恢复时冷代理必须读取并执行的内容|
| **SAIPEN** |实时执行状态、工作队列、事件历史、持久知识和机器可检查的延续规则 —— 以普通文件的形式保存在代码旁边|没有；这种组合就是契约|

区别不在于任何一个文件。区别在于SAIPEN执行恢复步骤
机器可检查：冷代理在`/saipen continue`之后的第一个操作
由已保存的`next_action`并通过验证器验证，而不是
从记忆中重建。

## 工程证据

SAIPEN将规范的普通文件协议与可执行的、以失败为导向的
检查。该仓库展示了协议/状态机设计，Python
工具、模式驱动状态、恢复推理、回归测试，
多代理工作流边界和规范纪律。

- **设计的合约。** [SPEC.md](SPEC.md)定义了文件支持的
继续模型和稳定的磁盘合约；[CORE.md](saipen/CORE.md)
和[MAINTENANCE.md](saipen/MAINTENANCE.md)当前规范行为。
- **机器检查状态。**仅使用 stdlib 的规范
  [验证器](tools/validate.py)读取实时
  [状态模式](extensions/schemas/state.schema.json)并检查阶段
转换、票据依赖、事件图链接、跨文档
不变量、能力及恢复状态。
- **故障覆盖率。** [CONFORMANCE.md](saipen/CONFORMANCE.md)映射
需求到[场景固定装置](tests/scenarios/); 的
  [场景运行器](tools/run_scenarios.py)执行结构化通过/失败案例
包括损坏的恢复状态、无效转换、依赖循环和
只读限制。
- **回归控制。** [audit_checks.py](tools/audit_checks.py)修改
已知良好的副本并证明验证器的检查仍可能失败，而不是
将永久通过的检查视为证据。
- **可执行层。** [saipen.py](tools/saipen.py)提供带日志的状态
操作；[bootstrap/](bootstrap/)保存安装、卸载和导出
辅助工具，可选的[pre-commit 钩子安装器](tools/install_hook.py).
- **明确的权衡。**核心协议状态是普通的文件，没有运行时
依赖项。规范验证和 CLI 工具需要 Python，但仅使用
其标准库，不需要`pip`安装。

## 架构

三层，严格单向依赖：

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

核心不依赖维护：禁用自主演化时，SAIPEN
仍然是一个完整的延续协议 —— 冷代理仍然可以恢复。

- **核心状态机** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **自主维护**—— 板卡停止(中没有任何可操作内容`## TODO`,
中没有任何内容`## DOING`)且不`BLOCKED`? 自动转换`HUNT` (扫描错误)
  → `ADD` (演化特性) → `HUNT`, 无需提问。一个会话正在
  `BLOCKED`从不自动狩猎
  ([维护 § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **目标模式** — `/saipen goal <objective>`旋转棋盘并运行
目标通过 VERIFY/REVIEW 前进，进入自主维护
直到完成规则触发或运行达到上限(3 波 / 20 张票,
然后检查点并报告) ([维护 § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **强化**— 批量输入被解析为逐个的手术票
  (核心 § 1.8)；脏树延续保留未提交的工作(核心 § 1.5);
类似秘密的值会被从日志中抹去(`sk-***`) (核心 § 1.2).

## 常用命令

日常入口点；完整的当前表面位于
[核心 § 1.10](saipen/CORE.md#110-command-surface).

|命令|执行|
|---|---|
| `/saipen set` |采用项目：创建`.saipen/`状态|
| `/saipen continue` |从已保存的项目状态恢复 —— 不需要重新简报|
| `/saipen plan` |将请求或原始待办事项转换为工单|
| `/saipen goal <text>` |针对新目标自主执行波次|
| `/saipen validate` |运行符合性检查|
| `/saipen status` |只读报告：阶段、工单、阻碍项、陈旧性|
| `/saipen stop` |检查点并暂停|

<details>
<summary><b>More commands</b></summary>

|命令|执行|
|---|---|
| `/saipen hunt` |立即执行缺陷/改进扫描|
| `/saipen markhunt` |干运行、无上限审计 —— 记录发现内容，不进行任何修复|
| `/saipen ship` |发布门；在允许时提交、打标签并推送|
| `/saipen clean` |看板和状态清理|
| `/saipen translate` |孤立的翻译工厂|
| `/saipen prepare` / `/saipen collect` |为交接/集成准备打包工作|
| `/saipen test` |运行声明的测试套件，仅报告|
| `/saipen crew` |固定顺序的机组电路(hunt → reproduce → intake → build → translate → document → ship) |
| `/saipen improve` |对协议改进的元控制审计|
| `/saipen sub ...` |生成/采用只读子代理|

**打包密钥。** `ee`/`qq`准备完整的翻译/维基包，不进行
集成；`eee`/`qqq`仅接受已准备好的包，然后集成、验证、
审查并推送。

**saicrew。** `sc` / `saipen crew` (`extensions/subs/crew.md`)遍历整个
内置的 crew 按固定顺序执行 —— 传感器(saihunt, saitest, saipython, saiui),
生产者(saitranslate, saiwiki)以及 Core 作为唯一的主树写入者 ——
直到另一次完整的遍历没有实际内容需要更改。它添加了自己独有的机制：持久的编排目标
`execution_intent:(收敛
converge_target: crew`']}] ）; 但是根据您的要求，我将按照每项单独翻译并保持顺序的方式呈现结果，如下所示：（注意：由于原始输入中包含 JSON 数组，我将保持其结构，仅翻译内容部分）：（翻译结果）：[{` with `,)使电路可恢复的
并可从证据中推导出崩溃。`saipen crew --dry-run --json`推导出
电路只读；`bootstrap/saipen_crew.*`是一个可选的手动
多窗口辅助工具，而不是`saipen crew`所指的含义。参见
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## SAIPEN 不是什么

- **一个语言模型或模型**——它是一种代理遵循的协议，而不是智能体。
- **一个 IDE 或托管内存数据库**— 状态是项目中的普通文件；
没有任何内容被托管。
- **Git 的替代方案**— Git 仍然拥有版本历史；提交你的
  `.saipen/`像其他代码一样。
- **分布式共识**— 请参见下面的并发边界。
- **一种保证大语言模型将做出正确工程决策的保证**— 它
减少上下文丢失和行为偏移；它不会使随机代理变得无误。
SAIPEN 的工作是状态/延续合同加上验证和工具 —

— 状态是项目中的普通文件；
将下一个代理提供一个经过机器验证的起点，而不是魔法。

**并发边界。**记录状态变更(SAIOPS)使用一个
项目作用域的操作系统锁和一个恢复日志([OPS § 5](saipen/OPS.md#5-locks)).
普通的项目编辑和断开连接的写入者在该锁之外。SAIPEN
不是分布式共识，因此断开连接的写入者需要外部
协调([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## 生态系统

|项目|与 SAIPEN 的关系|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |本地 Windows 控制中心，用于 SAIPEN 项目 —— 可自动发现`.saipen/`工作区，可视化实时状态和符合性判断，管理工单，并启动 AI CLI。它是辅助工具，而非权威。|
| [SAIWORK](https://github.com/vacterro/saiwork) |下游 CodeNomad 分支，集成了 SAIPEN：注入`BOOT.md`/`STYLE.md`到 OpenCode 启动中，暴露 SAIPEN 快捷方式和项目状态视图，并添加了一个持久的提示队列。|
| [FastPrompter](https://github.com/vacterro/fastprompter) |可移植的 Windows 草稿纸和代码片段管理器，可自动检测`.saipen/`文件夹，并添加只读的 STATE/BOARD/LOG 查看器。|

## 文档

|文档|是什么|
|---|---|
| [SPEC.md](SPEC.md) |正式架构、设计目标、测试用例|
| [CORE.md](saipen/CORE.md) |规范延续、状态机和命令契约|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |自主维护和目标模式|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |可执行/行为要求和验证规则|
| [GUIDE.md](GUIDE.md) |人类教程|
| [RFC.md](saipen/RFC.md) |兼容性重定向到拆分的规范性文档|
| [STYLE.md](saipen/STYLE.md) |代理通信风格和声音|
| [UI.md](saipen/UI.md) |复古金色UI设计指南|
|宣传册|宣传册 —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [英语](guides/GUIDE_EN.md) · 🇪🇪 [爱沙尼亚语](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [德语](guides/GUIDE_DE.md) · 🇫🇷 [法语](guides/GUIDE_FR.md) · 🇪🇸 [西班牙语](guides/GUIDE_ES.md) · 🇮🇹 [意大利语](guides/GUIDE_IT.md)

🇵🇹 [葡萄牙语](guides/GUIDE_PT.md) · 🇳🇱 [荷兰语](guides/GUIDE_NL.md) · 🇵🇱 [波兰语](guides/GUIDE_PL.md) · 🇸🇪 [瑞典语](guides/GUIDE_SV.md) · 🇩🇰 [丹麦语](guides/GUIDE_DA.md)

🇫🇮 [芬兰语](guides/GUIDE_FI.md) · 🇳🇴 [挪威语](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [越南语](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [土耳其语](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [印度尼西亚语](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [捷克语](guides/GUIDE_CS.md) · 🇷🇴 [罗马尼亚语](guides/GUIDE_RO.md) · 🇭🇺 [匈牙利语](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [斯洛伐克语](guides/GUIDE_SK.md) · 🇭🇷 [克罗地亚语](guides/GUIDE_HR.md)

</details>

## 配置说明

**回复语言。**代理默认使用**爱沙尼亚语**— 这是一个
设置，而非协议要求，SAIPEN 的其他内容均不是爱沙尼亚语。
协议、代码、提交记录和每一份文档在所有
情况下都使用英语。只需在一处进行更改：`reply_language:`文件顶部的
[`saipen/STYLE.md`](saipen/STYLE.md). `et`爱沙尼亚语，`en`英语，`ru`俄语，
`auto`从你发送的消息中选取。

**适配器。**平台未被注入器覆盖(DeepSeek，Qwen，独立
OpenAI等)? 每个平台的注释位于`extensions/adapters/`.

## 截图

<details>
<summary><b>Click to expand</b></summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- translation-model: qwen3:14b contract:structured-markdown-v2 -->
<!-- source-digest: README.md sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 -->
