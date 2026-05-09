# Claude Code Deck VS Code Extension

This extension adds a Claude Code Deck sidebar for VS Code and VS Code Remote SSH.

It does not reimplement Claude Code Deck. It calls the remote/workspace `ccd` command:

- `ccd list --json`
- `ccd new --cwd <path> --no-enter --json <ccd_name>`
- `ccd rename --json <old> <new>`
- `ccd delete --yes --json <ccd_name>`
- `ccd enter <ccd_name>`
- `ccd enter --new-if-unbound <ccd_name>`

## Development

```bash
cd vscode-extension
npm install
npm run compile
```

Open this folder in VS Code and press `F5` to launch an extension development host.

For Remote SSH, install/run the extension on the remote workspace side so `ccd` resolves to the remote Claude Code Deck executable.
