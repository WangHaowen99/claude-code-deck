<div align="center" id="claude-code-deck">

# Claude Code Deck

A Claude Code session manager for phone SSH and remote terminals.  
Use one `ccd` command to turn Claude Code conversations and tmux terminals into named, reconnectable workspaces.

[![GitHub Stars](https://img.shields.io/github/stars/WangHaowen99/claude-code-deck?style=flat-square&logo=github&color=yellow)](https://github.com/WangHaowen99/claude-code-deck/stargazers)
[![Branch](https://img.shields.io/badge/default_branch-develop-2ea44f?style=flat-square&logo=git)](https://github.com/WangHaowen99/claude-code-deck/tree/develop)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![tmux](https://img.shields.io/badge/tmux-required-1BB91F?style=flat-square)](https://github.com/tmux/tmux)
[![Claude Code](https://img.shields.io/badge/Claude_Code-supported-111111?style=flat-square)](https://docs.anthropic.com/en/docs/claude-code)

**[中文](README.md)** | **English**

</div>

## Quick Start

One-line install:

```bash
curl -fsSL https://raw.githubusercontent.com/WangHaowen99/claude-code-deck/develop/install.sh | bash
```

Open the menu:

```bash
ccd
```

Create a workspace:

```bash
ccd new paper-writing
```

Resume later:

```bash
ccd enter paper-writing
```

## Why

Claude Code can resume conversations, but phone SSH and long-running remote work need a smaller workflow:

- reconnect after SSH drops
- avoid reading raw session ids on a narrow terminal
- manage work by purpose names
- preserve the live Claude Code terminal, not just the conversation history

Claude Code Deck keeps each workspace in tmux and maps it to a stable `ccd_name`.

## Workflow

Claude Code Deck joins these layers:

```text
ccd_name -> ccd internal id -> tmux session -> Claude Code session id
```

Entering a workspace:

```text
ccd enter paper-writing
  |- attach/switch to the live tmux session if it exists
  `- otherwise create tmux and run claude --resume <session_id>
```

Creating a workspace:

```text
enter ccd_name
choose a common root directory
optionally enter a relative folder
create the ccd registry record
start tmux + Claude Code
Claude Code SessionStart hook writes back the real session id
```

## Features

| Feature | Description |
|:---|:---|
| Session list | Shows only ccd-managed sessions, sorted by recent use |
| New session | Choose a root directory and optionally create a subdirectory |
| Enter session | Attach to live tmux or resume Claude Code automatically |
| Unread reminder | Shows unread results in the ccd list and VS Code extension when the transcript is newer than the last entered time |
| Mouse scrolling | Refreshes tmux mouse mode and intercepts wheel events for narrow terminals |
| Session ID lookup | Show the Claude Code session id bound to a ccd workspace |
| Delete session | Kill tmux and remove the ccd mapping, preserving Claude Code history |
| Rename | Supports live sessions and names with spaces |
| Roots | Manage common root directories |
| Mapping | Bind, import, unbind, or transfer raw Claude Code sessions |
| Doctor | Report config, hook, registry, tmux, cwd, and mapping issues |

## Data and Safety

Claude Code Deck uses XDG-style paths:

```text
~/.config/ccd/config.json
~/.local/share/ccd/sessions.json
~/.local/state/ccd/ccd.log
~/.local/state/ccd/lock
```

Claude Code integration:

```text
~/.claude/settings.json          # SessionStart hook
~/.claude/history.jsonl          # Claude Code history summary
~/.claude/projects/**/*.jsonl    # Claude Code transcripts
```

Safety choices:

- Registry writes use `flock`
- Writes are atomic
- Deleting a ccd session does not delete Claude Code history
- The hook only runs when `CCD_SESSION_ID` is present
- Logs do not store Claude Code conversation content
- `~/.claude/settings.json` is backed up before modification

## Install

Requirements:

```bash
python3 --version
tmux -V
claude --version
```

Manual install:

```bash
git clone https://github.com/WangHaowen99/claude-code-deck.git
cd claude-code-deck
git checkout develop
chmod +x ccd install.sh
./install.sh
```

Custom install directory:

```bash
INSTALL_DIR=/usr/local/bin ./install.sh
```

Skip initialization:

```bash
CCD_SKIP_INIT=1 ./install.sh
ccd init
```

## Commands

```bash
ccd                       # open menu
ccd list                  # list ccd sessions
ccd list --json           # machine-readable session list
ccd new [ccd_name]        # create session; same name enters existing
ccd new --cwd PATH --no-enter --json [ccd_name]
ccd enter [ccd_name]      # enter session
ccd enter --new-if-unbound [ccd_name]
ccd enter --print-command [ccd_name]
ccd uuid [ccd_name]       # show the bound Claude Code session id
ccd uuid --all            # list bound IDs for all ccd sessions
ccd delete [--yes] [ccd_name]
ccd rename [--json] OLD NEW
ccd roots                 # manage common roots
ccd map                   # manage raw Claude Code mappings
ccd doctor                # report state problems
ccd init                  # initialize and install hook
ccd install-hook          # refresh Claude Code hook
```

## VS Code Extension

`vscode-extension/` provides a small sidebar extension for listing, creating, opening, renaming, deleting, and copying session ids.

Download the compiled VSIX:

[claude-code-deck-0.1.0.vsix](https://github.com/WangHaowen99/claude-code-deck/raw/develop/dist/claude-code-deck-0.1.0.vsix)

Install after download:

```bash
code --install-extension claude-code-deck-0.1.0.vsix
```

Build from source:

```bash
cd vscode-extension
npm install
npm run compile
```

The extension calls `ccd` on the remote/workspace host by default. Override it with the `Claude Code Deck: Ccd Path` setting.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile ccd
```

## Uninstall

```bash
rm -f ~/.local/bin/ccd
rm -rf ~/.config/ccd ~/.local/share/ccd ~/.local/state/ccd
```

Then remove the `SessionStart` hook that calls `ccd __hook-session-start` from `~/.claude/settings.json`.
