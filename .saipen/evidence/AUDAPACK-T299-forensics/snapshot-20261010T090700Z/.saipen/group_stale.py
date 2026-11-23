"""Print the BOARD subject of every stale-closure Work, so each one can be
scoped to the subsystem whose tests actually pin its behaviour."""
import pathlib
import re

STALE = ['T-110', 'T-111', 'T-112', 'T-129', 'T-130', 'T-131', 'T-132', 'T-133',
         'T-146', 'T-157', 'T-160', 'T-164', 'T-165', 'T-182', 'T-187', 'T-194',
         'T-195', 'T-250', 'T-31', 'T-32', 'T-33', 'T-34', 'T-38', 'T-39', 'T-40',
         'T-41', 'T-43', 'T-44', 'T-46', 'T-47', 'T-48', 'T-54', 'T-55', 'T-56',
         'T-57', 'T-58', 'T-59', 'T-60', 'T-61', 'T-62', 'T-63', 'T-64', 'T-65',
         'T-66', 'T-67', 'T-68', 'T-69', 'T-70', 'T-71', 'T-72', 'T-73', 'T-74',
         'T-75', 'T-76', 'T-77', 'T-78', 'T-79', 'T-80', 'T-81', 'T-82', 'T-83',
         'T-84', 'T-85', 'T-86', 'T-87', 'T-88', 'T-89', 'T-90', 'T-91', 'T-92',
         'T-93', 'T-94', 'T-95', 'T-96', 'T-97', 'T-98', 'T-99']

rows = {}
for line in pathlib.Path('.saipen/BOARD.md').read_text(encoding='utf-8').splitlines():
    m = re.match(r'- \[[ x]\] (T-\d+) (.*)', line)
    if m and m.group(1) in STALE:
        rows[m.group(1)] = m.group(2).split('| verify')[0].strip()

for ticket in STALE:
    print(ticket, '::', rows.get(ticket, '?? NOT ON BOARD'))