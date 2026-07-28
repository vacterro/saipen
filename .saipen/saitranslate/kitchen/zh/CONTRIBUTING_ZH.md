# 贡献于 SAIPEN

SAIPEN 首先是一个规范，其次才是一个实现。大多数的贡献是对 `saipen/RFC.md`、`phases/*.md` 文件或 `tests/` 中的一致性工具进行更改，而不是应用程序代码。

## 在提出变更之前

使用 [SAIPEN 试金石测试](SPEC.md#the-saipen-litmus-test) 评估你的想法：
1. 它是否使智能体之间的过渡更可靠？
2. 它是否使不同模型的行为更统一？
3. 它是否降低了上下文丢失的可能性？

如果对其中至少两个问题的回答是“否”，则无论它在其他地方可能多么有用，都超出了此协议的范围。

## 报告差距

开启一个 Issue，描述：
- 差距在哪个文件/部分 (RFC.md，一个阶段文档，一个 schema，一个测试)
- 具体的证据 (一句话引用，一个命令及其输出，或者当前行为出错的一个场景)
- 你期望发生什么

含糊的报告 ("感觉不对劲") 很难处理，比不上一个具体的 `grep`/复现。请参阅错误报告 Issue 模板，了解这应该采取何种形式。

## 进行变更

1. 在编辑之前完整阅读 `saipen/RFC.md` 以及相关的 `phases/*.md` 文件——大多数明显的差距通常已在其他地方解决，或因为文档化的原因而被刻意地限定了范围。
2. 检查 `CHANGELOG.md` 和 `.saipen/KNOWLEDGE/decisions.md` 以获取现有的先例。不要默默地重新讨论一项已经被做出并拒绝的决策——如果你有新的证据证明过去的拒绝是错误的，请在 PR 描述中明确说明。
3. 每一个规范性变更 (MUST/MUST NOT/SHOULD) 都需要一条 `CHANGELOG.md` 记录，并在可行的情况下，提供 `tests/validate.sh` + `tests/validate.ps1` (两个平台) 的覆盖，或在 `tests/scenarios/` 下提供一个 fixture。
4. 在开启 PR 之前运行标准验证器：
   ```bash
   python tools/validate.py
   ```
   这才是最重要的验证工具——它会对照 `extensions/schemas/state.schema.json`
   检查 `STATE.md`，遍历 `LOG.md` 中已密封段的事件图，并验证运行时清单和
   注入器连接。`tests/validate.sh` / `validate.ps1` 是面向没有 Python 的
   主机的**冻结便携底线**（每个文件顶部都说明了这一点）：检查较少，保留它们
   只是为了没有 Python 的主机不至于无检验可用。如果你的更改涉及其中任何一个，
   也请运行它们，但绝不能 *代替* -- 仅通过底线测试能证明的东西远比看起来的要少。
   CI 会在每次推送和 PR 时运行标准验证器，无论其他情况如何
   (`.github/workflows/validate.yml`)。
5. 根据 `phases/ship.md` 中的方案提升 `VERSION` 版本号 (针对仅涉及文档的说明使用 patch，针对新的规范性行为使用 minor，针对破坏契约的变更使用 major)，并保持 `README.md` 中的版本徽章同步——`tests/validate.sh`/`.ps1` 会在从该仓库克隆运行时自动检查这点。

## 风格

- 协议和阶段文档：简洁，在重要的地方使用 RFC-2119 关键字，没有废话。请参阅 `saipen/STYLE.md`。
- 本文件中的所有内容、提交信息、代码注释以及 CHANGELOG：平实且专业。项目自己的聊天/LOG 声音 (`saipen/STYLE.md`) 不适用于工件。

## 超出范围的内容

- 将 SAIPEN 变成一个分布式共识系统。请参阅 `SPEC.md` 的“并发性与分布式边界”部分。
- 机器可解析的 LOG 标记语法，超出现有骨架。`LOG.md` 围绕固定的形状保持散文形式。
- 一个 `saipen doctor` 命令或类似的东西，这与 `saipen validate` + `saipen status` 重余。

这些都曾经被提出并评估过；如果想要重新讨论，需要新的证据，而不能仅仅是重新询问。
