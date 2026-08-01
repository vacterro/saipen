<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN ガイド (日本語)

おい新兵、問題は単純だ。AIエージェントの記憶力は金魚並みだ。昨日アーキテクチャの説明に半日費やしたのに、今日新しいチャットを開くとゼロから構築し始める。

**SAIPEN**はプロジェクト内の `.saipen/` フォルダに存在するノートだ。

**ショートカット:** `cc` は有効な Goal Mode を続行し、`sss` はコードを変更せず状態を表示し、`ss` はチェックポイントを保存して停止する。[全13キーの一覧](../saipen/RFC.md#110-command-surface)。キリル文字の `сс`、`ссс`、`аа`、`ее`、`еее`、`рр` も使える。

**パッケージ用キー:** `ee`/`qq` は翻訳/Wikiの完全なパッケージを準備するだけで、統合しない。`eee`/`qqq` は ready のパッケージだけを受け取り、統合・検証・レビュー後に push する。

## クイックスタート

1. **マシンごとに1回インストール:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **プロジェクトで開始:**
> `saipen set`

3. **作業:**
> `saipen`

## コマンド

| コマンド | アクション |
|---|---|
| `saipen set` | メモリフォルダ `.saipen/` の初期化 |
| `saipen continue` | ノートから作業を再開 |
| `saipen stop` | 進捗を保存して停止 |
| `saipen status` | ボードと状態を読み取る |
| `saipen goal <text>` | 新しい目標へピボット |
| `saipen clean` | リポジトリのディープクリーン |
| `saipen translate` | 分離された32言語の翻訳ビルド |
| `saipen markhunt` | 深く無制限の監査 -- 発見事項の記録のみ、修正はしない |
| `saipen prepare` | 次のエージェントへの引き継ぎのために作業をパッケージ化 |
| `saipen ship` | リリースフローのトリガー |

## 知っておくと良いこと
- プロジェクトに戻ったときに未コミットの変更があっても普通のことだ。SAIPENは`ship`の時にコミットする、毎ステップではない。エージェントは何かに触れる前に、それが誰の変更か確認する。
- 本物のアーキテクチャ決定を覚えさせたいなら、`.saipen/KNOWLEDGE/`に`decisions.md`か番号付き`ADR-001.md`ファイルとして置け。
- このマシンにgitやshellがないなら、エージェントは推測せず正直に言う(`mode`、`WAIT: <category> -- <質問>`) (カテゴリは7つのうちの1つ: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; どのような回答が状況を解除するかを示します)。
- 保険が欲しいか？`python <saipen-clone>/tools/install_hook.py`でコミット前チェックを導入できる。

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
