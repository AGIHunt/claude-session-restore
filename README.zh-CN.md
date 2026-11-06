# Claude Session Restore

换账号后，恢复 macOS 上 **Claude Desktop 的 Code 会话列表**。

[English](README.md) · MIT 开源协议 · 只使用 Python 标准库

## 使用方法

需要 macOS、Claude Desktop 和 Python 3.9 以上版本。

首次只需安装一次：

```sh
curl -fsSL https://raw.githubusercontent.com/AGIHunt/claude-session-restore/main/install.sh | bash
```

然后**新开一个终端窗口**。以后登录新 Claude 账号、打开一次 Code 页后，执行：

```sh
claude-session-restore
```

恢复前先等正在运行的任务结束，工具会退出并重新打开 Claude。安装本身不会执行恢复。如果想在当前终端立即使用，先执行一次 `export PATH="$HOME/.local/bin:$PATH"`。

```sh
claude-session-restore --dry-run     # 只预览，不修改会话
claude-session-restore --uninstall   # 卸载工具，保留历史和备份
```

再次运行安装命令即可更新。无需 sudo、手动配置 alias、克隆仓库或安装 Python 第三方依赖。需要已有 Python 3.9+；缺少时安装器会提示下载地址。

安装器下载当前 main 版本，可以先查看 [install.sh](install.sh)，也可以下载仓库后执行 `bash install.sh`。程序放在 `~/.local/share/claude-session-restore`，命令放在 `~/.local/bin`。安装器会先备份已有 `.zshrc` 和 `.bash_profile`，再补充 PATH 配置；重复安装不重复添加。其他 shell 需自行把 `~/.local/bin` 加入 PATH。卸载保留共享的 PATH 配置与全部会话备份。

### 想更短？可选 alias

在 `~/.zshrc` 加一行：

```sh
alias ccr='claude-session-restore'
```

新开终端后，输入 `ccr` 即可恢复，`ccr --dry-run` 即可预览。

### 不安装也能用

GitHub 点击 **Code → Download ZIP**，解压后双击 `Restore-Claude-Sessions.command`，或者在该目录执行 `python3 restore_sessions.py`。若启动器缺少执行权限，运行 `chmod +x Restore-Claude-Sessions.command`；若 macOS 阻止打开，直接在终端运行 Python 命令即可。

## 恢复逻辑

- 正常退出 Claude 后再写入，避免内存中的旧索引回写覆盖恢复结果。
- 先备份目标目录及选中的源会话，再恢复缺失索引。
- 同名索引按活动时间选取更新版本，处理 `/compact` 后指向新对话 ID 的情况；时间相同则保留目标。
- 保留目标已有的归档、星标状态，尊重目标和主来源的删除标记。
- 校验写入结果，再打开 Claude。

默认比较所有普通账号／组织目录；会话数最多的旧目录作为缺失会话的归档、删除状态来源。这只是启发式规则，不代表该账号一定最新。对话指向另外按活动时间比较。若只想从指定旧账号导入：

```sh
claude-session-restore --source-account 旧账号UUID
```

当前账号有多个组织时，必须指定：

```sh
claude-session-restore --org 目标组织UUID
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
