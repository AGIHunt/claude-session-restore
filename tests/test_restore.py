import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import restore_sessions as restore


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'target'
        self.source = self.root / 'source'
        self.target.mkdir()
        self.source.mkdir()

    def session(self, folder, name='local_example.json', **values):
        data = {'cliSessionId': 'old', 'lastActivityAt': 1, 'isArchived': False}
        data.update(values)
        (folder / name).write_text(json.dumps(data))
        return data

    def plan(self):
        return restore.plan_restore(self.target, [self.source])

    def test_unstarted_session_without_cli_id(self):
        self.session(self.source, sessionId='local_example', cliSessionId=None)
        self.assertEqual(self.plan()['copied'], 1)

    def test_new_session_and_archive(self):
        self.session(self.source, isArchived=True)
        plan = self.plan()
        self.assertEqual(plan['copied'], 1)
        self.assertEqual(plan['index']['archived'], ['local_example'])
        self.assertFalse((self.target / 'local_example.json').exists())

    def test_newer_pointer_replaces_old_and_preserves_preferences(self):
        self.session(self.target, isArchived=True, isStarred=True)
        self.session(self.source, cliSessionId='after-compact', lastActivityAt=10)
        data = self.plan()['writes']['local_example.json']
        self.assertEqual(data['cliSessionId'], 'after-compact')
        self.assertTrue(data['isArchived'])
        self.assertTrue(data['isStarred'])

    def test_newer_target_is_never_downgraded(self):
        self.session(self.target, lastActivityAt=100)
        self.session(self.source, lastActivityAt=10)
        self.assertEqual(self.plan()['writes'], {})

    def test_target_and_source_tombstones(self):
        self.session(self.source)
        for folder in [self.target, self.source]:
            marker = folder / 'deleted_example'
            marker.touch()
            self.assertEqual(self.plan()['copied'], 0)
            marker.unlink()

    def test_backup_and_idempotence(self):
        self.session(self.source, lastActivityAt=10)
        original = self.session(self.target)
        (self.target / 'scheduled-tasks.json').write_text('{"untouched":true}')
        backup = restore.apply_plan(self.target, self.plan(), self.root / 'backups')
        self.assertEqual(restore.read(backup / 'target-before/local_example.json'), original)
        self.assertEqual(restore.read(self.target / 'scheduled-tasks.json'), {'untouched': True})
        self.assertEqual(self.plan()['writes'], {})

    def test_bad_json_fails_before_mutation(self):
        (self.source / 'local_broken.json').write_text('{')
        with self.assertRaises(ValueError):
            self.plan()
        self.assertEqual(list(self.target.iterdir()), [])

    def test_selects_newest_across_sources(self):
        other = self.root / 'other'
        other.mkdir()
        self.session(self.source)
        self.session(other, cliSessionId='new', lastActivityAt=30)
        plan = restore.plan_restore(self.target, [self.source, other])
        self.assertEqual(plan['writes']['local_example.json']['cliSessionId'], 'new')

    def test_ambiguous_org_requires_selection(self):
        account = '00000000-0000-4000-8000-000000000001'
        orgs = ['00000000-0000-4000-8000-000000000002',
                '00000000-0000-4000-8000-000000000003']
        (self.root / 'config.json').write_text(json.dumps({'lastKnownAccountUuid': account}))
        for org in orgs:
            (self.root / 'claude-code-sessions' / account / org).mkdir(parents=True)
        with self.assertRaises(RuntimeError):
            restore.select_target(self.root)
        self.assertEqual(restore.select_target(self.root, orgs[0]).name, orgs[0])

    def test_quit_timeout_never_proceeds(self):
        with patch.object(restore.subprocess, 'run') as run, patch.object(restore.time, 'sleep'):
            run.return_value.returncode = 0
            with self.assertRaises(RuntimeError):
                restore.quit_claude()


if __name__ == '__main__':
    unittest.main()
