<div align="center" id="claude-code-deck">

# Claude Code Deck

专为手机 SSH 和远程终端打造的 Claude Code 会话管理器。  
用一个 `ccd` 命令，把 Claude Code 历史会话和 tmux 运行现场整理成稳定、可恢复、可命名的工作台。

[![GitHub Stars](https://img.shields.io/github/stars/WangHaowen99/claude-code-deck?style=flat-square&logo=github&color=yellow)](https://github.com/WangHaowen99/claude-code-deck/stargazers)
[![Branch](https://img.shields.io/badge/default_branch-develop-2ea44f?style=flat-square&logo=git)](https://github.com/WangHaowen99/claude-code-deck/tree/develop)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![tmux](https://img.shields.io/badge/tmux-required-1BB91F?style=flat-square)](https://github.com/tmux/tmux)
[![Claude Code](https://img.shields.io/badge/Claude_Code-supported-111111?style=flat-square)](https://docs.anthropic.com/en/docs/claude-code)

**中文** | **[English](README-EN.md)**

</div>

## 快速开始

一行安装：

```bash
curl -fsSL https://raw.githubusercontent.com/WangHaowen99/claude-code-deck/develop/install.sh | bash
```

安装后运行：

```bash
ccd
```

新建并进入一个 Claude Code 工作台：

```bash
ccd new 写论文
```

之后随时恢复：

```bash
ccd enter 写论文
```

## 为什么需要它

Claude Code 自带历史恢复，但在手机 SSH、远程服务器和长任务场景里，经常会遇到这些问题：

- SSH 断开后要重新找到正确会话
- 原始 session id 难记，也不适合在窄屏里辨认
- 多个项目或长期任务混在一起，缺少用途名
- 需要保留正在运行的 Claude Code 现场，而不是只恢复历史记录

Claude Code Deck 用 tmux 保存现场，并用 `ccd_name` 管理用途名。

## 工作流

Claude Code Deck 把三层状态统一起来：

```text
ccd_name -> ccd 内部 id -> tmux session -> Claude Code session id
```

进入工作台时：

```text
ccd enter 写论文
  |- 如果 ccd_内部id 的 tmux 还活着：直接 attach/switch
  `- 如果 tmux 不存在：新建 tmux，并运行 claude --resume <session_id>
```

新建工作台时：

```text
输入 ccd_name
选择常用目录
可选输入相对文件夹名
创建 ccd 注册表记录
启动 tmux + Claude Code
Claude Code SessionStart hook 回写真实 session id
```

## 核心功能

| 功能 | 说明 |
|:---|:---|
| 会话列表 | 只展示 ccd 管理的会话，按最近使用时间排序 |
| 新建会话 | 输入全局唯一用途名，选择常用目录，可选创建子目录 |
| 进入会话 | 优先 attach 到 live tmux，否则自动 `claude --resume` |
| 未读提醒 | transcript 晚于上次进入时间时，在 ccd 列表和 VS Code 插件里显示未查看结果 |
| 鼠标滚动 | 刷新 tmux 鼠标模式并接管滚轮，减少窄屏误操作 |
| Session ID 查询 | 显示某个 ccd 会话绑定的 Claude Code session id |
| 删除会话 | kill 对应 tmux，删除 ccd 映射，不删除 Claude Code 原始历史 |
| 重命名 | 支持中文和空格，live 会话也可重命名窗口 |
| 常用目录 | 管理新建会话时可选的 root 目录 |
| 手动映射 | 绑定、导入、解除、转移 Claude Code 原始会话 |
| 状态检查 | 检查配置、hook、注册表、tmux、cwd、重复映射 |

## 数据与安全

Claude Code Deck 使用 XDG 风格路径：

```text
~/.config/ccd/config.json
~/.local/share/ccd/sessions.json
~/.local/state/ccd/ccd.log
~/.local/state/ccd/lock
```

Claude Code 集成使用：

```text
~/.claude/settings.json          # 安装 SessionStart hook
~/.claude/history.jsonl          # 读取 Claude Code 历史摘要
~/.claude/projects/**/*.jsonl    # 读取 Claude Code transcript
```

安全策略：

- 注册表写入使用 `flock` 加锁
- 写文件使用临时文件和原子替换
- 删除 ccd 会话不删除 Claude Code 原始历史
- hook 只有检测到 `CCD_SESSION_ID` 时才工作
- 日志不记录 Claude Code 对话内容
- 修改 `~/.claude/settings.json` 前会创建时间戳备份

## 安装部署

依赖：

```bash
python3 --version
tmux -V
claude --version
```

手动安装：

```bash
git clone https://github.com/WangHaowen99/claude-code-deck.git
cd claude-code-deck
git checkout develop
chmod +x ccd install.sh
./install.sh
```

指定安装目录：

```bash
INSTALL_DIR=/usr/local/bin ./install.sh
```

跳过初始化：

```bash
CCD_SKIP_INIT=1 ./install.sh
ccd init
```

## 常用命令

```bash
ccd                       # 打开菜单
ccd list                  # 列出 ccd 会话
ccd list --json           # 输出机器可读会话列表
ccd new [ccd_name]        # 新建会话；同名则进入
ccd new --cwd PATH --no-enter --json [ccd_name]
ccd enter [ccd_name]      # 进入会话
ccd enter --new-if-unbound [ccd_name]
ccd enter --print-command [ccd_name]
ccd uuid [ccd_name]       # 查看绑定的 Claude Code session id
ccd uuid --all            # 列出所有 ccd 会话的绑定 ID
ccd delete [--yes] [ccd_name]
ccd rename [--json] OLD NEW
ccd roots                 # 管理常用目录
ccd map                   # 手动映射/导入 Claude Code 原始会话
ccd doctor                # 只报告状态问题
ccd init                  # 初始化并安装 hook
ccd install-hook          # 安装/刷新 Claude Code hook
```

## VS Code 扩展

`vscode-extension/` 提供一个轻量侧栏扩展，用来列出、创建、打开、重命名、删除和复制 session id。

直接下载编译好的 VSIX：

[claude-code-deck-0.1.0.vsix](https://github.com/WangHaowen99/claude-code-deck/raw/develop/dist/claude-code-deck-0.1.0.vsix)

下载后安装：

```bash
code --install-extension claude-code-deck-0.1.0.vsix
```

从源码编译：

```bash
cd vscode-extension
npm install
npm run compile
```

扩展默认调用远端/工作区主机上的 `ccd`，可通过 `Claude Code Deck: Ccd Path` 配置覆盖。

## 测试

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile ccd
```

## 卸载

```bash
rm -f ~/.local/bin/ccd
rm -rf ~/.config/ccd ~/.local/share/ccd ~/.local/state/ccd
```

然后从 `~/.claude/settings.json` 中删除 `ccd __hook-session-start` 相关的 `SessionStart` hook。
