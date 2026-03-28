"""
CLI for pymol-agent-bridge setup and management.

Usage:
    pymol-agent-bridge setup    # Configure PyMOL to auto-load the socket plugin
    pymol-agent-bridge status   # Check if PyMOL is running and connected
    pymol-agent-bridge test     # Test the connection
    pymol-agent-bridge info     # Show installation info
    pymol-agent-bridge launch   # Launch PyMOL or connect to existing instance
    pymol-agent-bridge run-code # Send code to PyMOL for evaluation
"""

import argparse
import os
import stat
import sys
from pathlib import Path

from pymol_agent_bridge.connection import (
    CONFIG_FILE,
    PyMOLConnection,
    check_pymol_installed,
    connect_or_launch,
    find_pymol_command,
    get_config,
    get_configured_python,
    get_plugin_path,
    has_legacy_pymolrc_entry,
    is_plugin_in_pymolrc,
    remove_legacy_pymolrc_entries,
    save_config,
)

WRAPPER_DIR = Path.home() / ".pymol-agent-bridge" / "bin"
WRAPPER_PATH = WRAPPER_DIR / "pymol-agent-bridge"
PYMOLRC_PATH = Path.home() / ".pymolrc"


def _create_wrapper_script():
    """Create wrapper shell script with baked Python path."""
    WRAPPER_DIR.mkdir(parents=True, exist_ok=True)
    python_path = sys.executable
    script = f"""#!/bin/bash
"{python_path}" -m pymol_agent_bridge.cli "$@"
"""
    WRAPPER_PATH.write_text(script)
    WRAPPER_PATH.chmod(
        WRAPPER_PATH.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    return python_path


def setup_pymol():
    """Configure PyMOL to auto-load the socket plugin."""
    plugin_path = get_plugin_path()
    if not plugin_path.exists():
        print(f"Error: Plugin not found at {plugin_path}", file=sys.stderr)
        return 1

    # Handle legacy claudemol entries
    if has_legacy_pymolrc_entry():
        print("Found legacy claudemol entries in .pymolrc, replacing...")
        remove_legacy_pymolrc_entries()

    # Check if already configured
    if is_plugin_in_pymolrc():
        print("PyMOL already configured for pymol-agent-bridge.")
        print(f"Plugin: {plugin_path}")
        # Still save config (in case Python path changed)
        save_config({"python_path": sys.executable})
        print(f"Saved Python path: {sys.executable}")
        _create_wrapper_script()
        print(f"Wrapper script: {WRAPPER_PATH}")
        return 0

    # Add to .pymolrc
    run_command = f"\n# pymol-agent-bridge\nrun {plugin_path}\n"

    if PYMOLRC_PATH.exists():
        with open(PYMOLRC_PATH, "a") as f:
            f.write(run_command)
        print(f"Added pymol-agent-bridge plugin to existing {PYMOLRC_PATH}")
    else:
        PYMOLRC_PATH.write_text(run_command.lstrip())
        print(f"Created {PYMOLRC_PATH} with pymol-agent-bridge plugin")

    print(f"Plugin path: {plugin_path}")
    print("\nSetup complete! The plugin will auto-load when you start PyMOL.")

    # Check if PyMOL is installed
    if not check_pymol_installed():
        print("\nNote: PyMOL not found in PATH.")
        print("Install PyMOL with one of:")
        print("  - pip install pymol-open-source-whl")
        print("  - brew install pymol (macOS)")
        print("  - Download from https://pymol.org")

    # Save Python path
    save_config({"python_path": sys.executable})
    print(f"Saved Python path: {sys.executable}")

    # Create wrapper script
    _create_wrapper_script()
    print(f"Wrapper script: {WRAPPER_PATH}")

    return 0


def check_status():
    """Check PyMOL connection status."""
    print("Checking PyMOL status...")

    configured_python = get_configured_python()
    if configured_python:
        print(f"Configured Python: {configured_python}")

    pymol_cmd = find_pymol_command()
    if pymol_cmd:
        print(f"PyMOL found: {' '.join(pymol_cmd)}")
    else:
        print("PyMOL not found in PATH")
        return 1

    conn = PyMOLConnection()
    try:
        conn.connect(timeout=2.0)
        print("Socket connection: OK (port 9880)")
        conn.disconnect()
        return 0
    except ConnectionError:
        print("Socket connection: Not available")
        print("  (PyMOL may not be running, or plugin not loaded)")
        return 1


def test_connection():
    """Test the PyMOL connection with a simple command."""
    conn = PyMOLConnection()
    try:
        conn.connect(timeout=2.0)
        result = conn.execute("print('pymol-agent-bridge connection test')")
        print("Connection test: OK")
        print(f"Response: {result}")
        conn.disconnect()
        return 0
    except ConnectionError as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        print("\nMake sure PyMOL is running with the socket plugin.")
        print("Start PyMOL and run: bridge_status")
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def show_info():
    """Show pymol-agent-bridge installation info."""
    plugin_path = get_plugin_path()

    print("pymol-agent-bridge installation info:")
    print(f"  Plugin: {plugin_path}")
    print(f"  Plugin exists: {plugin_path.exists()}")
    print(f"  .pymolrc: {PYMOLRC_PATH}")
    print(f"  .pymolrc exists: {PYMOLRC_PATH.exists()}")

    if PYMOLRC_PATH.exists():
        configured = is_plugin_in_pymolrc()
        print(f"  Configured in .pymolrc: {configured}")
        if has_legacy_pymolrc_entry():
            print("  Warning: legacy claudemol entries found (run setup to replace)")

    pymol_cmd = find_pymol_command()
    print(f"  PyMOL command: {' '.join(pymol_cmd) if pymol_cmd else 'not found'}")

    print(f"  Config file: {CONFIG_FILE}")
    config = get_config()
    if config:
        for key, value in config.items():
            print(f"  Config {key}: {value}")
    else:
        print("  Config: not set (run 'pymol-agent-bridge setup' to configure)")

    print(f"  Wrapper script: {WRAPPER_PATH}")
    print(f"  Wrapper exists: {WRAPPER_PATH.exists()}")


def do_launch(args):
    """Launch PyMOL or connect to existing instance."""
    file_path = getattr(args, "file", None)
    headless = getattr(args, "headless", False)
    try:
        conn, process = connect_or_launch(file_path=file_path, headless=headless)
        if process:
            mode = " (headless)" if headless else ""
            print(f"Launched PyMOL{mode} (pid {process.pid})")
        else:
            print("Connected to existing PyMOL instance")
        conn.disconnect()
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def do_run_code(args):
    """Send code to PyMOL for evaluation."""
    code = getattr(args, "code", None)

    if code:
        code = code
    elif not os.isatty(sys.stdin.fileno()):
        code = sys.stdin.read()
    else:
        print(
            "Error: No code provided. Pass as argument or pipe via stdin.",
            file=sys.stderr,
        )
        print(
            "  pymol-agent-bridge run-code \"cmd.fetch('1ubq')\"", file=sys.stderr
        )
        print(
            "  echo \"cmd.fetch('1ubq')\" | pymol-agent-bridge run-code",
            file=sys.stderr,
        )
        return 1

    if not code.strip():
        print("Error: Empty code.", file=sys.stderr)
        return 1

    conn = PyMOLConnection()
    try:
        conn.connect(timeout=2.0)
    except ConnectionError:
        print("Error: Cannot connect to PyMOL. Is it running?", file=sys.stderr)
        print("  Run: pymol-agent-bridge launch", file=sys.stderr)
        return 1

    try:
        result = conn.execute(code)
        if result:
            print(result, end="" if result.endswith("\n") else "\n")
        conn.disconnect()
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        conn.disconnect()
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="pymol-agent-bridge: Lightweight bridge connecting agents to PyMOL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "setup", help="Configure PyMOL to auto-load the socket plugin"
    )
    subparsers.add_parser("status", help="Check if PyMOL is running and connected")
    subparsers.add_parser("test", help="Test the connection with a simple command")
    subparsers.add_parser("info", help="Show installation info")

    launch_parser = subparsers.add_parser(
        "launch", help="Launch PyMOL or connect to existing instance"
    )
    launch_parser.add_argument(
        "file", nargs="?", default=None, help="File to open (e.g., .pdb, .cif)"
    )
    launch_parser.add_argument(
        "--headless",
        action="store_true",
        help="Launch PyMOL in command-line mode (no GUI)",
    )

    run_code_parser = subparsers.add_parser(
        "run-code", help="Send code to PyMOL for evaluation"
    )
    run_code_parser.add_argument(
        "code",
        nargs="?",
        default=None,
        help="Python code to send (or pipe via stdin)",
    )

    # "exec" is an alias for "run-code"
    exec_parser = subparsers.add_parser("exec", help="Alias for run-code")
    exec_parser.add_argument(
        "code",
        nargs="?",
        default=None,
        help="Python code to send (or pipe via stdin)",
    )

    args = parser.parse_args()

    if args.command is None:
        show_info()
        return 0
    elif args.command == "setup":
        return setup_pymol()
    elif args.command == "status":
        return check_status()
    elif args.command == "test":
        return test_connection()
    elif args.command == "info":
        show_info()
        return 0
    elif args.command == "launch":
        return do_launch(args)
    elif args.command in ("run-code", "exec"):
        return do_run_code(args)


if __name__ == "__main__":
    sys.exit(main())
