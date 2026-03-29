# pymol-agent-bridge

A lightweight bridge that lets coding agents control [PyMOL](https://pymol.org). Works with any agent that has a terminal — Claude Code, Cursor, Codex, or anything else.

## Why

PyMOL is powerful but complex. Coding agents make it accessible: you describe what you want in plain language and the agent handles the PyMOL commands. Because agents work in your terminal alongside your code, they can tie together structure analysis, literature, data pipelines, and visualization in ways that a standalone tool can't — fetching structures from databases, annotating functional sites from literature, labeling residues with predictions, or sanity-checking de novo protein designs.

This bridge connects your agent to a running PyMOL instance. That's all it does. No new UI, no LLM layer, no wrapper around PyMOL's functionality — just a pipe between your agent's terminal and PyMOL's Python API.

## How it works

Setup installs a small plugin into your `.pymolrc` that opens a TCP socket listener inside PyMOL. When your agent needs to interact with PyMOL, it sends Python commands through this socket via a simple CLI. The commands execute against PyMOL's standard `cmd.*` API, and results come back over the same connection. One socket, one port (9880), zero runtime dependencies.

## Install

```bash
pip install pymol-agent-bridge
pymol-agent-bridge setup
```

Setup will find your PyMOL installation (or help you install it), configure the bridge plugin in your `.pymolrc`, and create a stable wrapper script at `~/.pymol-agent-bridge/bin/pymol-agent-bridge`.

## Usage

After setup, open your coding agent and start working:

> "Load the structure 1UBQ and color it by secondary structure"

> "Fetch 6LU7, highlight the active site residues, and render a high-res image"

> "Compare the binding pockets of these two kinase structures"

The agent launches PyMOL if needed, sends commands through the bridge, and shows you the results. You don't need to learn any CLI commands — the agent knows how to use the bridge.

## Features

- **Zero dependencies** — Pure Python standard library. Nothing to install beyond the bridge itself.
- **Cross-platform** — macOS, Linux, and Windows.
- **Persistent session** — PyMOL stays running between commands. State is preserved.
- **JSON output** — Structured output mode for programmatic use.
- **Stable paths** — Wrapper script with baked Python path survives environment changes.
- **Agent-agnostic** — Works with any coding agent that can run shell commands.

## License

MIT
