from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / 'skills/jj/scripts/workbench.py'
DISCOVERY = ROOT / 'skills/lei/scripts/list-skills.py'


def run(script: Path, *args: str, env=None):
    return subprocess.run([sys.executable, '-X', 'utf8', str(script), *args], capture_output=True, text=True, encoding='utf-8', env=env)


class Contracts(unittest.TestCase):
    def test_missing_srt_stops_before_media_work(self):
        result = run(WORKBENCH, 'content-gate')
        row = json.loads(result.stdout)
        self.assertEqual(row['action'], 'request_timed_srt')
        self.assertFalse(row['media_processing_allowed'])

    def test_timed_srt_requires_user_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            srt = Path(temp) / 'input.srt'
            srt.write_text('1\n00:00:01,000 --> 00:00:04,000\n现场需要核对尺寸\n', encoding='utf-8')
            result = run(WORKBENCH, 'content-gate', '--srt', str(srt))
            row = json.loads(result.stdout)
            self.assertEqual(row['action'], 'review_srt')
            self.assertEqual(row['review_engine'], 'builtin')
            self.assertTrue(Path(row['review_script']).is_file())
            self.assertTrue(Path(row['review_reference']).is_file())
            self.assertTrue(row['await_human_confirmation'])
            self.assertFalse(row['media_processing_allowed'])
            self.assertEqual(list(Path(temp).iterdir()), [srt])

    def test_discovery_reports_real_missing_and_mismatched_skills(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
            (root / 'jj').mkdir()
            (root / 'jj/SKILL.md').write_text('---\nname: wrong\nmetadata:\n  version: ' + catalog['version'] + '\n---\n', encoding='utf-8')
            rows = json.loads(run(DISCOVERY, '--skills-root', temp).stdout)['skills']
            self.assertFalse(any(row['available'] for row in rows))
            self.assertEqual(next(row for row in rows if row['name'] == 'jj')['reason'], 'name_mismatch')
            (root / 'jj/SKILL.md').write_text('---\nname: jj\nmetadata:\n  version: 0.0.0\n---\n', encoding='utf-8')
            rows = json.loads(run(DISCOVERY, '--skills-root', temp).stdout)['skills']
            self.assertEqual(next(row for row in rows if row['name'] == 'jj')['reason'], 'version_mismatch')

    def test_repository_skills_are_discoverable(self):
        rows = json.loads(run(DISCOVERY, '--skills-root', str(ROOT / 'skills')).stdout)['skills']
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row['available'] for row in rows))

    def test_doctor_reports_missing_editing_skill(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run(ROOT / 'skills/lei-doctor/scripts/check.py', '--skills-root', temp)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)['ok'])

    def test_runtime_paths_follow_current_user_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, LOCALAPPDATA=temp, JY_USER_DATA=str(Path(temp) / 'data'), JJ_FONT_PATH=str(Path(temp) / 'font.ttf'))
            code = 'import workbench as w, os;from pathlib import Path;assert w.jianying_user_data()==Path(os.environ["JY_USER_DATA"]);assert w.DEFAULT_SUBTITLE_FONT_PATH==os.environ["JJ_FONT_PATH"]'
            env['PYTHONPATH'] = str(WORKBENCH.parent)
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_version_snapshot_and_links_remain_consistent(self):
        spec = importlib.util.spec_from_file_location('validate', ROOT / 'tools/validate.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.validate(), [])


if __name__ == '__main__':
    unittest.main()
