# SAIPEN 规范

## 摘要
**设计目标 #1：一个没有任何聊天历史记录的冷智能体必须能够执行 `/saipen continue` 并在不到一分钟内恢复高效工作，而无需让用户重复背景信息。**

SAIPEN 保证任何兼容的 AI 智能体都可以安全地继续任何项目而无需重新简报。它是用于工程化 AI 智能体的 ABI (应用二进制接口)——一个解决失忆问题的兼容层。无论你今天使用 Claude，明天使用 Gemini，后天使用 GPT，它们都会基于相同的项目状态运行，而不需要你重申上下文。

### 核心哲学：项目状态 > 模型记忆
记忆应该与代码放在一起，而不是存在于另一个模型的脑海中。SAIPEN 将范式从 `Project -> Memory -> LLM` 转移到了 `Project -> SAIPEN State -> LLM`。记忆属于项目本身。

SAIPEN 的核心是为 LLM 智能体提供一个可移植的、基于文件的延续协议。具体实现可以 (MAY) 有所不同。磁盘上的协议契约必须 (MUST) 保持稳定。这个协议中的所有内容的存在都是为了服务于“延续性测试”。

SAIPEN 是演进式的，而非创造性的。它的目的是完成软件，而不是重新发明它。ADD (添加) 扩展了现有的设计模式、行业惯例和明显的功能对称性。

- **`STATE`**: 存在是为了回答 *"我现在该做什么？"*
- **`BOARD`**: 存在是为了回答 *"我正在接手什么任务？"*
- **`LOG`**: 存在是为了回答 *"为什么我们会走到这一步？"*
- **`KNOWLEDGE`**: 存在是为了回答 *"这个项目持久的真相是什么？"*
- **`next_action`**: SAIPEN 的心脏。它回答 *"为了恢复工作，我此时此刻确切地需要执行什么命令？"*

## SAIPEN 试金石测试

任何对协议的拟议变更或新想法必须 (MUST) 通过以下三个问题：
1. 它是否使智能体之间的过渡更可靠？
2. 它是否使不同模型的行为更统一？
3. 它是否降低了上下文丢失的可能性？

如果对这些问题中至少两个的回答是“否”，则该想法被拒绝。SAIPEN 优先考虑纪律性、可重复性和可靠性，而非新颖性。

## 架构

该协议是严格规范的。SAIPEN 在概念上分为两层：**核心 (Core)** 和 **维护 (Maintenance)**。
- **核心层** 保证了安全的、厂商中立的任务延续。
- **维护层** 是构建在核心之上的自动化软件演进模型。

在这两层之下，SAIPEN 分离了三个互不纠缠的关注点：
**正确性与延续性** (Core -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`，能力协商，检查点)，**无人值守的演进** (Maintenance -- `HUNT`/`ADD`/`CLEAN`，在纯粹的 `saipen`/`saipen continue` 默认情况下完全起作用)，以及 **吞吐量** (Goal 模式，子智能体 -- 两者都是显式选择的，见 §1.3/§2.4)。禁用 Goal 模式：协议保持不变，每次处理一个工单。禁用子智能体：`HUNT` 顺序运行这六个类别，结果相同。仅使用 Core，完全没有 Maintenance 层：协议仍然成立——冷智能体仍能正确恢复。每一层都建立在它之下的一层上，永远不会出现相反的情况；上游没有任何东西依赖于下游功能的存在。

```text
saipen/
  RFC.md                    规范性说明 (分为核心和维护两部分)
  CONFORMANCE.md             自检向量 + 场景覆盖率表
  SKILL.md                  供读取技能的平台使用的轻量级入口点
  STYLE.md                  语音风格：聊天、LOG.md、工件
  UI.md                     深金色 Win95 UI 规范 (在处理 UI 工作时强制执行)
  BOOT.md                   ~冷启动内核：裸 `continue` 所需的快速路径，
                             在上述任何内容加载之前
  phases/                   严格的状态机逻辑 -- 16 个文档，每个对应
                             RFC § 1.6 枚举值之一（由 tools/validate.py
                             双向机器检查）
    [Core Phases 核心阶段]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Maintenance Phases 维护阶段]
    hunt.md / markhunt.md / add.md / clean.md / translate.md

    [Infrastructure 基础设施]
    prepare.md              打包工作以移交给下一个智能体
    validate.md             一致性测试

extensions/                 <- 自适应层 (THE ADAPTIVE LAYER)
  adapters/                 每个模型的指令桥梁，适用于注入器无法自动检测到的平台 (README.md 指向此处)
  schemas/                  state.schema.json 被 tools/validate.py 机器读取
                             (STATE 形状的唯一真实来源)；board/log 架构仅供参考 (见 schemas/README.md)
  templates/                全新的 .saipen/ 样板文件
  security/                 示例钩子 (EXAMPLE hook)，用于复制到项目中 (RFC § 1.9，附加到 VERIFY 阶段)
  performance/              示例钩子 (EXAMPLE hook)，用于复制到项目中 (RFC § 1.9，附加到 REVIEW 阶段)
  subs/                     只读的研究子智能体示例 (RFC § 1.9) -- 每个子智能体
                             有自己的 STATE/BOARD/LOG，仅通过 OUTBOX 提供发现结果，
                             绝不作为第二条写入项目的路径

bootstrap/                  <- 安装/导出/卸载，每次一台机器
  inject.ps1 / .sh          安装 SAIPEN 块 + 技能副本 (README 快速入门)
  uninstall.ps1 / .sh       回滚注入 -- 移除块 + 技能副本
  export.ps1 / .sh          归档一个项目的 .saipen/ 用于备份
  saipen_crew.bat / .sh     打开三窗口协作布局（额外功能，extensions/subs/crew.md）

tools/                      <- 规范验证器及仓库实用工具
  validate.py               规范的一致性验证器 (stdlib Python，零安装；直接
                             根据 state.schema.json 验证 STATE，加上 shell 对
                             无法做到的图检查)
  install_hook.py           安装运行 validate.py 的 pre-commit 钩子
  uninstall_hook.py         移除该钩子 (恢复任何以前的钩子)

tests/                      <- 一致性层
  validate.ps1 / .sh        为没有 Python 的主机提供的冻结的可移植底层基础 -- 
                             新检查只在 tools/validate.py 中落地
  scenarios/                模拟状态 (崩溃恢复、所有权冲突等)
```

## 双向能力协商
智能体不仅声明它们能做什么；协议还要求必备项。
项目在其状态中定义 `requires: [filesystem, git, shell, python]`。智能体将自身主机的能力与要求进行交叉引用，并锁定为一种模式 `mode`（如，`full`，`read-only`）。

## 基于图的事件日志
SAIPEN 中的日志不是线性字符串。它们使用事件 ID (`E-001`) 构成一个无环决策图。这允许复杂的分支、智能体合并和精确的审计跟踪。

## 架构决策记录 (ADR)
瞬时的事件日志不存放永久性知识。SAIPEN 强制要求将结构性的架构决策作为 ADR 持久化（例如 `KNOWLEDGE/ADR-001-use-sqlite.md`）。

## 并发性与分布式边界
SAIPEN 通过基于文件的声明（`owner`，`claim_time`）和顺序图（`LOG.md`）确保状态完整性。然而，**SAIPEN 是一个状态协议，而不是一个分布式共识算法。**
- **本地/共享文件系统**：冲突解决依赖于原子级的文件系统写入 ("先提交者胜")。
- **网络/分布式环境**：如果智能体在没有实时文件同步的断开连接的机器之间操作，`BOARD.md` 的所有权竞争条件将会发生。在高度分布式的设置中，SAIPEN 的磁盘协议契约必须保持稳定——项目状态本身仍然不断发生突变，那是通过 SAIPEN 自己的规则 (§ 1.5 检查点) 进行的，绝不是协议形状本身遵循这些规则。


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
