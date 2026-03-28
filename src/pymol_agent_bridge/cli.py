"""
CLI for pymol-agent-bridge setup and management.

Usage:
    pymol-agent-bridge setup    # Configure PyMOL to auto-load the socket plugin
    pymol-agent-bridge status   # Check if PyMOL is running and connected
    pymol-agent-bridge test     # Test the connection
    pymol-agent-bridge info     # Show installation info
    pymol-agent-bridge launch   # Launch PyMOL or connect to existing instance
    pymol-agent-bridge exec     # Execute code in PyMOL
"""

import argparse
import json
import os
import stat
import sys
import time
from pathlib import Path

from pymol_agent_bridge.connection import (
    PyMOLConnection,
    connect_or_launch,
    find_pymol_command,
    find_pymolrc_path,
    get_config,
    get_plugin_path,
    is_plugin_in_pymolrc,
    save_config,
)

WRAPPER_DIR = Path.home() / ".pymol-agent-bridge" / "bin"
WRAPPER_PATH = WRAPPER_DIR / "pymol-agent-bridge"


def _create_wrapper_script():
    """Create wrapper script with baked Python path."""
    WRAPPER_DIR.mkdir(parents=True, exist_ok=True)
    python_path = sys.executable

    if sys.platform == "win32":
        # Windows batch file
        script = f'@echo off\n"{python_path}" -m pymol_agent_bridge.cli %*\n'
        wrapper_path = WRAPPER_PATH.with_suffix(".bat")
    else:
        # Bash script
        script = f'#!/bin/bash\n"{python_path}" -m pymol_agent_bridge.cli "$@"\n'
        wrapper_path = WRAPPER_PATH

    wrapper_path.write_text(script)
    if sys.platform != "win32":
        wrapper_path.chmod(
            wrapper_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        )
    return python_path


def setup_pymol():
    """Configure PyMOL to auto-load the socket plugin."""
    plugin_path = get_plugin_path()
    pymolrc_path = find_pymolrc_path()

    if not plugin_path.exists():
        print(f"Error: Plugin not found at {plugin_path}", file=sys.stderr)
        return 1

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
    clean_plugin_path = str(plugin_path).replace("\\", "/")
    run_command = f"\n# pymol-agent-bridge\nrun {clean_plugin_path}\n"

    if pymolrc_path.exists():
        with open(pymolrc_path, "a") as f:
            f.write(run_command)
        print(f"Added pymol-agent-bridge plugin to existing {pymolrc_path}")
    else:
        pymolrc_path.write_text(run_command.lstrip())
        print(f"Created {pymolrc_path} with pymol-agent-bridge plugin")

    # Save Python path
    save_config({"python_path": sys.executable})
    _create_wrapper_script()

    print("\nSetup complete! The plugin will auto-load when you start PyMOL.")
    return 0


def check_status():
    """Check PyMOL connection status."""
    print("Checking PyMOL status...")
    conn = PyMOLConnection()
    try:
        conn.connect(timeout=2.0)
        print("Socket connection: OK (port 9880)")
        conn.disconnect()
        return 0
    except ConnectionError:
        print("Socket connection: Not available")
        return 1


def run_doctor():
    """Perform a system check for common issues."""
    print("Checking system health for pymol-agent-bridge...")
    all_ok = True

    # Check OS & Python
    print(f"[OK] OS: {sys.platform}")
    vi = sys.version_info
    py_ver = f"{vi.major}.{vi.minor}.{vi.micro}"
    if sys.version_info >= (3, 10):
        print(f"[OK] Python: {py_ver}")
    else:
        print(f"[ERROR] Python: {py_ver} (Requires >=3.10)")
        all_ok = False

    # Check PyMOL
    pymol_cmd = find_pymol_command()
    if pymol_cmd:
        print(f"[OK] PyMOL found: {' '.join(pymol_cmd)}")
    else:
        print("[ERROR] PyMOL not found in PATH or common locations")
        all_ok = False

    # Check .pymolrc
    pymolrc_path = find_pymolrc_path()
    if pymolrc_path.exists():
        print(f"[OK] PyMOL config found: {pymolrc_path}")
        if is_plugin_in_pymolrc():
            print("[OK] Bridge plugin is configured in PyMOL config")
        else:
            print("[WARN] Bridge plugin NOT configured in PyMOL config")
            all_ok = False
    else:
        print("[WARN] PyMOL config not found")
        all_ok = False

    return 0 if all_ok else 1


def test_connection():
    """Test the PyMOL connection with a simple command."""
    conn = PyMOLConnection()
    try:
        conn.connect(timeout=2.0)
        result = conn.execute("print('bridge test')")
        print(f"Connection test: OK. Response: {result}")
        conn.disconnect()
        return 0
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        return 1


def show_info():
    """Show pymol-agent-bridge installation info."""
    print("pymol-agent-bridge installation info:")
    print(f"  Plugin: {get_plugin_path()}")
    print(f"  .pymolrc: {find_pymolrc_path()}")
    print(f"  Wrapper: {WRAPPER_PATH}")
    config = get_config()
    if config:
        print(f"  Config: {config}")


def do_launch(args):
    """Launch PyMOL or connect to existing instance."""
    try:
        conn, process = connect_or_launch(file_path=args.file, headless=args.headless)
        if process:
            print(f"Launched PyMOL (pid {process.pid})")
        else:
            print("Connected to existing PyMOL instance")
        conn.disconnect()
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def do_repl():
    """Start an interactive PyMOL shell."""
    print("PyMOL Bridge Interactive Shell. Type 'exit' to quit.")
    conn = PyMOLConnection()
    try:
        conn.connect(timeout=2.0)
        while True:
            line = input("pymol> ")
            if line.lower() in ("exit", "quit"):
                break
            if not line.strip():
                continue
            print(conn.execute(line))
    except (EOFError, KeyboardInterrupt):
        print()
    except Exception as e:
        print(f"Error: {e}")
    return 0


def do_watch(args):
    """Watch a file and send it to PyMOL on change."""
    path = Path(args.file)
    print(f"Watching {path}... (Ctrl-C to stop)")
    last_mtime = None
    waiting_for_file = False
    conn = PyMOLConnection()
    try:
        while True:
            try:
                mtime = path.stat().st_mtime
            except FileNotFoundError:
                if not waiting_for_file:
                    print(f"Waiting for file: {path}")
                    waiting_for_file = True
                last_mtime = None
                time.sleep(0.5)
                continue

            waiting_for_file = False
            if mtime != last_mtime:
                print("Sending change...")
                try:
                    code = path.read_text()
                    conn.connect(timeout=2.0)
                    print(conn.execute(code))
                except OSError as e:
                    print(f"Error reading {path}: {e}")
                except Exception as e:
                    print(f"Error: {e}")
                else:
                    last_mtime = mtime
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        conn.disconnect()


def do_run_code(args):
    """Send code to PyMOL for evaluation."""
    def emit_error(message):
        if args.json:
            print(json.dumps({"status": "error", "error": message}))
        else:
            print(f"Error: {message}", file=sys.stderr)
        return 1

    code = args.code
    if args.file:
        file_path = Path(args.file)
        try:
            code = file_path.read_text()
        except OSError as e:
            return emit_error(f"Cannot read file '{file_path}': {e}")
    elif code and code.startswith("@"):
        file_path = Path(code[1:])
        try:
            code = file_path.read_text()
        except OSError as e:
            return emit_error(f"Cannot read file '{file_path}': {e}")
    elif not code and not os.isatty(sys.stdin.fileno()):
        code = sys.stdin.read()

    if not code or not code.strip():
        return emit_error("No code provided")

    conn = PyMOLConnection()
    try:
        conn.connect(timeout=2.0)
        result = conn.execute(code)
        if args.json:
            print(json.dumps({"status": "success", "output": result}))
        else:
            print(result)
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"status": "error", "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description="pymol-agent-bridge")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("setup")
    subparsers.add_parser("status")
    subparsers.add_parser("doctor")
    subparsers.add_parser("test")
    subparsers.add_parser("info")
    subparsers.add_parser("repl")

    l_p = subparsers.add_parser("launch")
    l_p.add_argument("file", nargs="?")
    l_p.add_argument("--headless", action="store_true")

    w_p = subparsers.add_parser("watch")
    w_p.add_argument("file")

    for cmd in ["exec", "run-code"]:
        e_p = subparsers.add_parser(cmd)
        e_p.add_argument("code", nargs="?")
        e_p.add_argument("-f", "--file")
        e_p.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if not args.command:
        show_info()
        return 0

    cmds = {
        "setup": setup_pymol,
        "status": check_status,
        "doctor": run_doctor,
        "test": test_connection,
        "info": show_info,
        "repl": do_repl,
        "watch": lambda: do_watch(args),
        "launch": lambda: do_launch(args),
        "exec": lambda: do_run_code(args),
        "run-code": lambda: do_run_code(args),
    }
    return cmds[args.command]()


if __name__ == "__main__":
    sys.exit(main())
