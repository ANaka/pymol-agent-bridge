# CLAUDE.md

## Project Overview

pymol-agent-bridge is a lightweight TCP socket bridge between coding agents and PyMOL. No LLM layer, no API keys, no UI opinions. Zero runtime dependencies.

## Design Philosophy

**We are a bridge and nothing more.** This project exists to let coding agents control PyMOL. That's it.

### The interaction model

```
Human -> Agent -> CLI (exec/launch/status) -> TCP socket -> PyMOL plugin -> cmd.*
```

The human talks to the agent. The agent talks to the bridge. The bridge talks to PyMOL. The human never needs to learn CLI commands — they describe what they want and the agent handles the rest.

### Why coding agents (not API-key LLM wrappers)

Coding agents are superior to setups where you pass in an API key and make LLM calls, because the things people want to do with PyMOL often involve interacting with other data and code. Agents can:
- Do complicated queries to find and ingress structure data
- Run analyses to label/annotate structures (e.g. zero-shot predictions for mutation sites)
- Find and read literature, then annotate functional sites
- Write complex specifications for protein design workflows
- Sanity-check de novo protein designs by inspecting structures

A coding agent ties all of these together in a single terminal session. An API-key wrapper can only talk to PyMOL.

### Why we don't wrap or rebuild PyMOL

Other approaches rebuild PyMOL's functionality or wrap it with new UI. We deliberately don't:
- PyMOL's existing UI is fine — we just open a new, agent-centered interface alongside it
- We use an external terminal because PyMOL's terminal is specifically for PyMOL, not general use
- Users of coding agents have already optimized their terminal/IDE setups — we let them keep those

### Why CLI over MCP

We chose a CLI interface over MCP (Model Context Protocol) deliberately:
- **Universality**: CLI works with any agent that has a terminal. MCP requires framework support — Claude Code and Cursor support it, but not everything does. A terminal is the lowest common denominator.
- **Simplicity**: MCP adds JSON-RPC, tool schemas, and capability negotiation on top of our already simple TCP protocol. CLI is just "run a command, read stdout."
- **Debuggability**: A human can test `pymol-agent-bridge exec "cmd.fetch('1ubq')"` directly in their terminal. MCP requires the agent framework running to test.
- **No agent lock-in**: CLI is stdin/stdout/stderr everywhere. MCP hosts have different quirks.
- **Durability**: MCP is still evolving as a spec. CLI conventions have been stable for decades. We bet on the stable interface.

### Minimal surface area

We expect both coding agents and PyMOL to keep evolving. We keep this project minimal so it stays useful:
- Zero runtime dependencies
- Small CLI surface: `setup`, `launch`, `exec`, `status`, `test`, `info`
- No features that duplicate what agents or PyMOL already do
- If an agent can do it (troubleshooting, interactive exploration, file watching), we don't build it into the bridge

## CLI Reference

```bash
pymol-agent-bridge setup      # Configure ~/.pymolrc and create wrapper script
pymol-agent-bridge launch     # Launch PyMOL or connect to existing
pymol-agent-bridge launch --headless  # Launch without GUI
pymol-agent-bridge exec "code"  # Execute Python code in PyMOL
pymol-agent-bridge exec -f script.py  # Execute from file
pymol-agent-bridge exec --json "code"  # JSON-formatted output
pymol-agent-bridge status     # Check if PyMOL is running and connected
pymol-agent-bridge test       # Test connection with a simple command
pymol-agent-bridge info       # Show installation info
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
  cli.py          # CLI: setup, launch, exec, status, test, info
  connection.py   # TCP socket client, PyMOL discovery, launch, config
  plugin.py       # Socket listener that runs inside PyMOL
  protocol.py     # Length-prefixed JSON wire protocol
```
