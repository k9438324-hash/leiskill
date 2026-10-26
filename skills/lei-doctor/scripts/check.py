"""Locate the installed editing skill and run its read-only diagnostics."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-root', type=Path)
    args = parser.parse_args()
    parents = [args.skills_root] if args.skills_root else [Path(__file__).resolve().parents[2], Path.home() / '.agents/skills', Path.home() / '.codex/skills']
    for parent in parents:
        doctor = parent / 'jj/scripts/doctor.py'
        definition = parent / 'jj/SKILL.md'
        if doctor.is_file() and definition.is_file():
            return subprocess.run([sys.executable, '-X', 'utf8', str(doctor)], check=False).returncode
    print(json.dumps(dict(ok=False, error='jj skill or doctor.py is missing; install leiskill first'), ensure_ascii=False))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
