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

**AIコーディングエージェント用の継続プロトコル。**プロジェクトのメモリは平文で
プロジェクト内のMarkdownファイルに(`.saipen/`)保存されているので、どの互換性のあるコールドエージェントでも—
チャット履歴やセッションメモリがなくても—実行できます。`/saipen continue`読み取り、
永続化された`next_action`データを読み取り、ユーザーに再説明を求める必要なしに作業を再開できます。状態はプロジェクトに属し、特定のモデルベンダーのメモリには属しません。
再開のための1つのコマンド。平文ファイルの状態。機械検証済みの契約。

**リポジトリはプッシュされるたびに自分自身を検証します; インストール、状態、チェック、および**


アンインストールはすべてローカルです — クラウドサービスもデーモンもデータベースもありません。

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.238.0** | [仕様](SPEC.md) | [ガイド](GUIDE.md) | [コア](saipen/CORE.md) | [メンテナンス](saipen/MAINTENANCE.md) | [スタイル](saipen/STYLE.md) | [UI](saipen/UI.md) | [適合性](saipen/CONFORMANCE.md) |MIT

**ショートカット:** `cc` はコンテキストを収束まで継続し（実行中の目標があればそれを再開）、`sss` はコードを変更せず状況を表示し、`ss` はチェックポイントを保存して停止する。[全19キーの一覧](saipen/RFC.md#110-command-surface)。キリル文字の同形キーも使える: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`。 `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## 何が残っているか

ライブプロジェクトのメモリは に存在します`.saipen/`— 読むこと、差分を取ること、および
コードの隣にコミットできます。冷たいエージェントはファイルから5つの質問に答えます
単独で:

|ファイル / フィールド|回答|
|---|---|
| `STATE.md` |今何が起こっているのか？(フェーズ、アクティブチケット、運用モード、ブロッカー) |
| `BOARD.md` |どのような作業が存在する／進行中の作業は？(チケットグラフ：DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |なぜプロジェクトはこの状態に至ったのか？(アペンドオンリーイベントグラフ) |
| `KNOWLEDGE/` |セッションを越えて保持すべき耐久的なプロジェクト事実とは？|
| `next_action` (in`STATE.md`) |次のエージェントが実行すべき正確なアクションは？|

これはチェックポイント契約であり、設計の提案ではない：`saipen stop`およびすべての
チケットの状態変化はファイルを固定順序で書き込み、その結果は
バリデータによってチェックされる。ホストされたデータベースには何も保存されず、セッションが終了しても何も失われない。
セッションが終了します。

## クイックスタート

**1. マシンごとに1回だけインストール**— Claude Code, Codex, Gemini, OpenCode を教える
Aider, Antigravity、および一般的な`~/.agents/skills`リーダー(FreeBuff など):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`エージェントの指示にブロックを追加
すでに持っているファイル(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— それぞれをバックアップして`.bak`まず —
そしてプロトコルを対応するスキルフォルダにコピーします。それらの外には何もありません
パス、デーモンなし、ネットワークコールなし。</sub>

**2. プロジェクトを開始**— フォルダ内のエージェントを開き、次を入力:

> `saipen set`

**インストール不要？**任意のエージェントに1行を貼り付け:

> Read&lt;clone&gt;/saipen/BOOT.md first(cold-start kernel), then&lt;clone&gt;/saipen/INDEX.md +&lt;クローン&gt;/saipen/STYLE.md を確認し、それに従ってください。

**考えを変更しましたか？**1つのコマンドで元に戻せます:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

それはマークされたブロックを正確に削除し(ファイルの他の部分はそのままである), 保存し
a `.uninstalled.bak`コピーをまず作成し、スキルフォルダを削除します。

## なぜチャット履歴だけではダメなのでしょうか？

SAIPEN は特定の失敗を対象としています：セッションが終了した後で何も覚えていないAIコーディングエージェント
他のツールや習慣はその問題の一部をカバーしています:

|アプローチ|何に役立つか|何を含まないか|
|---|---|---|
|チャット履歴／モデルの記憶|手軽で、セットアップ不要|セッションおよびベンダーに依存し、プロジェクトに保存されないため、冷たいエージェントはこれを見たことがない|
|静的`AGENTS.md`／インストラクションファイル|持続可能な立場のルールと慣習|ライブタスクの状態を独自に表すものではない`next_action`, または回復履歴|
|問題／TODOトラッカー|タスクおよびバックログ管理|自身ではエージェントの継続セマンティクスを定義しない — 冷たいエージェントが再開時に読み取って実行しなければならないもの|
| **SAIPEN** |実行中の状態、作業キュー、イベント履歴、耐久性のある知識、および機械検証可能な継続ルール — コードの隣に plain ファイルとして保存|何もしない；その組み合わせが契約である|

違いはファイル一つだけではない。SAIPEN が再開ステップを実行するからである
機械検証可能：冷たいエージェントの最初の行動は`/saipen continue`によって
規定され、検証者によって検証され、`next_action`記憶から再構築されない。
エンジニアリングの証拠

## SAIPEN は、規範的な plain ファイルプロトコルと、失敗に向き合う実行可能なものをペアにしている。


チェック。リポジトリはプロトコル/ステートマシンの設計、Python
ツール、スキーマ駆動型のステート、回復の論理、リグレッションテスト、
マルチエージェントワークフローの境界、および仕様の規律。

- **設計された契約。** [SPEC.md](SPEC.md)はファイルバックド
継続モデルと安定したディスク上の契約を定義しています；[CORE.md](saipen/CORE.md)
および[MAINTENANCE.md](saipen/MAINTENANCE.md)は現在の規範的な動作を所有しています。
- **機械検証されたステート。**stdlib-only canonical
  [validator](tools/validate.py)reads the live
  [STATE schema](extensions/schemas/state.schema.json)and checks phase
transitions, ticket dependencies, event-graph links, cross-document
invariants, capabilities, and recovery state.
- **Failure coverage.** [CONFORMANCE.md](saipen/CONFORMANCE.md)maps
requirements to[scenario fixtures](tests/scenarios/); the
  [シナリオ実行者](tools/run_scenarios.py)は構造的なパス/フェイルケースを実行します
これには、破損した回復状態、無効な遷移、依存関係の循環、および
読み取り専用制限が含まれます。
- **リグレッション制御。** [audit_checks.py](tools/audit_checks.py)は
知られている良好なコピーを変更し、検証器のチェックが依然として赤になることを証明し、
永久に緑のチェックを証拠として扱う代わりにします。
- **実行可能層。** [saipen.py](tools/saipen.py)提供する journaled state /no_think
運用;[ブートストラップ/](bootstrap/)インストール、アンインストール、およびエクスポートを保持します
ヘルパー、オプションの /no_think[pre-commit hook インストーラー](tools/install_hook.py).
- **明示的なトレードオフ。 **コアプロトコルの状態は、ランタイムがない plain ファイルです
依存関係。Canonical validation および CLI ツールは Python を必要としますが、それ以外のものは使用しません。
その標準ライブラリが必要ない`pip`インストール。

## アーキテクチャ

3層、厳密に片方向の依存関係:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

コアはメンテナンスに依存しない: 自主進化が無効な場合、SAIPEN
はまだ完全な継続プロトコルである — 冷たいエージェントはまだ再開する。

- **コア状態機械** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **自主メンテナンス**— ボードが停止中(で動作可能なものは何も`## TODO`,
何も`## DOING`)そして`BLOCKED`? 自動遷移`HUNT` (バグスキャン)
  → `ADD` (機能の進化) → `HUNT`, 質問なし。セッションが座っている
  `BLOCKED`は自動的に狩りを行わない
  ([メンテナンス § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **ゴールモード** — `/saipen goal <objective>`はボードを回転させ、
目標をVERIFY/REVIEWを通して進行させ、自律的なメンテナンスに陥る
まで、または実行が上限に達するまで(3波 / 20チケット,
その後チェックポイントを設定し、報告する) ([メンテナンス § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **強化**— バッチ入力は外科的な1つずつのチケットに解析される
  (CORE § 1.8); 未確定の作業を保持する dirty-tree の継続(CORE § 1.5);
秘密のような値はログから削除される(`sk-***`) (CORE § 1.2).

## 一般的なコマンド

日常的なエントリポイント; 現在の完全な表面はここに存在する
[Core § 1.10](saipen/CORE.md#110-command-surface).

|コマンド|実行|
|---|---|
| `/saipen set` |プロジェクトを採用: 作成`.saipen/`状態|
| `/saipen continue` |永続化されたプロジェクト状態から再開 — 再ブリーフは不要|
| `/saipen plan` |リクエストまたは未加工のバックログをチケットに変換|
| `/saipen goal <text>` |新しい目標に対して自律的な波の実行|
| `/saipen validate` |適合性チェックを実行|
| `/saipen status` |読み取り専用レポート: フェーズ、チケット、ブロッカー、陳腐化|
| `/saipen stop` |チェックポイントを設定し、停止|

<details>
<summary><b>More commands</b></summary>

|コマンド|実行|
|---|---|
| `/saipen hunt` |欠陥/改善のスイープを今すぐ強制的に実行|
| `/saipen markhunt` |乾いた、上限なしの監査 — 発見事項を記録し、修正は行わない|
| `/saipen ship` |リリースゲート; 許可されたときにコミット、タグ、プッシュ|
| `/saipen clean` |ボードおよび状態のスクラップ|
| `/saipen translate` |孤立した翻訳ファクトリー|
| `/saipen prepare` / `/saipen collect` |手渡し用のパッケージ作業 / 既存のパッケージを統合|
| `/saipen test` |宣言されたテストスイートを実行し、結果のみを報告|
| `/saipen crew` |固定順序のクルー回路(hunt → reproduce → intake → build → translate → document → ship) |
| `/saipen improve` |プロトコル改善のメタコントロール監査|
| `/saipen sub ...` |読み取り専用のサブエージェントを生成/採用|

**パッケージキー。** `ee`/`qq`統合せずに完全な翻訳/ウィキパッケージを準備
integrating;`eee`/`qqq`準備されたパッケージのみを受け入れ、その後統合、検証、
レビュー、およびプッシュ。

**saicrew。** `sc` / `saipen crew` (`extensions/subs/crew.md`)は全体を歩く
組み込みのクルーは固定順序で — センサー(saihunt, saitest, saipython, saiui),
プロデューサー(saitranslate, saiwiki)および Core を唯一のメインツリー書き手として —
次の新しいパスが実際に変更すべきものがないまで。それは正確に1つ
独自のメカニズムを追加する：耐久性のあるオーケストレーションターゲット(`execution_intent:
収束` with `converge_target: crew`)回路を再開可能にし、
証拠からクラッシュを導出可能にします。`saipen crew --dry-run --json`は、
回路を読み取り専用にします;`bootstrap/saipen_crew.*`は、オプションの手動
マルチウィンドウヘルパーであり、決して`saipen crew`を意味しません。 See
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## SAIPENが何ではないか

- **LLMやモデル**— それは、エージェントが従うプロトコルであり、知能ではありません。
- **IDEやホストされたメモリデータベース**— 状態はプロジェクト内の通常のファイルです;
何もホスティングされていません。
- **Gitの代替**— Gitはまだバージョン履歴を保持しています; コミットしてください
  `.saipen/`他のコードのように。
- **分散型コンセンサス**— 以下の並行性境界をご覧ください。
- **LLMが正しいエンジニアリング決定を行うことを保証するもの**— それは
コンテキストの損失と行動の偏りを減らします; それは確率的なエージェントを不敗にしません。
SAIPENの役割は、継続/状態契約に加えて検証とツールの提供です —


次のエージェントに機械でチェックされた開始点を渡し、魔法ではなくする。

**並行性の境界。**ジャーナル化された状態変更(SAIOPS)を使用する
プロジェクトスコープのOSロックと回復ジャーナル([OPS § 5](saipen/OPS.md#5-locks)).
通常のプロジェクト編集および接続されていないライターはそのロックの外側にある。SAIPEN
分散コンセンサスではないため、接続されていないライターは外部の
調整([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## エコシステム

|プロジェクト|SAIPEN との関係|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |SAIPEN プロジェクトのローカル Windows コントロールセンター — 自動で検出`.saipen/`ワークスペースを視覚化し、ライブ状態と適合判定を表示し、チケットを管理し、AI CLI を起動します。補助ツールであり、権威ではありません。|
| [SAIWORK](https://github.com/vacterro/saiwork) |SAIPEN を統合した下流の CodeNomad フォーク: OpenCode の起動に注入`BOOT.md`/`STYLE.md`SAIPEN のショートカットとプロジェクト状態ビューを公開し、永続的なプロンプトキューを追加します。|
| [FastPrompter](https://github.com/vacterro/fastprompter) |ポータブルな Windows スクラッチパッドおよびスニペットマネージャーで、自動で検出`.saipen/`フォルダを追加し、読み取り専用の STATE/BOARD/LOG ビューアを提供します。|

## ドキュメンテーション

|文書|何であるか|
|---|---|
| [SPEC.md](SPEC.md) |正式なアーキテクチャ、設計目標、リタムステスト|
| [CORE.md](saipen/CORE.md) |規範的な継続、状態機械、コマンド契約|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |自律的なメンテナンスとGoal Mode|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |実行可能/行動要件およびバリデータルール|
| [GUIDE.md](GUIDE.md) |人間向けチュートリアル|
| [RFC.md](saipen/RFC.md) |互換性のための分割された規範文書へのリダイレクト|
| [STYLE.md](saipen/STYLE.md) |エージェントの通信スタイルと声|
| [UI.md](saipen/UI.md) |ヴィンテージゴールデンUIデザインガイドライン|
|パンフレット|プレゼンテーションパンフレット —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [英語](guides/GUIDE_EN.md) · 🇪🇪 [エストニア語](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [ドイツ語](guides/GUIDE_DE.md) · 🇫🇷 [フランス語](guides/GUIDE_FR.md) · 🇪🇸 [スペイン語](guides/GUIDE_ES.md) · 🇮🇹 [イタリア語](guides/GUIDE_IT.md)

🇵🇹 [ポルトガル語](guides/GUIDE_PT.md) · 🇳🇱 [オランダ語](guides/GUIDE_NL.md) · 🇵🇱 [ポーランド語](guides/GUIDE_PL.md) · 🇸🇪 [スウェーデン語](guides/GUIDE_SV.md) · 🇩🇰 [デンマーク語](guides/GUIDE_DA.md)

🇫🇮 [フィンランド語](guides/GUIDE_FI.md) · 🇳🇴 [ノルウェー語](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [ベトナム語](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [トルコ語](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [インドネシア語](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [チェコ語](guides/GUIDE_CS.md) · 🇷🇴 [ルーマニア語](guides/GUIDE_RO.md) · 🇭🇺 [ハンガリー語](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [スロバキア語](guides/GUIDE_SK.md) · 🇭🇷 [クロアチア語](guides/GUIDE_HR.md)

</details>

## 設定に関するメモ

**返信言語。**エージェントはデフォルトで**エストニア語**で応答します — これは
設定であり、プロトコルの要件ではなく、SAIPENの他の部分はエストニア語ではありません。
プロトコル、コード、コミット、およびすべてのドキュメントはすべての
値において英語のままです。変更するには1か所だけ:`reply_language:`ファイルの先頭の
[`saipen/STYLE.md`](saipen/STYLE.md). `et`エストニア語、`en`英語、`ru`ロシア語、
`auto`はあなたが送ったメッセージから選択します。

**アダプター。**プラットフォームがインジェクターでカバーされていない(DeepSeek, Qwen, standalone
OpenAIなど)? プラットフォームごとのノートは にライブで存在する`extensions/adapters/`.

## スクリーンショット

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
