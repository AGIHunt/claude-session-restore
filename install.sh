#!/bin/bash
# Install the terminal command without sudo. Re-run to update.
set -euo pipefail

if [ "$(uname -s)" != Darwin ]; then
  echo 'Claude Session Restore currently supports macOS only.' >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
  echo 'Python 3.9+ is required: https://www.python.org/downloads/macos/' >&2
  exit 1
fi

# Use a stable per-user location; backups live separately and are never removed.
install_dir="$HOME/.local/share/claude-session-restore"
bin_dir="$HOME/.local/bin"
if [ "${1:-}" = --uninstall ]; then
  python3 - <<'PY'
from pathlib import Path
import shutil
home = Path.home()
launcher = home / '.local/bin/claude-session-restore'
if launcher.exists() and 'AGIHunt/claude-session-restore launcher' in launcher.read_text():
    launcher.unlink()
folder = home / '.local/share/claude-session-restore'
# Delete only files this installer owns, leaving unexpected files alone.
for name in ('restore_sessions.py', 'uninstall.sh'):
    (folder / name).unlink(missing_ok=True)
try:
    folder.rmdir()
except OSError:
    pass
print('Uninstalled. Session data, backups, and the shared ~/.local/bin PATH entry are preserved.')
PY
  exit 0
fi
if [ "$#" -ne 0 ]; then
  echo 'Usage: bash install.sh [--uninstall]' >&2
  exit 1
fi

stage_dir="$(mktemp -d)"
trap 'rm -rf "$stage_dir"' EXIT
base_url='https://raw.githubusercontent.com/AGIHunt/claude-session-restore/main'
curl --fail --silent --show-error --location "$base_url/restore_sessions.py" -o "$stage_dir/restore_sessions.py"
curl --fail --silent --show-error --location "$base_url/install.sh" -o "$stage_dir/uninstall.sh"
# Validate downloaded files before modifying an existing installation.
python3 - "$stage_dir/restore_sessions.py" <<'PY'
import pathlib, sys
source = pathlib.Path(sys.argv[1]).read_text()
compile(source, sys.argv[1], 'exec')
if 'def main():' not in source or 'plan_restore' not in source:
    raise SystemExit('Unexpected download; installation stopped.')
PY
bash -n "$stage_dir/uninstall.sh"
python3 - "$stage_dir" <<'PY'
from pathlib import Path
import datetime, os, shutil, sys
home = Path.home()
stage = Path(sys.argv[1])
folder = home / '.local/share/claude-session-restore'
bin_dir = home / '.local/bin'
launcher = bin_dir / 'claude-session-restore'
marker = '# AGIHunt/claude-session-restore launcher'
if launcher.is_symlink() or (launcher.exists() and marker not in launcher.read_text()):
    raise SystemExit('Refusing to overwrite an unrelated command: ' + str(launcher))
folder.mkdir(parents=True, exist_ok=True)
bin_dir.mkdir(parents=True, exist_ok=True)
for name in ('restore_sessions.py', 'uninstall.sh'):
    temp = folder / (name + '.install-tmp')
    shutil.copyfile(stage / name, temp)
    temp.replace(folder / name)
text = '''#!/bin/bash
# AGIHunt/claude-session-restore launcher
set -e
if [ "${1:-}" = "--uninstall" ]; then
  exec bash "$HOME/.local/share/claude-session-restore/uninstall.sh" --uninstall
fi
exec python3 "$HOME/.local/share/claude-session-restore/restore_sessions.py" "$@"
'''
temp = bin_dir / 'claude-session-restore.install-tmp'
temp.write_text(text)
temp.chmod(0o755)
temp.replace(launcher)
# Future default macOS zsh terminals and bash login terminals get the command.
path_line = 'export PATH="$HOME/.local/bin:$PATH"'
for name in ('.zshrc', '.bash_profile'):
    rc = home / name
    old = rc.read_text() if rc.exists() else ''
    if path_line in old:
        continue
    if rc.exists():
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        shutil.copy2(rc, rc.with_name(rc.name + '.before-claude-restore-' + stamp))
    with rc.open('a') as stream:
        stream.write('\n# User-local commands (Claude Session Restore installer)\n' + path_line + '\n')
print('Installed: ' + str(launcher))
print('Open a new terminal, then run: claude-session-restore')
print('Preview: claude-session-restore --dry-run')
print('Uninstall: claude-session-restore --uninstall')
print('Claude and your session files were not changed during installation.')
PY
