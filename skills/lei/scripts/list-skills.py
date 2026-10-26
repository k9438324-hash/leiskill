"""Discover only catalogued skills that really exist; no network access."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def scalar(text: str, key: str) -> str:
    header = text.split('---', 2)[1] if text.startswith('---') else ''
    match = re.search(r'^\s*' + re.escape(key) + r':\s*(.+)$', header, re.M)
    if not match:
        return ''
    value = match.group(1).strip()
    return json.loads(value) if value.startswith('"') else value.strip("'")


def discover(skills_root: Path | None = None) -> dict:
    own = Path(__file__).resolve().parents[1]
    repository = own.parent.parent
    source = repository / 'catalog.json'
    if not source.is_file():
        source = own / 'references/catalog.json'
    catalog = json.loads(source.read_text(encoding='utf-8'))
    roots = [skills_root] if skills_root is not None else [own.parent, Path.home() / '.agents/skills', Path.home() / '.codex/skills']
    rows = []
    for item in catalog['skills']:
        row = dict(item, available=False, path=None, reason='not_installed')
        for parent in roots:
            path = parent / item['name'] / 'SKILL.md'
            if not path.is_file():
                continue
            text = path.read_text(encoding='utf-8')
            if scalar(text, 'name') != item['name']:
                row['reason'] = 'name_mismatch'
                continue
            if scalar(text, 'version') != catalog['version']:
                row['reason'] = 'version_mismatch'
                continue
            row.update(available=True, path=str(path), reason=None)
            break
        rows.append(row)
    return dict(version=catalog['version'], catalog=str(source), skills=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-root', type=Path, help='Inspect one explicit installation root')
    args = parser.parse_args()
    print(json.dumps(discover(args.skills_root), ensure_ascii=False, indent=2))
