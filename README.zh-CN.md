# Claude Session Restore

换账号后，恢复 macOS 上 **Claude Desktop 的 Code 会话列表**。

[English](README.md) · MIT 开源协议 · 只使用 Python 标准库

## 使用方法

需要 macOS、Claude Desktop 和 Python 3.9 以上版本。

1. 在 Claude 登录新账号，打开一次 **Code** 页。
2. 等正在运行的任务结束。工具会正常退出并重新打开 Claude。
3. 在 GitHub 点击 **Code → Download ZIP**，解压。
4. 双击 `Restore-Claude-Sessions.command`。

也可以在解压后的目录打开终端执行：

```sh
python3 restore_sessions.py
```

预览恢复数量，不关闭 Claude、不修改文件：

```sh
python3 restore_sessions.py --dry-run
```

如果启动器没有执行权限，运行 `chmod +x Restore-Claude-Sessions.command`。如果 macOS 阻止打开启动器，直接在终端运行上面的 Python 命令。

## 恢复逻辑

- 正常退出 Claude 后再写入，避免内存中的旧索引回写覆盖恢复结果。
- 先备份目标目录及选中的源会话，再恢复缺失索引。
- 同名索引按活动时间选取更新版本，处理 `/compact` 后指向新对话 ID 的情况；时间相同则保留目标。
- 保留目标已有的归档、星标状态，尊重目标和主来源的删除标记。
- 校验写入结果，再打开 Claude。

默认比较所有普通账号／组织目录；会话数最多的旧目录作为缺失会话的归档、删除状态来源。这只是启发式规则，不代表该账号一定最新。对话指向另外按活动时间比较。若只想从指定旧账号导入：

```sh
python3 restore_sessions.py --source-account 旧账号UUID
```

当前账号有多个组织时，必须指定：

```sh
python3 restore_sessions.py --org 目标组织UUID
```

账号及组织 UUID 可在此目录中查找：

```text
~/Library/Application Support/Claude/claude-code-sessions/<账号>/<组织>/
```

不修改 `~/.claude/projects/` 中的对话原文，不迁移登录凭据或定时任务。工具本身不联网，重新打开 Claude 后由 App 正常运行。不支持 Cowork、云端聊天、已删除的对话原文，也不保证换账号后的远程访问能力。软链账号／组织目录会被跳过。

## 备份和回滚

```text
~/Library/Application Support/ClaudeSessionRestore/backups/<时间>/
```

`target-before/` 是恢复前的目标目录，`selected-sources/` 是选中的源文件，`manifest.json` 记录目标路径与恢复计划。

回滚前完全退出 Claude，把当前目标目录移到别处保留，再把 `target-before/` 复制回清单记录的目标路径，然后重新打开 Claude。每个文件单独原子写入，整个恢复不是一次事务；中途失败时可用备份回滚。备份可能含私人信息，请勿公开上传。

## 软链能一劳永逸吗？

已接入的账号可共用目录，但全新账号／组织仍会产生新路径，需要重新建立链接。共享目录还会共享删除、归档及可能的定时任务状态。因此本工具选择可备份、可回滚的一次性恢复；没有常驻监控服务。

这是非官方工具，Claude 内部存储格式更新后可能需要适配。完整设计说明和开发测试方法见 [英文 README](README.md)。
