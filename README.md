# pymol-agent-bridge

Lightweight bridge connecting coding agents to [PyMOL](https://pymol.org) via TCP socket. No LLM layer, no API keys, no UI opinions. Works with any coding agent that has a terminal.

## Features

- **Cross-platform**: Supports macOS, Linux, and Windows.
- **Zero-dependency**: Pure Python standard library.
- **Agent-friendly**: Clean CLI interface, JSON output support, and stable paths for tool integration.
- **Live-coding**: `watch` mode to auto-reload scripts as you edit them.
- **Interactive**: Built-in `repl` for quick testing.
- **Diagnostic**: `doctor` command to troubleshoot setup issues.

## Install

```bash
pip install pymol-agent-bridge
pymol-agent-bridge setup
```

## Usage

### Basic Commands
```bash
# Launch PyMOL with the bridge plugin
pymol-agent-bridge launch

# Execute commands (standard Python/PyMOL API)
pymol-agent-bridge exec "cmd.fetch('1ubq')"

# Execute from a file
pymol-agent-bridge exec -f script.py
# Or using the @ prefix
pymol-agent-bridge exec @script.py

# Watch a file and reload on change (Live Coding)
pymol-agent-bridge watch script.py

# Interactive REPL
pymol-agent-bridge repl

# Check system health
pymol-agent-bridge doctor
```

### Headless / Batch Mode
```bash
# Launch without GUI
pymol-agent-bridge launch --headless

# Run and get JSON output
pymol-agent-bridge exec "cmd.fetch('1ubq'); print(cmd.get_area('all'))" --json
```

## Agent Integration

This bridge is designed to be used as a **tool** for coding agents (Claude, Cursor, GPT-4, etc.). 

### Why Agents love this
- **Fast**: TCP socket is much faster than launching PyMOL per command.
- **Context-aware**: PyMOL's state is preserved between `exec` calls.
- **Standard**: Uses the standard PyMOL Python API (`cmd.*`).

### Recommended Agent Setup
Point your agent to the stable wrapper script created during `setup`:
- macOS/Linux: `~/.pymol-agent-bridge/bin/pymol-agent-bridge`
- Windows: `~/.pymol-agent-bridge/bin/pymol-agent-bridge.bat`

## Troubleshooting

Run `pymol-agent-bridge doctor` to check for:
- PyMOL installation and PATH.
- `.pymolrc` / `pymolrc.py` configuration.
- Port 9880 availability.

## Image Capture Tip

Always use `cmd.ray()` then `cmd.png()` separately to avoid view matrix corruption in PyMOL.

```python
cmd.ray(2400, 2400)
cmd.png('output.png')
```

## License

MIT
