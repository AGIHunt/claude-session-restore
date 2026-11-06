"""Exercise installer with an isolated HOME and fake downloads; no network/app access."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='restore installer ')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.fake = self.home / 'fake-bin'
        self.fake.mkdir()
        (self.fake / 'uname').write_text('#!/bin/sh\necho Darwin\n')
        (self.fake / 'curl').write_text('''#!/bin/bash
if [ "${FAIL_DOWNLOAD:-}" = 1 ]; then exit 22; fi
while [ "$#" -gt 0 ]; do
  case "$1" in
    https://*) url="$1" ;;
    -o) shift; output="$1" ;;
  esac
  shift
done
cp "$FIXTURE_REPO/${url##*/}" "$output"
''')
        for path in self.fake.iterdir():
            path.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home),
                        PATH=str(self.fake) + ':' + os.environ['PATH'], FIXTURE_REPO=str(REPO))
        self.command = self.home / '.local/bin/claude-session-restore'

    def install(self, **env):
        return subprocess.run(['bash', str(REPO / 'install.sh')], env=dict(self.env, **env),
                              text=True, capture_output=True)

    def test_install_update_help_uninstall_and_preserve_data(self):
        rc = self.home / '.zshrc'
        rc.write_text('# existing config\n')
        self.assertEqual(self.install().returncode, 0)
        self.assertTrue(list(self.home.glob('.zshrc.before-claude-restore-*')))
        result = subprocess.run([str(self.command), '--help'], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--dry-run', result.stdout)
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(rc.read_text().count('export PATH='), 1)
        self.assertTrue(rc.read_text().startswith('# existing config'))
        backup = self.home / 'Library/Application Support/ClaudeSessionRestore/backups/keep'
        backup.mkdir(parents=True)
        result = subprocess.run([str(self.command), '--uninstall'], env=self.env, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.command.exists())
        self.assertTrue(backup.exists())

    def test_failed_download_preserves_installed_version(self):
        self.assertEqual(self.install().returncode, 0)
        script = self.home / '.local/share/claude-session-restore/restore_sessions.py'
        before = script.read_bytes()
        self.assertNotEqual(self.install(FAIL_DOWNLOAD='1').returncode, 0)
        self.assertEqual(script.read_bytes(), before)

    def test_unrelated_command_is_not_overwritten(self):
        self.command.parent.mkdir(parents=True)
        self.command.write_text('unrelated command')
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual(self.command.read_text(), 'unrelated command')


if __name__ == '__main__':
    unittest.main()
