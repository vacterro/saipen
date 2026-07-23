<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**AIコーディングエージェントのための継続プロトコル。** プロジェクトの記憶をプレーンなマークダウンで永続化し、チャット履歴のない初期状態のエージェントでも `/saipen continue` を実行するだけで1分以内に作業を再開可能 -- 再度のブリーフィングは不要。ベンダーや日時を問わず機能します。

**コマンド1つ。記憶喪失ゼロ。**

**v7.41.0** | [仕様](SPEC.md) | [ガイド](GUIDE.md) | [RFC](saipen/RFC.md) | [スタイル](saipen/STYLE.md) | [UI](saipen/UI.md) | [適合性](saipen/CONFORMANCE.md) | プレーンマークダウン | 依存関係ゼロ | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
User  ->  /saipen continue
Agent ->  reads STATE ("今何をすべきか？")
Agent ->  reads BOARD ("どのタスクをピックアップするか？")
Agent ->  reads next_action (コマンドを実行)
Agent ->  Works.
```

### モデルの記憶よりもプロジェクトの状態
記憶はモデルの頭の中ではなく、プロジェクトに存在します。`プロジェクト -> 記憶 -> LLM` が `プロジェクト -> SAIPEN状態 -> LLM` になります。

### 主要なプロトコルのロジックと保証
- **コアステートマシン**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **プロンプト不要の自律性**: Boardが空の場合、`HUNT` (バグスキャン) → `ADD` (機能の進化) → `HUNT` のループへ自動的に移行。質問は一切しません。
- **明示的なトリガー**: `/saipen clean` (リポジトリのクリーンアップ), `/saipen translate` (独立した `.saipen/saitranslate/` ファクトリー), `/saipen validate` (適合性チェック), `/saipen goal` (自律的なウェーブの実行)。
- **厳格な信頼性**: バッチ入力の解析 (外科的な1つずつのチケット), ダーティツリーの採用 (コミットされていない作業を絶対に消去しない), シークレットの墨塗り (`sk-***`)。

## SAIPENを採用しているプロジェクト
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — SAIPENメモリプロトコルとネイティブに統合された、高性能プロンプト管理ツール。

## 2つのレイヤー

| レイヤー | 必須 | 目的 |
|---|---|---|
| **コア (Core)** | ✅ | 作業を安全に継続する |
| **保守 (Maintenance)** | コアの上で機能 | タスク指示なしでソフトウェアを進化させる |

**自動化された進化。** Boardが空の状態で `/saipen` と入力すると、`HUNT` がバグ、デッドコード、失敗しているテストを監査します。クリーンな場合、`ADD` が次に必要な明らかな機能を構築し、検証し、再び探索（hunt）します。プロダクトが成熟すると、正常に停止します。

**GOAL モード。** `/saipen goal <やりたいこと>` は、Boardをピボットし（古いチケットは降格されますが、削除されることはありません）、新しい目標を前に進めます -- チケット間で「続けてもいいですか？」という確認はなく、VERIFY/REVIEW がスキップされることもありません。SHIP は既存のリモートに自動でプッシュします。新規の空リポジトリの場合は1度だけ確認します。目標をシップしてもそれで停止するわけではありません -- そのまま自律的な HUNT/ADD の保守に移行し、プロダクトが成熟するか、ブロックされるか、実行が上限（3ウェーブ / 20チケット、その後チェックポイントとレポート作成）に達するまで続きます。

## クイックスタート

**1. マシンごとに1回インストール** -- Claude Code、Gemini、OpenCode、Aider、Antigravity に SAIPEN を学習させます:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. プロジェクトを開始する** -- プロジェクトフォルダ内でエージェントを開き、次のように入力します:
> `saipen set`

インストールしない場合？ 任意のエージェントに次の1行を貼り付けます:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

上記リストにないプラットフォーム (DeepSeek, Qwen, スタンドアロンの OpenAI など) を使用する場合？
プラットフォームごとのメモは `extensions/adapters/` にあります。

## ドキュメントと仕様のリンク
- **[SPEC.md](SPEC.md)** -- 正式なアーキテクチャ、設計目標、リトマス試験。
- **[RFC.md](saipen/RFC.md)** -- エージェントによって実行される規範的な仕様。
- **[GUIDE.md](GUIDE.md)** -- 人間向けのチュートリアル & ELI5（小学生にもわかる）ガイド:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- エージェントのコミュニケーションスタイルとボイスの定義。
- **[UI.md](saipen/UI.md)** -- ダークゴールデン Win95 UI デザインガイドライン。
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- 振る舞いのテストシナリオとバリデーターのルール。

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
