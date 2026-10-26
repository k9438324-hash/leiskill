"""Read-only environment diagnostics; does not open or change drafts."""
from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

import workbench as wb


def main() -> int:
    checks = []

    def record(name, ok, detail, required=True):
        checks.append(dict(name=name, ok=bool(ok), detail=str(detail), required=required))

    record('windows', os.name == 'nt', platform.system())
    record('python', sys.version_info >= (3, 10), platform.python_version())
    try:
        ffmpeg, ffprobe = wb.ffmpeg_paths()
        result = wb.subprocess.run([ffmpeg, '-version'], capture_output=True, timeout=15)
        record('ffmpeg', result.returncode == 0, ffmpeg)
        record('ffprobe', bool(wb.shutil.which(ffprobe) or Path(ffprobe).is_file()), ffprobe, False)
    except Exception as exc:
        record('ffmpeg', False, exc)
    try:
        wb.ensure_jianying_module()
        import pyJianYingDraft as jy
        from pyJianYingDraft.draft_codec import load_json_object_with_codec, write_json_text_with_codec
        record('pyJianYingDraft', all(hasattr(jy, key) for key in ('JianyingDraftCryptoCodec', 'DraftCryptoConfig', 'DraftFolder')), jy.__file__)
    except Exception as exc:
        record('pyJianYingDraft', False, exc)
    try:
        _, install = wb.jianying_codec()
        record('jianying_install', True, install)
    except Exception as exc:
        record('jianying_install', False, exc)
    record('jianying_user_data', wb.jianying_user_data().is_dir(), wb.jianying_user_data())
    record('subtitle_font', Path(wb.DEFAULT_SUBTITLE_FONT_PATH).is_file(), '字幕开启时需要；使用 JJ_FONT_PATH 或 manifest 指定字体', False)
    review = Path(__file__).with_name('review_srt.py')
    try:
        result = wb.subprocess.run([sys.executable, '-X', 'utf8', str(review), '--help'], capture_output=True, timeout=15)
        record('builtin_srt_review', review.is_file() and result.returncode == 0, review)
    except Exception as exc:
        record('builtin_srt_review', False, exc)
    ok = all(row['ok'] for row in checks if row['required'])
    print(json.dumps(dict(ok=ok, checks=checks, scope='environment only; draft playback and export not verified'), ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
