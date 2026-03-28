# pymol-agent-bridge

Lightweight bridge connecting coding agents to [PyMOL](https://pymol.org) via TCP socket. No LLM layer, no API keys, no UI opinions. Works with any coding agent that has a terminal.

## Why this exists

Projects like ChatMol and PyMolAI bundle LLM layers, require API keys, and build custom UIs inside PyMOL. They'll break when models change. This project bets that:

- **The agent IS the intelligence** -- this tool just gives it hands inside PyMOL
- **PyMOL's terminal is not great**, but your own terminal/IDE is -- so connect through there
- **The thinnest possible layer is the most future-proof**

## Install

```bash
pip install pymol-agent-bridge
pymol-agent-bridge setup
```

## Usage

```bash
# Launch PyMOL with the bridge plugin
pymol-agent-bridge launch

# Execute commands
pymol-agent-bridge exec "cmd.fetch('1ubq')"
pymol-agent-bridge exec "cmd.show('cartoon'); cmd.color('cyan')"

# Headless mode (no GUI -- for servers, CI, batch jobs)
pymol-agent-bridge launch --headless
pymol-agent-bridge exec "cmd.fetch('1ubq'); cmd.ray(2400, 2400); cmd.png('/tmp/1ubq.png')"

# Check status
pymol-agent-bridge status
```

## How it works

```
Agent/Terminal --> pymol-agent-bridge exec --> TCP socket (localhost:9880) --> PyMOL plugin --> cmd.*
```

1. `pymol-agent-bridge setup` configures PyMOL to auto-load a socket listener plugin on startup
2. `pymol-agent-bridge launch` starts PyMOL (or connects to an existing instance)
3. `pymol-agent-bridge exec "..."` sends Python code to PyMOL over TCP and returns the output

Zero runtime dependencies. Pure Python stdlib.

## Image capture

**Always use `cmd.ray()` then `cmd.png()` separately.** Never pass dimensions to `cmd.png()` directly -- it corrupts PyMOL's view matrix after multiple reinitialize cycles.

```python
# Correct
cmd.ray(2400, 2400)
cmd.png('/tmp/output.png')

# Wrong -- causes view corruption
cmd.png('/tmp/output.png', 2400, 2400)
```

## PyMOL commands

The plugin registers these commands inside PyMOL's terminal:

| Command | Description |
|---------|-------------|
| `bridge_status` | Show listener status |
| `bridge_stop` | Stop the listener |
| `bridge_start` | Restart the listener |

## Works with any coding agent

This bridge is agent-agnostic. If your agent can run shell commands, it can control PyMOL:

- **Claude Code** -- use with [claudemol](https://github.com/ANaka/claudemol) skills for structural biology workflows
- **Cursor, Copilot, etc.** -- point at `~/.pymol-agent-bridge/bin/pymol-agent-bridge exec` in your instructions
- **Shell scripts** -- automate batch rendering, analysis pipelines, CI jobs

## Migrating from claudemol

If you previously used the `claudemol` pip package:

```bash
pip install pymol-agent-bridge
pymol-agent-bridge setup  # Detects and replaces old claudemol entries in ~/.pymolrc
```

The `setup` command will automatically remove legacy claudemol entries from your `~/.pymolrc` and configure the new bridge plugin.

## Development

```bash
git clone https://github.com/ANaka/pymol-agent-bridge.git
cd pymol-agent-bridge
uv sync
pytest tests/  # Requires PyMOL installed
ruff check src/
```

## License

MIT
