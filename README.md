# Claude Session Restore

Restore missing **Claude Desktop Code** sessions after switching accounts on macOS.

[中文说明](README.zh-CN.md) · MIT license · Python standard library only

Claude Desktop keeps Code session metadata under an account and organization directory. Signing into a different account can leave the Code sidebar empty even though local transcripts still exist. This tool restores that metadata and updates older entries to newer conversation IDs, including continuations after compaction.

## Quick start

Requires macOS, Claude Desktop, and Python 3.9 or later.

1. Sign into your new account in Claude Desktop and open the **Code** tab once.
2. Let active tasks finish. The tool will quit and reopen Claude.
3. Download this repository from **Code → Download ZIP** and unzip it, or clone it:

   ```sh
   git clone https://github.com/AGIHunt/claude-session-restore.git
   cd claude-session-restore
   ```
4. Double-click `Restore-Claude-Sessions.command` in Finder, or run:

   ```sh
   python3 restore_sessions.py
   ```

If the downloaded launcher lacks execute permission, run `chmod +x Restore-Claude-Sessions.command`. If macOS blocks opening the launcher, run the Python command in Terminal instead.

Preview without closing Claude or changing files:

```sh
python3 restore_sessions.py --dry-run
```

The launcher is portable: it uses its own directory, with no hard-coded username or installation path.

## What it does

- Identifies the current account from Claude's local configuration.
- Validates metadata, quits Claude normally, and waits for it to exit before writing. This prevents Claude from saving stale in-memory pointers over a restore.
- Backs up the target directory and every selected source session outside this repository.
- Imports missing sessions and updates existing ones only when source activity timestamps are newer. Equal timestamps keep the target.
- Preserves existing target archive/star preferences and respects deletion markers in the target and the canonical source.
- Writes and verifies JSON, then reopens Claude.

Session metadata lives at:

```text
~/Library/Application Support/Claude/claude-code-sessions/<account>/<organization>/
```

Actual conversation transcripts remain under `~/.claude/projects/`. The tool does not modify transcripts, credentials, or scheduled tasks. It makes no network requests of its own; reopening Claude lets the app behave normally.

## Source selection and limits

By default, all ordinary account/organization directories are considered. The source containing the most session files supplies archive/deletion preferences for missing target entries; this is a **heuristic**, not proof that the account is most recent. Conversation content pointers are selected separately using the newest activity timestamp across sources. Missing target entries can therefore include sessions from several accounts.

To restrict recovery to a specific old account:

```sh
python3 restore_sessions.py --source-account OLD_ACCOUNT_UUID
```

If the current account has multiple organizations, select one explicitly:

```sh
python3 restore_sessions.py --org TARGET_ORGANIZATION_UUID
```

UUIDs can be found in the local directory layout above. Symlinked account/organization directories are skipped. There is no background service or automatic account monitoring.

This is an unofficial local recovery tool, not an Anthropic product. Claude's internal storage format may change. It cannot recover transcripts that were deleted, restore cloud-only chats or Cowork sessions, or guarantee remote access under a new account. Test coverage uses synthetic fixtures; app behavior has been checked manually on macOS.

## Backups and rollback

Backups are stored at:

```text
~/Library/Application Support/ClaudeSessionRestore/backups/<timestamp>/
```

Each backup includes `target-before/`, `selected-sources/`, and `manifest.json`. The manifest records the exact target path and intended changes. Backups contain private metadata; do not upload them to issues or commits.

To roll back: fully quit Claude, move the current target directory aside (preserving any work since recovery), copy `target-before/` back to the target path recorded in the manifest, and reopen Claude. A restore is atomic per file, not across the whole directory; use the backup if interrupted halfway through. Errors leave Claude closed when necessary; inspect the error before reopening or retrying.

## Why not symlinks?

Directory symlinks can share history among already configured accounts, but every new account/organization needs another link. They also share deletion, archive, and potentially scheduled-task state. This tool uses explicit, backed-up recovery instead of linking entire account directories.

## Development

```sh
python3 -m unittest discover -s tests -v
zsh -n Restore-Claude-Sessions.command
```

Tests use temporary synthetic sessions; they never close Claude or touch real history. CI runs on macOS with Python 3.9 and 3.13. Please report bugs without including real transcripts, account UUIDs, credentials, or backups.
