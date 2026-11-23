import difflib
import hashlib
import json
import re
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
helper = {
    'en': 'For Claude Code, a local helper starts on the first prompt and exits when idle with no host running.',
    'et': 'Claude Code’i esimene päring käivitab kohaliku abiprotsessi, mis sulgub, kui see on jõude ja ükski host enam ei tööta.',
    'ded': 'Первый запрос Claude Code запускает местный помощник; без работающего хоста он завершается в простое.',
    'ru': 'Первый запрос Claude Code запускает локальный вспомогательный процесс, который завершается в простое, когда ни один хост больше не работает.',
    'ja': 'Claude Codeでは最初のプロンプトでローカル補助プロセスが起動し、動作中のホストがなく、アイドル状態になると終了します。',
}
replacements = {
    'en': [
        ('uninstall are all local — no cloud service, no daemon, no database.',
         'uninstall are all local — no cloud service or database.\n' + helper['en']),
        ('account, server, or daemon is needed.', 'SAIPEN account or manually managed server is needed.'),
    ],
    'et': [
        ('eemaldamine on kohaline — ei ole ühtegi pilveteenust, ei daemoni, ei andmebaasi.',
         'eemaldamine on kohalikud — pilveteenust ega andmebaasi pole vaja.\n' + helper['et']),
        ('teed, ei deemoni, ei võrguühendusi.', 'teed, ei võrguühendusi.'),
    ],
    'ded': [
        ('удаление — всё локальное — никакой облачной службы, никакого демона, никакой базы данных.',
         'удаление — всё локальное, без облачного сервиса и базы данных.\n' + helper['ded']),
        ('Ничего вне этих путей, никакого демона, никаких сетевых вызовов.',
         'Ничего вне этих путей, никаких сетевых вызовов.'),
    ],
    'ru': [
        ('от uninstall — всё локальное — никакой облачной службы, никакого демона, никакой базы данных.',
         'удаление — всё локальное, без облачного сервиса и базы данных.\n' + helper['ru']),
        ('пути, без демона, без сетевых вызовов.', 'пути, без сетевых вызовов.'),
    ],
    'ja': [
        ('アンインストールはすべてローカルです — クラウドサービスもデーモンもデータベースもありません。',
         'アンインストールはすべてローカルで、クラウドサービスやデータベースは不要です。\n' + helper['ja']),
        ('パス、デーモンなし、ネットワークコールなし。', 'パス、ネットワークコールなし。'),
    ],
}
targets = {
    'README.md': 'en', 'README.ee.md': 'et', 'README.ded.md': 'ded', 'README.ja.md': 'ja',
    '.saipen/saitranslate/kitchen/et/README_ET.md': 'et',
    '.saipen/saitranslate/kitchen/ru/README_RU.md': 'ru',
    '.saipen/saitranslate/kitchen/ded/README_DED.md': 'ded',
    '.saipen/saitranslate/kitchen/ja/README_JA.md': 'ja',
}
baseline = {}
candidate = {}
patch = []
for relative, language in targets.items():
    original = (root / relative).read_bytes()
    text = original.decode('utf-8')
    newline = '\r\n' if b'\r\n' in original else '\n'
    after = text
    for old, new in replacements[language]:
        old = old.replace('\n', newline)
        new = new.replace('\n', newline)
        # Some kitchen mirrors already removed the quick-start daemon claim.
        count = after.count(old)
        if count == 0 and old != replacements[language][0][0]:
            continue
        if count != 1:
            raise SystemExit(f'expected one exact fragment ({count}): {relative}: {old!r}')
        after = after.replace(old, new, 1)
    assert after.count(helper[language]) == 1
    if language == 'en':
        assert after.index(helper[language]) < after.index('## Quick start')
        assert 'no daemon' not in after
        assert 'or daemon is needed' not in after
    saved = evidence / 'pre' / relative
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(original)
    target = evidence / 'candidate' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(after.encode('utf-8'))
    baseline[relative] = hashlib.sha256(original).hexdigest()
    candidate[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    patch.extend(difflib.unified_diff(text.splitlines(keepends=True), after.splitlines(keepends=True),
                                     fromfile='a/' + relative, tofile='b/' + relative))
(evidence / 'paths.json').write_text(json.dumps(list(targets), indent=2) + '\n', encoding='utf-8')
(evidence / 'baseline.json').write_text(json.dumps(baseline, indent=2) + '\n', encoding='utf-8')
(evidence / 'candidate.json').write_text(json.dumps(candidate, indent=2) + '\n', encoding='utf-8')
(evidence / 'owned-review.patch').write_text(''.join(patch), encoding='utf-8')
import sys
sys.path.insert(0, str(root / 'tools'))
from freshness import source_content_digest
new_source = (evidence / 'candidate/README.md').read_text(encoding='utf-8-sig')
freshness = {}
for relative in targets:
    if relative == 'README.md':
        continue
    before = (evidence / 'pre' / relative).read_text(encoding='utf-8-sig')
    after = (evidence / 'candidate' / relative).read_text(encoding='utf-8-sig')
    markers = re.findall(r'<!-- source-digest: README\.md sha256:([0-9a-f]+) -->', before)
    assert markers == re.findall(r'<!-- source-digest: README\.md sha256:([0-9a-f]+) -->', after)
    freshness[relative] = {'previous_marker_retained': bool(markers),
                           'whole_translation_refreshed': False}
result = {'paths': len(targets), 'bounded_statement_updated': True,
          'new_readme_digest': source_content_digest(new_source), 'locales': freshness,
          'live_source_changed': False, 'full_family': 'NOT_RUN'}
(evidence / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
