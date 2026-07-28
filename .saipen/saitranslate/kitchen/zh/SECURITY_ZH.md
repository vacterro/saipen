# 安全策略

## 范围

SAIPEN 是一个规范，加上一小组本地的安装/导出脚本 (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`, `export.ps1`/`.sh`)。它不运行服务器，不收集遥测数据，也不会将任何数据传输到任何地方。脚本所做的一切都是对你已经控制的文件 (你自己电脑的 `~/.claude`, `~/.gemini`, 项目 `.saipen/` 等) 进行本地文件系统写入。

这里适用两种不同的谨慎级别，精确说明比笼统地声称安全更值得：

- **你自己的配置文件** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.aider.conf.yml`) 只能通过添加或删除带分隔符的 `SAIPEN:BEGIN`/`END` 区块来编辑，并且在首次修改之前，原始文件会被复制到 `<file>.bak`。卸载会在删除前额外写出 `<file>.uninstalled.bak`。
- **注入器创建的技能目录** (`~/.claude/skills/saipen` 等) 是 SAIPEN 拥有的副本，**不会**被备份：安装会整体覆盖它们，卸载会递归删除它们。这是有意为之的——它们只包含此仓库自身文件的副本——但如果你手动编辑了本地技能副本，这些编辑会在下次 `inject`/`uninstall` 时丢失。请将自定义内容保存在你自己的配置块或 fork 中，而不是复制的技能文件夹内。

真正值得报告安全的两种情况：
1. bootstrap 脚本对你的文件系统或 git 历史执行了超出其自身注释/README 描述范围的操作。
2. 协议本身的机密卫生规则 (RFC.md § 1.1 -- 绝不要将 API 密钥、令牌、密码写入 `STATE.md`/`BOARD.md`/`LOG.md`/`KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/`recovery/`/`logs/`) 存在真正的漏洞，导致遵循 SAIPEN 的智能体将机密泄露到已提交的文件中。最后两个是比较微妙的：恢复 (Recovery) 会将损坏的 `STATE.md` 逐字复制到 `.saipen/recovery/`，而 LOG 封存会将内容逐字移动到 `.saipen/logs/`，因此任何到达原始文件的内容都会被其全部职责即不改变内容的机制存档。

## 支持的版本

仅支持 `main` 上最新标记的发布版本。这是一个协议规范，不是一个长期运行的服务——没有 LTS 分支。

## 报告漏洞

开启一个 GitHub Issue。如果报告涉及一个真实的、当前可被利用的问题 (而不是假设)，请通过此仓库的 **Security (安全)** 选项卡 ("Report a vulnerability" 报告漏洞) 将其标记为私有/安全建议，而不是公共的 Issue，这样它就不会在修复发布之前被公开可见。

包括：哪个脚本或 RFC 规则、具体场景，以及实际发生的情况 vs. 应该发生的情况。证据标准与任何其他错误报告相同 (参见 `CONTRIBUTING.md`)。
