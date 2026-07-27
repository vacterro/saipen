<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**AI 编程 Agent 的工作连续性协议。** 采用纯 Markdown 实现持久化项目记忆，即使是没有聊天记录的全新 Agent，只需运行 `/saipen continue` 即可在几秒钟内恢复工作 —— 无需重新交代背景，适用于任何厂商、任何时间。

**一条命令，决不失忆。**

**v7.86.0** | [规范](SPEC.md) | [指南](GUIDE.md) | [RFC](saipen/RFC.md) | [风格](saipen/STYLE.md) | [UI 指南](saipen/UI.md) | [一致性](saipen/CONFORMANCE.md) | 纯 Markdown | 零依赖 | MIT 协议

[![俄语指南](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![英语指南](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![爱沙尼亚语指南](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![日语指南](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded 语音版](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
用户   ->  /saipen continue
Agent  ->  读取 STATE（“我现在应该做什么？”）
Agent  ->  读取 BOARD（“我要接手什么任务？”）
Agent  ->  读取 next_action（执行命令）
Agent  ->  开始工作。
```

### 项目状态 > 模型记忆
记忆存在于项目中，而非存在于模型的大脑里。`项目 -> 记忆 -> LLM` 变为 `项目 -> SAIPEN 状态 -> LLM`。

### 核心协议逻辑与保证
- **核心状态机**：`INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **零提示自主性**：没有未完成的待办事项？自动切换 `HUNT`（扫描 Bug）→ `ADD`（演进功能）→ `HUNT` 循环。全程无需询问任何问题。
- **显式触发指令**：`/saipen clean`（仓库清理）、`/saipen translate`（隔离的 `.saipen/saitranslate/` 工厂）、`/saipen markhunt`（不修复的无上限审计，仅记录）、`/saipen prepare`（打包工作以供交接）、`/saipen validate`（一致性检查）、`/saipen goal`（自主 Wave 执行）。元数据/控制：`/saipen status`（只读报告）、`/saipen stop`（保存检查点并暂停）。完整列表见：RFC.md § 1.10。
- **严格可靠性**：批量输入解析（精确按 1-by-1 Ticket 处理）、未提交工作区接管（绝不擦除未提交工作）、敏感信息脱敏（`sk-***`）。

## 使用 SAIPEN 的项目
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — 原生集成 SAIPEN 记忆协议的高性能 Prompt 管理工具。

## 两层架构

| 层级 | 是否必选 | 目的 |
|---|---|---|
| **核心层 (Core)** | ✅ | 安全地继续工作 |
| **维护层 (Maintenance)** | 在核心层之上 | 在无需人为安排任务的情况下演进软件 |

**自动化演进。** 当没有打开的待办事项时，输入 `/saipen`：`HUNT` 阶段将审计 Bug、废弃代码和失败的测试。如果没有问题？`ADD` 阶段构建下一个显而易见缺失的能力，进行验证，然后再次 HUNT。当产品成熟后，优雅停止。

**GOAL 模式。** `/saipen goal <你的目标>` 重置任务板（旧任务被降级，但绝不删除），并自主推进新目标 —— 任务之间不需要询问“要继续吗？”，VERIFY/REVIEW 步骤绝不跳过。SHIP 会自动 Push 到现有的远程仓库；若是全新仓库，只询问一次。发布目标并不是终点 —— 它将直接进入自主 HUNT/ADD 维护模式，直到产品成熟、遭遇阻塞或运行达到上限（3 个 Wave / 20 个 Ticket，随后创建检查点并汇报）。

## 快速开始

**1. 每台机器只需安装一次** —— 适配 Claude Code、Gemini、OpenCode、Aider、Antigravity：
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. 在项目中启动** —— 在你的项目文件夹中打开 Agent，输入：
> `saipen set`

未安装？直接将以下这行复制给任何 Agent：
> 读取 <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md 并按其要求执行。

使用的平台不在上述列表中（DeepSeek、Qwen、独立 OpenAI 等）？
针对各平台的说明位于 `extensions/adapters/` 目录中。

## 文档与规范链接
- **[SPEC.md](SPEC.md)** —— 正式架构、设计目标、试金石测试。
- **[RFC.md](saipen/RFC.md)** —— Agent 执行的规范说明。
- **[GUIDE.md](GUIDE.md)** —— 人类教程与通俗易懂 (ELI5) 指南：
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** —— Agent 通信风格与语气定义。
- **[UI.md](saipen/UI.md)** —— 深金 Windows 95 UI 设计指南。
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** —— 行为测试场景与验证器规则。

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


