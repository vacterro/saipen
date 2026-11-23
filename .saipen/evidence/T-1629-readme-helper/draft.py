"""Prepare the queued documentation change outside the frozen project tree."""

import hashlib
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
scratch = Path(tempfile.mkdtemp(prefix="saipen-t1629-docs-", dir=r"V:\_TEMP_"))
changes = {
    "README.md": [(
        "The repository validates itself on every push; install, state, checks, and\n"
        "uninstall are all local — no cloud service, no daemon, no database.",
        "The repository validates itself on every push; install, state, checks, and\n"
        "uninstall are local, with no cloud service or database. Claude Code starts a\n"
        "local helper on demand at the first prompt; it exits when idle and no host is running.",
    ), (
        "Requires **Git, Python 3.11 or newer**, and a coding agent. No `pip` install,\n"
        "account, server, or daemon is needed. Keep the clone until you uninstall;",
        "Requires **Git, Python 3.11 or newer**, and a coding agent. No `pip` install,\n"
        "account, or manual service setup is needed. Keep the clone until you uninstall;",
    )],
    "README.ee.md": [(
        "Repo valideerib ise iga pushiga; install, olek, kontrollid ja\n"
        "eemaldamine on kohaline — ei ole ühtegi pilveteenust, ei daemoni, ei andmebaasi.",
        "Repo valideerib ennast iga pushiga; install, olek, kontrollid ja eemaldamine\n"
        "on kohalikud, ilma pilveteenuse ja andmebaasita. Claude Code käivitab esimese\n"
        "päringu juures vajadusel kohaliku abiprotsessi; see lõpeb jõudeolekul, kui ükski agentirakendus enam ei tööta.",
    ), (
        "ja kopeerib protokollide failid vastavate oskustega kataloogidesse. Midagi väljaspool neid\n"
        "teed, ei deemoni, ei võrguühendusi.</sub>",
        "ja kopeerib protokollide failid vastavate oskustega kataloogidesse.\n"
        "Taustateenust pole vaja käsitsi seadistada.</sub>",
    )],
    "README.ded.md": [(
        "Репозиторий проверяет себя при каждом push; установка, состояние, проверки и\n"
        "удаление — всё локальное — никакой облачной службы, никакого демона, никакой базы данных.",
        "Репозиторий проверяет себя при каждом push; установка, состояние, проверки и\n"
        "удаление локальные, без облачной службы и базы данных. Claude Code сам запускает\n"
        "локального помощника при первом запросе; тот выходит, когда простаивает и ни один агент уже не запущен.",
    ), (
        "и копирует протокол в соответствующие папки навыков. Ничего вне этих путей, никакого демона, никаких сетевых вызовов.</sub>",
        "и копирует протокол в соответствующие папки навыков. Фоновую службу вручную настраивать не надо.</sub>",
    )],
    "README.ja.md": [(
        "アンインストールはすべてローカルです — クラウドサービスもデーモンもデータベースもありません。",
        "アンインストールはすべてローカルで、クラウドサービスやデータベースは不要です。\n"
        "Claude Code は最初のプロンプトで必要に応じてローカルの補助プロセスを自動起動し、アイドル状態で実行中のエージェントアプリがなくなると終了します。",
    ), (
        "そしてプロトコルを対応するスキルフォルダにコピーします。それらの外には何もありません\n"
        "パス、デーモンなし、ネットワークコールなし。</sub>",
        "そしてプロトコルを対応するスキルフォルダにコピーします。\n"
        "バックグラウンドサービスを手動で設定する必要はありません。</sub>",
    )],
}
manifest = {}
for name, edits in changes.items():
    original = (ROOT / name).read_bytes()
    before = HERE / "pre" / name
    before.parent.mkdir(parents=True, exist_ok=True)
    before.write_bytes(original)
    text = original.decode("utf-8").replace("\r\n", "\n")
    for old, new in edits:
        if text.count(old) != 1:
            raise SystemExit(f"baseline does not match: {name}")
        text = text.replace(old, new)
    (scratch / name).write_text(text, encoding="utf-8", newline="\n")
    manifest[name] = hashlib.sha256(original).hexdigest()
descriptor = {"scratch": str(scratch), "baseline": manifest}
(HERE / "scratch.json").write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8")
print(json.dumps(descriptor))
