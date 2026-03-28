# CLAUDE.md

## Project Overview

pymol-agent-bridge is a lightweight TCP socket bridge between coding agents (or terminals) and PyMOL. No LLM layer, no API keys, no UI opinions. Zero runtime dependencies.

## Architecture

```
Agent/Terminal -> ~/.pymol-agent-bridge/bin/pymol-agent-bridge exec -> TCP Socket (port 9880) -> PyMOL Plugin -> cmd.* execution
```

## CLI Reference

```bash
pymol-agent-bridge setup      # Configure ~/.pymolrc and create wrapper script
pymol-agent-bridge status     # Check if PyMOL is running and connected
pymol-agent-bridge test       # Test connection with a simple command
pymol-agent-bridge info       # Show installation info
pymol-agent-bridge launch     # Launch PyMOL or connect to existing
pymol-agent-bridge launch --headless  # Launch without GUI
pymol-agent-bridge exec "code"  # Execute Python code in PyMOL
```

## Key Patterns

- Always use `~/.pymol-agent-bridge/bin/pymol-agent-bridge` (wrapper script with baked Python path)
- Launch before exec: `pymol-agent-bridge launch` then `pymol-agent-bridge exec`
- Image capture: use `cmd.ray(w, h)` then `cmd.png(path)` — NEVER pass dimensions to `cmd.png()` directly
- Port 9880 on localhost — one PyMOL instance at a time

## Development

```bash
uv sync                    # Install dependencies
ruff check src/            # Lint
ruff format src/           # Format
pyright                    # Type check
pytest tests/              # Run tests (requires PyMOL installed)
```

## Repository Structure

```
src/pymol_agent_bridge/
  connection.py   # TCP socket client, PyMOL discovery, launch, config
  plugin.py       # Socket listener that runs inside PyMOL
  session.py      # Session lifecycle, health checks, recovery
  cli.py          # CLI: setup, status, test, info, launch, exec
```
