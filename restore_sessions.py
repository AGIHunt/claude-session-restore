#!/usr/bin/env python3
"""Restore local Claude Desktop Code session metadata on macOS (Python 3.9+)."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import UUID

ROOT = Path.home() / 'Library/Application Support/Claude'
STATE = Path.home() / 'Library/Application Support/ClaudeSessionRestore'


def read(path):
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)


def score(data):
    return max([value for key in ('lastActivityAt', 'lastTurnEdgeAt',
                                  'latestUserFrameAt', 'createdAt')
                if isinstance(value := data.get(key), (int, float))] + [0])


def atomic_write(path, data):
    temp = path.with_name(path.name + '.restore-tmp')
    with temp.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def uuid_name(value):
    return str(UUID(value))


def directories(base):
    result = []
    for account in sorted(base.iterdir()):
        try:
            uuid_name(account.name)
        except ValueError:
            continue
        if not account.is_dir() or account.is_symlink():
            continue
        for org in sorted(account.iterdir()):
            try:
                uuid_name(org.name)
            except ValueError:
                continue
            if org.is_dir() and not org.is_symlink():
                result.append(org)
    return result


def select_target(root, org=None):
    account = uuid_name(read(root / 'config.json')['lastKnownAccountUuid'])
    candidates = [p for p in directories(root / 'claude-code-sessions')
                  if p.parent.name == account and (org is None or p.name == org)]
    if len(candidates) != 1:
        raise RuntimeError('Cannot identify one organization. Open Code after signing in, '
                           'or specify --org UUID. Symlinked directories are not supported.')
    return candidates[0]


def archive_index(directory):
    file = directory / 'archived-sessions.idx'
    data = read(file) if file.exists() else {'v': 1, 'archived': []}
    if data.get('v') != 1 or not isinstance(data.get('archived'), list):
        raise ValueError('Unsupported archive index: ' + str(file))
    return data


def plan_restore(target, sources):
    """Pure read/plan step: malformed metadata fails before any writes."""
    if not sources:
        raise RuntimeError('No source account directories found.')
    # This preference heuristic is intentionally separate from content freshness.
    canonical = max(sources, key=lambda p: len(list(p.glob('local_*.json'))))
    chosen = {}
    for directory in [canonical] + [p for p in sources if p != canonical]:
        for file in sorted(directory.glob('local_*.json')):
            data = read(file)
            if not isinstance(data, dict) or not (data.get('sessionId') or data.get('cliSessionId')):
                raise ValueError('Invalid session metadata: ' + str(file))
            if file.name not in chosen or score(data) > score(chosen[file.name][1]):
                chosen[file.name] = (file, data)
    idx = archive_index(target)
    archived = set(idx['archived'])
    canonical_archived = set(archive_index(canonical)['archived'])
    writes, origins = {}, {}
    copied = updated = skipped = 0
    for name, (source, data) in chosen.items():
        destination = target / name
        sid = Path(name).stem
        tombstone = 'deleted_' + sid[6:]
        if (target / tombstone).exists() or (canonical / tombstone).exists():
            skipped += 1
            continue
        old = read(destination) if destination.exists() else None
        if old is not None and score(old) >= score(data):
            skipped += 1
            continue
        data = dict(data)
        preferences = old
        if preferences is None:
            file = canonical / name
            preferences = read(file) if file.exists() else data
        for key in ('isArchived', 'isStarred'):
            if key in preferences:
                data[key] = preferences[key]
        if old is None:
            if sid in canonical_archived or data.get('isArchived'):
                archived.add(sid)
            copied += 1
        else:
            updated += 1
        writes[name] = data
        origins[name] = str(source)
    idx['archived'] = sorted(archived)
    return {'writes': writes, 'index': idx, 'origins': origins,
            'copied': copied, 'updated': updated, 'skipped': skipped,
            'canonical': str(canonical)}


def apply_plan(target, plan, backup_root):
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = backup_root / stamp
    backup.mkdir(parents=True, mode=0o700)
    shutil.copytree(target, backup / 'target-before')
    # Preserve every selected source, even when it is not in the canonical account.
    (backup / 'selected-sources').mkdir()
    for name, source in plan['origins'].items():
        shutil.copy2(source, backup / 'selected-sources' / name)
    atomic_write(backup / 'manifest.json', {'target': str(target), 'plan': plan})
    for name, data in plan['writes'].items():
        atomic_write(target / name, data)
        if read(target / name) != data:
            raise RuntimeError('Verification failed: ' + name)
    atomic_write(target / 'archived-sessions.idx', plan['index'])
    if read(target / 'archived-sessions.idx') != plan['index']:
        raise RuntimeError('Archive verification failed')
    return backup


def quit_claude():
    subprocess.run(['osascript', '-e', 'tell application "Claude" to quit'],
                   check=True, timeout=30)
    for _ in range(100):
        status = subprocess.run(['pgrep', '-f', '/Claude.app/Contents/MacOS/Claude'],
                                stdout=subprocess.DEVNULL).returncode
        if status == 1:
            return
        if status != 0:
            raise RuntimeError('Could not check whether Claude is running.')
        time.sleep(0.2)
    raise RuntimeError('Claude is still running. Quit it and retry; no sessions were changed.')


def run(args):
    target = select_target(ROOT, args.org)
    sources = [p for p in directories(ROOT / 'claude-code-sessions') if p != target]
    if args.source_account:
        sources = [p for p in sources if p.parent.name == args.source_account]
    # Validate before closing the app, then plan again after shutdown flushes its state.
    plan = plan_restore(target, sources)
    if args.dry_run:
        print(json.dumps({k: plan[k] for k in ('copied', 'updated', 'skipped', 'canonical')}, indent=2))
        print('Preview only. Claude and session files were not changed.')
        return
    quit_claude()
    if select_target(ROOT, args.org) != target:
        raise RuntimeError('Account changed during shutdown; stopped.')
    plan = plan_restore(target, sources)
    backup = apply_plan(target, plan, STATE / 'backups')
    print(f"Restored {plan['copied']}; updated {plan['updated']}; skipped {plan['skipped']}.")
    print('Backup:', backup)
    subprocess.run(['open', '-a', 'Claude'], check=True)
    print('Claude reopened. Open Code to check your restored sessions.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Preview without closing Claude or writing files')
    parser.add_argument('--org', type=uuid_name, help='Target organization UUID if account has multiple organizations')
    parser.add_argument('--source-account', type=uuid_name, help='Only import from this source account UUID')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('This tool supports macOS only.')
    try:
        if args.dry_run:
            run(args)
        else:
            STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (STATE / 'restore.lock').open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                run(args)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print('Restore stopped:', exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
