---
name: pymol
description: How to use pymol-agent-bridge to connect to and control PyMOL
---

# PyMOL Agent Bridge Basics

## Connecting

```bash
# Launch PyMOL with the bridge plugin (opens GUI)
~/.pymol-agent-bridge/bin/pymol-agent-bridge launch

# Launch in headless mode (no GUI, for servers/CI)
~/.pymol-agent-bridge/bin/pymol-agent-bridge launch --headless

# Check connection status
~/.pymol-agent-bridge/bin/pymol-agent-bridge status
```

## Executing Commands

Send any PyMOL Python code via `exec`:

```bash
# Fetch a structure
~/.pymol-agent-bridge/bin/pymol-agent-bridge exec "cmd.fetch('1ubq')"

# Run multiple commands
~/.pymol-agent-bridge/bin/pymol-agent-bridge exec "cmd.fetch('1ubq'); cmd.show('cartoon'); cmd.color('cyan')"

# Execute from a file
~/.pymol-agent-bridge/bin/pymol-agent-bridge exec -f script.py

# Pipe from stdin
echo "cmd.fetch('1ubq')" | ~/.pymol-agent-bridge/bin/pymol-agent-bridge exec

# Get JSON output
~/.pymol-agent-bridge/bin/pymol-agent-bridge exec --json "cmd.fetch('1ubq'); print(cmd.get_area('all'))"
```

## Image Capture

**CRITICAL: Always use `cmd.ray()` then `cmd.png()` separately. NEVER pass width/height to `cmd.png()` directly.**

PyMOL's view matrix becomes corrupted when using `cmd.png(path, width, height)` after multiple `cmd.reinitialize()` cycles. The safe pattern:

```bash
~/.pymol-agent-bridge/bin/pymol-agent-bridge exec "
cmd.ray(2400, 2400)
cmd.png('/tmp/output.png')
"
```

Wrong (causes view corruption):
```python
cmd.png('/tmp/output.png', 2400, 2400)  # DO NOT DO THIS
```

## Common Gotchas

- **Port 9880**: The bridge uses TCP port 9880 on localhost. Only one PyMOL instance can use it at a time.
- **Stale processes**: If `launch` fails with a timeout, a previous PyMOL may still hold the port. Check with `lsof -ti :9880` and kill if needed.
- **Plugin not loaded**: If `status` shows "not available", PyMOL may be running without the plugin. Run `pymol-agent-bridge setup` to configure auto-loading, then restart PyMOL.
- **Headless rendering**: In headless mode (`-c`), PyMOL can still ray-trace and save images. It just doesn't open a window.
