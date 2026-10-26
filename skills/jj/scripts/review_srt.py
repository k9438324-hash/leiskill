"""Prepare and verify an evidence-linked edit proposal from a user-supplied SRT.

This module performs text and timing checks only. Editorial choices belong to
the reviewer; approval belongs to the user. No external skills are loaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

PROTOCOL = 'leiskill-srt-review-v1'
STAMP = r'(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})'
TIMING = re.compile(r'^' + STAMP + r'\s*-->\s*' + STAMP + r'\s*$')


def seconds(parts: tuple[str, ...]) -> float:
    h, m, s, ms = map(int, parts)
    return h * 3600 + m * 60 + s + ms / 1000


def timecode(value: float) -> str:
    millis = round(value * 1000)
    h, millis = divmod(millis, 3600000)
    m, millis = divmod(millis, 60000)
    s, millis = divmod(millis, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{millis:03d}'


def read_srt(path: Path) -> tuple[str, list[dict], list[str]]:
    raw = path.read_bytes()
    text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n[ \t]*\n', text.strip())
    cues, seen, warnings = [], set(), []
    for position, block in enumerate(blocks, 1):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise ValueError(f'Invalid SRT cue at block {position}; expected an index, timing and original text')
        cue_id = int(lines[0].strip())
        if cue_id <= 0 or cue_id in seen:
            raise ValueError(f'Invalid or duplicate SRT index: {cue_id}')
        match = TIMING.fullmatch(lines[1].strip())
        if not match:
            raise ValueError(f'Invalid timing at cue {cue_id}')
        start, end = seconds(match.groups()[:4]), seconds(match.groups()[4:])
        original = '\n'.join(lines[2:])
        if start >= end or not original.strip():
            raise ValueError(f'Empty text or non-positive duration at cue {cue_id}')
        if cues and start < cues[-1]['source_start']:
            raise ValueError(f'Source times move backwards at cue {cue_id}; supply corrected SRT')
        if cues and start < cues[-1]['source_end']:
            warnings.append(f'Overlapping source cues: {cues[-1]["id"]}/{cue_id}; preserve speaker context')
        seen.add(cue_id)
        cues.append(dict(id=cue_id, source_start=start, source_end=end, source_in=timecode(start), source_out=timecode(end), text=original))
    if not cues:
        raise ValueError('SRT contains no cues')
    return hashlib.sha256(raw).hexdigest(), cues, warnings


def prepare(path: Path) -> dict:
    digest, cues, warnings = read_srt(path)
    return dict(schema_version=1, protocol=PROTOCOL, source_sha256=digest, human_approved=False,
                source_cues=cues, warnings=warnings,
                cuts=[dict(id=f'cut-{index:04d}', cue_ids=[cue['id']], decision='pending', reason='', risks=[], order=None)
                      for index, cue in enumerate(cues, 1)])


def check(path: Path, plan: dict, target: float, minimum: float, maximum: float) -> dict:
    if not isinstance(plan, dict):
        raise ValueError('Review plan must be a JSON object')
    if not all(math.isfinite(x) for x in (target, minimum, maximum)) or not 0 < minimum <= target <= maximum:
        raise ValueError('Duration must satisfy 0 < min <= target <= max')
    digest, cues, warnings = read_srt(path)
    errors, cuts, assigned, kept, cut_ids = [], [], set(), [], set()
    if plan.get('protocol') != PROTOCOL or plan.get('schema_version') != 1:
        errors.append('Unknown review protocol or schema version')
    if plan.get('source_sha256') != digest:
        errors.append('SRT changed or source fingerprint is missing; prepare and review it again')
    if plan.get('human_approved') is not False:
        errors.append('Review plans must explicitly remain unapproved; user approval is recorded separately')
    by_id = {cue['id']: cue for cue in cues}
    positions = {cue['id']: i for i, cue in enumerate(cues)}
    entries = plan.get('cuts')
    if not isinstance(entries, list) or not entries:
        errors.append('An explicit keep/drop decision is required for every source cue')
        entries = []
    for item in entries:
        if not isinstance(item, dict):
            errors.append('Each cut must be an object')
            continue
        cut_id, ids = item.get('id'), item.get('cue_ids')
        if not isinstance(cut_id, str) or not cut_id.strip() or cut_id in cut_ids:
            errors.append('Cut IDs must be nonempty and unique')
        else:
            cut_ids.add(cut_id)
        if not isinstance(ids, list) or not ids or any(type(i) is not int or i not in by_id for i in ids):
            errors.append(f'{cut_id}: cue_ids must reference existing SRT indices')
            continue
        indices = [positions[i] for i in ids]
        if indices != list(range(indices[0], indices[0] + len(indices))):
            errors.append(f'{cut_id}: each clip must reference adjacent source cues in original order')
        if len(ids) != len(set(ids)) or assigned.intersection(ids):
            errors.append(f'{cut_id}: a cue cannot be assigned more than once')
        assigned.update(ids)
        selected = [by_id[i] for i in ids]
        start, end = selected[0]['source_start'], max(row['source_end'] for row in selected)
        original = '\n'.join(row['text'] for row in selected)
        for key, expected in [('source_start', start), ('source_end', end)]:
            if key in item and (type(item[key]) not in (int, float) or not math.isfinite(item[key]) or abs(item[key] - expected) > .0005):
                errors.append(f'{cut_id}: {key} does not match original cue boundaries')
        if 'text' in item and item['text'] != original:
            errors.append(f'{cut_id}: proposed text changes original wording')
        decision = item.get('decision')
        if decision not in ('keep', 'drop'):
            errors.append(f'{cut_id}: a keep/drop decision is still missing')
        if not isinstance(item.get('reason'), str) or not item['reason'].strip():
            errors.append(f'{cut_id}: explain the editing decision')
        risks = item.get('risks')
        if not isinstance(risks, list) or any(not isinstance(risk, str) or not risk.strip() for risk in risks):
            errors.append(f'{cut_id}: risks must be a list of explicit observations (or an empty list)')
        if decision == 'keep':
            if type(item.get('order')) is not int or item['order'] < 1:
                errors.append(f'{cut_id}: kept cuts need a positive integer order')
            else:
                kept.append(dict(id=cut_id, order=item['order'], source_start=start, source_end=end))
        elif item.get('order') is not None:
            errors.append(f'{cut_id}: dropped or undecided cuts must not have a playback order')
        cuts.append(dict(id=cut_id, cue_ids=ids, source_start=start, source_end=end,
                         source_in=timecode(start), source_out=timecode(end), text=original,
                         decision=decision, reason=item.get('reason'), risks=risks, order=item.get('order')))
    if assigned != set(by_id):
        errors.append('Some source cues have no recorded keep/drop decision')
    orders = sorted(row['order'] for row in kept)
    if orders != list(range(1, len(kept) + 1)) or not kept:
        errors.append('Kept cuts must have unique consecutive playback orders starting at 1')
    chronological = sorted(kept, key=lambda row: row['source_start'])
    for previous, following in zip(chronological, chronological[1:]):
        if following['source_start'] < previous['source_end'] - .0005:
            errors.append(f'Kept source clips overlap: {previous["id"]}/{following["id"]}; combine or review them')
    duration = round(sum(row['source_end'] - row['source_start'] for row in kept), 3)
    within = minimum <= duration <= maximum
    if not within:
        warnings.append('Proposed duration is outside the requested range; report the gap instead of padding or silently changing the target')
    return dict(schema_version=1, protocol=PROTOCOL, source_sha256=digest,
                ok=not errors, errors=errors, warnings=warnings, human_approved=False,
                ready_for_confirmation=not errors and within, media_processing_allowed=False,
                duration=dict(target_seconds=target, min_seconds=minimum, max_seconds=maximum, proposed_seconds=duration, within=within), cuts=cuts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'check'):
        command = commands.add_parser(name)
        command.add_argument('--srt', type=Path, required=True)
        command.add_argument('--output', type=Path)
        if name == 'check':
            command.add_argument('--plan', type=Path, required=True)
            command.add_argument('--target-seconds', type=float, default=150)
            command.add_argument('--min-seconds', type=float, default=135)
            command.add_argument('--max-seconds', type=float, default=165)
    args = parser.parse_args()
    try:
        if args.output and (args.output.resolve() == args.srt.resolve() or (args.command == 'check' and args.output.resolve() == args.plan.resolve())):
            raise ValueError('Output must not overwrite source SRT or the review plan')
        result = prepare(args.srt) if args.command == 'prepare' else check(args.srt, json.loads(args.plan.read_text(encoding='utf-8-sig')), args.target_seconds, args.min_seconds, args.max_seconds)
        if args.output:
            # Exclusive create preserves existing reviews and user material.
            with args.output.open('x', encoding='utf-8') as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            print(json.dumps(dict(ok=result.get('ok', True), output=str(args.output), source_sha256=result['source_sha256'], cues=len(result.get('source_cues', [])), cuts=len(result['cuts']), ready_for_confirmation=result.get('ready_for_confirmation', False), media_processing_allowed=False), ensure_ascii=False))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get('ok', True) else 2
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps(dict(ok=False, error=str(exc), media_processing_allowed=False), ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
