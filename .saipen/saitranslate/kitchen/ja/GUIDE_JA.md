<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN ガイド (日本語)

[TRANSLATED JA]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN**はプロジェクト内の `.saipen/` フォルダに存在するノートだ。

## クイックスタート

## コマンド

## 知っておくと良いこと
- プロジェクトに戻ったときに未コミットの変更があっても普通のことだ。SAIPENは`ship`の時にコミットする、毎ステップではない。エージェントは何かに触れる前に、それが誰の変更か確認する。
- 本物のアーキテクチャ決定を覚えさせたいなら、`.saipen/KNOWLEDGE/`に`decisions.md`か番号付き`ADR-001.md`ファイルとして置け。
- このマシンにgitやshellがないなら、エージェントは推測せず正直に言う(`mode`、`WAIT: <category> -- <質問>`) (カテゴリは7つのうちの1つ: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; どのような回答が状況を解除するかを示します)。
- 保険が欲しいか？`python <saipen-clone>/tools/install_hook.py`でコミット前チェックを導入できる。