<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**AIコーディングエージェントのための継続プロトコル。** プレーンなMarkdownによる永続的なプロジェクトメモリにより、チャット履歴のないコールドエージェントでも `/saipen continue` を実行すれば1分以内に作業を再開できます。再説明は不要で、どのベンダーでも、いつでも利用可能です。

**コマンド1つ。記憶喪失ゼロ。**

**ショートカット:** `cc` は有効な Goal Mode を続行し、`sss` はコードを変更せず状況を表示し、`ss` はチェックポイントを保存して停止する。[全15キーの一覧](saipen/RFC.md#110-command-surface)。キリル文字の同形キーも使える: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`。

**パッケージ用キー:** `ee`/`qq` は翻訳/Wikiの完全なパッケージを準備するだけで、統合しない。`eee`/`qqq` は ready のパッケージだけを受け取り、統合・検証・レビュー後に push する。

**返信言語。** エージェントはデフォルトで**エストニア語**で応答します — これは設定であり、気まぐれではなく、SAIPEN の中でエストニア語なのはこれだけです。変更は1か所: [`saipen/STYLE.md`](saipen/STYLE.md) 冒頭の `reply_language:` 行。`et` エストニア語、`en` 英語、`ru` ロシア語、`auto` は送ったメッセージの言語から選びます。プロトコル、コード、コミット、すべてのドキュメントはどの値でも英語のままです。

**v7.195.0** | [仕様](SPEC.md) | [ガイド](GUIDE.md) | [RFC](saipen/RFC.md) | [スタイル](saipen/STYLE.md) | [UI](saipen/UI.md) | [適合性](saipen/CONFORMANCE.md) | プレーンMarkdown | 依存関係ゼロ | MIT

```text
ユーザー  ->  /saipen continue
エージェント ->  STATEを読む ("今何をするべきか？")
エージェント ->  BOARDを読む ("どのタスクを引き継ぐか？")
エージェント ->  next_actionを読む (コマンドを実行する)
エージェント ->  作業中。
```

### プロジェクト状態 > モデルメモリ
メモリはモデルの頭の中ではなく、プロジェクト内に存在します。 `Project -> Memory -> LLM` は `Project -> SAIPEN State -> LLM` に変わります。

### 主要なプロトコルロジックと保証
- **コアステートマシン**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **ゼロプロンプト自律性**: 未完了のToDoがない場合？ 自動的に `HUNT` (バグ走査) → `ADD` (機能進化) → `HUNT` のループに移行します。質問は一切不要です。
- **明示的トリガー**: `/saipen clean` (リポジトリ清掃), `/saipen translate` (分離された `.saipen/saitranslate/` ファクトリー), `/saipen markhunt` (ドライ上限なし監査、記録のみ), `/saipen prepare` (引き継ぎ用の作業パッケージング), `/saipen validate` (適合性チェック), `/saipen goal` (自律ウェーブ実行)。 メタ/制御: `/saipen status` (読み取り専用レポート), `/saipen stop` (チェックポイント作成と停止)。完全な一覧: RFC.md § 1.10。
- **厳格な信頼性**: バッチ入力解析 (サージカルな1対1チケット), ダーティツリー採用 (未コミットの作業を削除しない), 秘密情報の伏字化 (`sk-***`)。

## SAIPENを採用しているプロジェクト
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — SAIPENメモリプロトコルとネイティブ統合された高性能プロンプト管理ツール。

## 2つのレイヤー

| レイヤー | 必須 | 目的 |
|---|---|---|
| **コア** | ✅ | 安全に作業を継続する |
| **メンテナンス** | コアの上 | タスク指定なしでソフトウェアを進化させる |

**自動化された進化。** 未完了のToDoがない場合、`/saipen` と入力: `HUNT` がバグ、死にコード、失敗テストを監査します。クリーンですか？ `ADD` が次に必要な明白な機能を構築し、検証して、再びHUNTします。製品が成熟したら -> 優雅に停止します。

**GOALモード。** `/saipen goal <要望>` はボードを転換し（古いチケットは降格されますが削除されません）、新しい目標に向けて自律的に前進します。チケット間に「継続しますか？」の問いかけはなく、VERIFY/REVIEWがスキップされることもありません。SHIPは既存のリモートへ自動プッシュします（新規リポジトリの場合は1度確認します）。目標のリリースは停止点ではありません。製品が成熟するか、ブロックされるか、実行上限（3ウェーブ / 20チケット）に達するまで、自律的なHUNT/ADDメンテナンスにそのまま移行します。

## クイックスタート

**1. マシンごとに1回インストール** -- Claude Code, Gemini, OpenCode, Aider, Antigravity に設定を注入:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. プロジェクトの開始** -- プロジェクトフォルダでエージェントを開き、次のように入力:
> `saipen set`

インストールしない場合？ エージェントに次の1行を貼り付けます:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

上記リストにないプラットフォーム（DeepSeek, Qwen, スタンドアロンOpenAIなど）の場合？
プラットフォームごとのメモは `extensions/adapters/` にあります。

## ドキュメントと仕様リンク
- **[SPEC.md](SPEC.md)** -- 正式なアーキテクチャ、設計目標、リトマス試験。
- **[RFC.md](saipen/RFC.md)** -- エージェントが実行する規範的仕様。
- **[GUIDE.md](GUIDE.md)** -- 人間向けチュートリアルおよびELI5ガイド:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- エージェントのコミュニケーションスタイルと口調の定義。
- **[UI.md](saipen/UI.md)** -- Vintage Golden UI設計ガイドライン。
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- 動作テストシナリオとバリデータルール。

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## ## スクリーンショット

<details>
<summary>クリックして展開</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff エージェントの指示" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="nomadcode での saipen set" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen スクリーンショット 2026-08-01" width="600"/>

</details>

<!-- source-digest: README.md sha256:951d8044313a6456 -->
