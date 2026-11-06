#!/bin/zsh
cd -- "${0:A:h}" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  print 'Python 3.9+ is required. Install it from https://www.python.org/downloads/macos/'
  read '?Press Return to close.'
  exit 1
fi
python3 restore_sessions.py
result=$?
read '?Press Return to close.'
exit "$result"
