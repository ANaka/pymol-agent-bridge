---
name: setup
description: Install and bootstrap pymol-agent-bridge with a working PyMOL connection
---

# PyMOL Agent Bridge Setup

## First-Time Install

Install the bridge package, then run setup:

```bash
# Pick one
uv add pymol-agent-bridge
# or
pip install pymol-agent-bridge

pymol-agent-bridge setup
```

`setup` will:
- Detect (or help install) PyMOL
- Add plugin autoload to `.pymolrc`
- Create a stable wrapper script at `~/.pymol-agent-bridge/bin/pymol-agent-bridge`

## Launch and Verify

After setup, launch PyMOL and verify the bridge:

```bash
# Launch GUI PyMOL
~/.pymol-agent-bridge/bin/pymol-agent-bridge launch

# Or headless
~/.pymol-agent-bridge/bin/pymol-agent-bridge launch --headless

# Verify socket + command execution
~/.pymol-agent-bridge/bin/pymol-agent-bridge status
~/.pymol-agent-bridge/bin/pymol-agent-bridge test
```

## Minimal Smoke Test

```bash
~/.pymol-agent-bridge/bin/pymol-agent-bridge exec "cmd.fetch('1ubq'); cmd.show('cartoon')"
```

If this succeeds, setup is complete.

## Troubleshooting

- **PyMOL missing**: Re-run `pymol-agent-bridge setup` in an interactive terminal to follow guided install prompts.
- **Status says "Not available"**: PyMOL is not running with the plugin; run `setup` again and relaunch PyMOL.
- **Port conflict (`9880`)**: Another stale PyMOL process may be holding the socket. Check `lsof -ti :9880` and stop the stale process.
- **Command not found**: Use the wrapper path directly: `~/.pymol-agent-bridge/bin/pymol-agent-bridge`.
