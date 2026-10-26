"""Validate leiskill's catalog, version, interfaces and local references."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def scalar(text: str, key: str) -> str:
    match = re.search(r'^\s*' + re.escape(key) + r':\s*(.+)$', text, re.M)
    if not match:
        return ''
    value = match.group(1).strip()
    return json.loads(value) if value.startswith('"') else value.strip("'")


def validate(root: Path = ROOT) -> list[str]:
    errors = []
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()
    catalog = json.loads((root / 'catalog.json').read_text(encoding='utf-8'))
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or catalog['version'] != version:
        errors.append('VERSION/catalog version mismatch')
    snapshot = json.loads((root / 'skills/lei/references/catalog.json').read_text(encoding='utf-8'))
    if snapshot != catalog:
        errors.append('installed catalog snapshot differs from canonical catalog')
    names = [row['name'] for row in catalog['skills']]
    if len(names) != len(set(names)):
        errors.append('duplicate catalog names')
    actual = sorted(path.parent.name for path in (root / 'skills').glob('*/SKILL.md'))
    if actual != sorted(names):
        errors.append('catalog differs from actual skills')
    for row in catalog['skills']:
        folder = root / 'skills' / row['name']
        text = (folder / 'SKILL.md').read_text(encoding='utf-8')
        if not text.startswith('---\n') or len(text.split('---', 2)) != 3:
            errors.append(f'{row["name"]}: missing frontmatter')
            continue
        header = text.split('---', 2)[1]
        for key, expected in [('name', row['name']), ('description', row['description']), ('version', version)]:
            if scalar(header, key) != expected:
                errors.append(f'{row["name"]}: {key} differs from catalog')
        for marker in ('lei-handoff:', row['accepts'], row['produces'], row['excludes']):
            if marker not in header:
                errors.append(f'{row["name"]}: missing handoff field {marker}')
        interface = (folder / 'agents/openai.yaml').read_text(encoding='utf-8')
        if scalar(interface, 'display_name') != row['display_name']:
            errors.append(f'{row["name"]}: display name mismatch')
        if not 25 <= len(scalar(interface, 'short_description')) <= 64:
            errors.append(f'{row["name"]}: short description must have 25-64 characters')
        if '$' + row['name'] not in scalar(interface, 'default_prompt'):
            errors.append(f'{row["name"]}: prompt lacks invocation')
        if f'skills/{row["name"]}/SKILL.md' not in (root / 'README.md').read_text(encoding='utf-8'):
            errors.append(f'{row["name"]}: missing README link')
    for file in root.rglob('*'):
        if not file.is_file() or any(part in ('.git', '__pycache__') for part in file.relative_to(root).parts):
            continue
        relative = file.relative_to(root)
        if any(part in {'evals', 'qa', 'cache', '.venv', 'node_modules'} for part in relative.parts) or file.name.startswith('.env') or file.name in {'project-state.json', 'review-metrics.jsonl'}:
            errors.append(f'non-public runtime artifact: {relative}')
        if file.suffix.lower() in {'.mp4', '.mov', '.mp3', '.wav', '.srt', '.dll', '.exe'}:
            errors.append(f'media or executable must not be published: {relative}')
        if file.suffix in {'.py', '.md', '.json', '.yaml', '.yml', '.ps1'}:
            public_text = file.read_text(encoding='utf-8')
            if re.search(r'[A-Za-z]:\\Users\\[^\\\s]+\\', public_text):
                errors.append(f'personal absolute path: {relative}')
            if re.search(r'gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', public_text):
                errors.append(f'possible credential: {relative}')
        if file.suffix == '.py':
            try:
                ast.parse(file.read_text(encoding='utf-8'), filename=str(file))
            except SyntaxError as exc:
                errors.append(str(exc))
        if file.suffix != '.md':
            continue
        text = file.read_text(encoding='utf-8')
        for destination in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
            if re.match(r'\w+://', destination) or destination.startswith('#'):
                continue
            target = unquote(destination.split('#', 1)[0].strip('<>'))
            if target and not (file.parent / target).exists():
                errors.append(f'{file.relative_to(root)}: missing link {target}')
    return errors


if __name__ == '__main__':
    try:
        errors = validate()
    except Exception as exc:
        errors = [str(exc)]
    print(json.dumps(dict(ok=not errors, errors=errors), ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))
