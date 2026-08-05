<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

<div align="center">
  <h3>🔥 <a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a> 🔥</h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp; 
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp; 
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**AIコーディングエージェントのための継続プロトコル。** SAIPENはプロジェクトのメモリをシンプルなMarkdown形式で保持します。これにより、チャット履歴のない「コールド」なエージェントでも、`/saipen continue`を実行し、`STATE.md` -> `BOARD.md` -> アクティブな`LOG.md`の末尾 -> `human_note` (設定されている場合) を読み取り、`next_action`を実行することで、1分以内に作業を再開できます。再ブリーフィング不要で、どのベンダーでも、いつでも再開可能です。

**コマンド1つ。依存関係ゼロ。記憶喪失ゼロ。**

**ショートカット:** `cc` は有効な Goal Mode を続行し、`sss` はコードを変更せず状況を表示し、`ss` はチェックポイントを保存して停止する。[全15キーの一覧](saipen/RFC.md#110-command-surface)。キリル文字の同形キーも使える: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`。

**パッケージ用キー:** `ee`/`qq` は翻訳/Wikiの完全なパッケージを準備するだけで、統合しない。`eee`/`qqq` は ready のパッケージだけを受け取り、統合・検証・レビュー後に push する。

**返信言語。** エージェントはデフォルトで**エストニア語**で応答します — これは設定であり、気まぐれではなく、SAIPEN の中でエストニア語なのはこれだけです。変更は1か所: [`saipen/STYLE.md`](saipen/STYLE.md) 冒頭の `reply_language:` 行。`et` エストニア語、`en` 英語、`ru` ロシア語、`auto` は送ったメッセージの言語から選びます。プロトコル、コード、コミット、すべてのドキュメントはどの値でも英語のままです。

**v7.174.0** | [仕様](SPEC.md) | [ガイド](GUIDE.md) | [RFC](saipen/RFC.md) | [スタイル](saipen/STYLE.md) | [UI](saipen/UI.md) | [適合性](saipen/CONFORMANCE.md) | MIT

```text
ユーザー ->  /saipen continue
エージェント ->  STATE.md を読み取る (フェーズ、タスク、next_action、モード、human_note)
エージェント ->  BOARD.md を読み取る (DOING / TODO / DONE / BLOCKED チケット)
エージェント ->  アクティブな LOG.md の末尾を読み取る (最近のイベント)
エージェント ->  human_note を読み取る (設定されている場合、1回限りの指示)
エージェント ->  next_action (コマンド) を直ちに実行する
エージェント ->  ルールが必要な場合にのみフェーズドキュメントを読み込む
エージェント ->  機能する。
```

### プロジェクトの状態 > モデルのメモリ
メモリはモデルの頭の中ではなく、プロジェクト内に存在します。`プロジェクト -> メモリ -> LLM` が `プロジェクト -> SAIPEN 状態 -> LLM` に変わります。

### プロトコルのコアロジックと保証
- **コアステートマシン**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **プロンプトなしの自律性**: ボードが停止している (実行可能な `TODO` がなく、`DOING` に何もない) **かつ `BLOCKED` でない**場合？ `HUNT` (バグのスキャン) → `ADD` (機能の進化) → `HUNT` に自動的に移行し、質問は一切しません。`BLOCKED` になっているセッションは絶対に自動ハントしません。人間がブロッカーを解決するのを待ちます (RFC § 2.1)。
- **明示的なトリガー**: `/saipen plan` (リクエストまたは生のバックログをチケットに変換する)、`/saipen ship` (バージョンのバンプ、変更ログ、タグ付け、プッシュ)、`/saipen clean` (リポジトリのスクラブ)、`/saipen translate` (分離された `.saipen/saitranslate/` ファクトリー)、`/saipen markhunt` (無制限のドライ監査、記録のみ)、`/saipen prepare` (引き継ぎのための作業パッケージ化)、`/saipen validate` (適合性チェック)、`/saipen goal` (自律的なウェーブの実行)。メタ/制御: `/saipen status` (読み取り専用レポート)、`/saipen stop` (チェックポイントと停止)。これに `saipen set` と `saipen continue` を加えたものがすべてです。12のコマンド、完全な詳細は RFC.md § 1.10 にあります。
- **厳格な信頼性**: バッチ入力の解析 (外科的な1つずつのチケット)、汚れたツリーの採用 (コミットされていない作業を決して消去しない)、シークレットの墨塗り (`sk-***`)。
- **実験的 -- saicrew**: マルチエージェントクルーを実行するためのオプションのボーナスレイヤー (`extensions/subs/`、コアの変更ゼロ) -- 1つのコアライターと、自身の `OUTBOX.md` を通じて報告する読み取り専用の `saihunt`/`saipython` ワーカー。活発なライブテスト中であり、エンドツーエンドの検証はまだ行われていません -- `extensions/subs/crew.md` を参照してください。

## SAIPENを活用するプロジェクト
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — SAIPENメモリプロトコルを中心に構築された、高性能なプロンプト管理ツール。

## 2つのレイヤー

| レイヤー | 必須 | 目的 |
|---|---|---|
| **コア** | ✅ | 安全に作業を継続する |
| **メンテナンス** | コアの上 | タスクなしでソフトウェアを進化させる |

**自動進化。** 開いているToDoが残っていない場合、`/saipen` と入力します: `HUNT` はバグ、デッドコード、失敗しているテストを監査します。クリーンですか？ `ADD` は次に見つからない明らかな機能を構築し、それを検証し、再びハントします。製品が成熟すると -> 優雅に停止します。

**GOAL (目標) モード。** `/saipen goal <望むもの>` はボードをピボットし (古いチケットは降格されますが、決して削除されません)、新しい目標を前進させます -- チケット間で「続行しますか？」と尋ねることはなく、VERIFY/REVIEW がスキップされることは決してありません。SHIP は既存のリモートに自動プッシュします。まったく新しいリポジトリは依然として1回尋ねます。目標の出荷も停止点ではありません -- 製品が成熟する、ブロックされる、または実行が上限に達する (3ウェーブ / 20チケット、その後チェックポイントとレポート) まで、自律的な HUNT/ADD メンテナンスに直接移行します。

## クイックスタート

**1. マシンごとに1回インストール** -- Claude Code、Codex、Gemini、OpenCode、Aider、Antigravity、および任意の汎用 `~/.agents/skills` リーダー (FreeBuff など) に教えます:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>これが何に触れるか、驚くことのないように: これは、すでに持っているエージェント指示ファイル (`~/.claude/CLAUDE.md`、`~/.config/opencode/AGENTS.md`、`~/.codex/AGENTS.md`、`~/.gemini/GEMINI.md`) に、マークされた `<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->` ブロックを追加し -- それぞれを最初に `.bak` にバックアップしてから -- プロトコルを一致するスキルフォルダにコピーします。これらのパスの外部には何もありません。デーモンも、ネットワーク呼び出しもありません。</sub>

**気が変わりましたか？** 1つのコマンドですべて元に戻せます:
```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```
これはマークされたブロックのみを正確に削除し (ファイルの残りの部分はそのままにします)、最初に `.uninstalled.bak` コピーを保存し、スキルフォルダを削除します。

**2. プロジェクトを開始する** -- フォルダ内でエージェントを開き、次のように入力します:
> `saipen set`

インストールしていませんか？任意のエージェントに1行貼り付けてください:
> Read <clone>/saipen/BOOT.md first (cold-start kernel), then <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

上記のリストにないプラットフォーム (DeepSeek、Qwen、スタンドアロンOpenAIなど) ですか？
プラットフォームごとのメモは `extensions/adapters/` にあります。

## ドキュメントと仕様のリンク
- **[SPEC.md](SPEC.md)** -- 正式なアーキテクチャ、設計目標、リトマス試験紙。
- **[RFC.md](saipen/RFC.md)** -- エージェントが実行する規範的仕様。
- **[GUIDE.md](GUIDE.md)** -- 人間向けのチュートリアル & ELI5 ガイド:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- エージェントのコミュニケーションスタイルと声の定義。
- **[UI.md](saipen/UI.md)** -- ヴィンテージゴールデンUIデザインガイドライン。
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- 動作テストシナリオと検証ルール。

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## スクリーンショット

<details>
<summary>クリックして展開</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff エージェントの指示" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="nomadcode での saipen set" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen スクリーンショット 2026-08-01" width="600"/>

</details>
