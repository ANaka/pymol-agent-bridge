"""Unit tests for CLI command functions (do_run_code, check_status, show_info, main)."""

import json
import sys

from pymol_agent_bridge import cli

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeConnection:
    """Minimal stand-in for PyMOLConnection used by do_run_code / check_status."""

    def __init__(self, execute_result="ok", connect_error=None):
        self._execute_result = execute_result
        self._connect_error = connect_error

    def connect(self, timeout=None):
        if self._connect_error:
            raise self._connect_error
        return True

    def execute(self, code):
        return self._execute_result

    def disconnect(self):
        pass


def _make_args(code=None, file=None, json_output=False):
    """Build a minimal namespace matching what argparse produces for 'exec'."""
    import argparse

    return argparse.Namespace(code=code, file=file, json=json_output)


# ---------------------------------------------------------------------------
# do_run_code
# ---------------------------------------------------------------------------


class TestDoRunCode:
    def test_exec_code_string(self, monkeypatch, capsys):
        """Executing a code string prints the result."""
        monkeypatch.setattr(
            cli, "PyMOLConnection", lambda: FakeConnection(execute_result="hello")
        )
        args = _make_args(code="print('hello')")
        ret = cli.do_run_code(args)

        assert ret == 0
        assert capsys.readouterr().out.strip() == "hello"

    def test_exec_from_file(self, monkeypatch, capsys, tmp_path):
        """The -f flag reads code from a file and executes it."""
        script = tmp_path / "test_script.py"
        script.write_text("cmd.fetch('1ubq')")

        monkeypatch.setattr(
            cli, "PyMOLConnection", lambda: FakeConnection(execute_result="fetched")
        )
        args = _make_args(file=str(script))
        ret = cli.do_run_code(args)

        assert ret == 0
        assert "fetched" in capsys.readouterr().out

    def test_exec_at_file_syntax(self, monkeypatch, capsys, tmp_path):
        """@path reads code from a file and executes it."""
        script = tmp_path / "run.py"
        script.write_text("print(1)")

        monkeypatch.setattr(
            cli, "PyMOLConnection", lambda: FakeConnection(execute_result="1")
        )
        args = _make_args(code=f"@{script}")
        ret = cli.do_run_code(args)

        assert ret == 0
        assert "1" in capsys.readouterr().out

    def test_exec_json_output(self, monkeypatch, capsys):
        """--json wraps output in a JSON envelope."""
        monkeypatch.setattr(
            cli, "PyMOLConnection", lambda: FakeConnection(execute_result="data")
        )
        args = _make_args(code="x", json_output=True)
        ret = cli.do_run_code(args)

        assert ret == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed == {"status": "success", "output": "data"}

    def test_exec_json_error(self, monkeypatch, capsys):
        """--json + connection failure produces a JSON error envelope."""
        monkeypatch.setattr(
            cli,
            "PyMOLConnection",
            lambda: FakeConnection(connect_error=ConnectionError("refused")),
        )
        args = _make_args(code="x", json_output=True)
        ret = cli.do_run_code(args)

        assert ret == 1
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["status"] == "error"
        assert "refused" in parsed["error"]

    def test_exec_no_code_returns_error(self, monkeypatch, capsys):
        """No code provided -> error message, returns 1."""
        # Provide a fake stdin with a fileno, then mark it as a TTY.
        fake_stdin = type(
            "FakeStdin", (), {"fileno": lambda self: 0}
        )()
        monkeypatch.setattr(sys, "stdin", fake_stdin)
        monkeypatch.setattr("os.isatty", lambda _: True)
        args = _make_args(code=None)
        ret = cli.do_run_code(args)

        assert ret == 1
        captured = capsys.readouterr()
        assert "No code provided" in captured.err or "No code provided" in captured.out

    def test_exec_from_stdin(self, monkeypatch, capsys):
        """When code is None and stdin is not a TTY, reads from stdin."""
        monkeypatch.setattr("os.isatty", lambda _: False)
        fake_stdin = type(
            "FakeStdin",
            (),
            {
                "read": lambda self: "print('stdin')",
                "fileno": lambda self: 0,
            },
        )()
        monkeypatch.setattr(sys, "stdin", fake_stdin)
        monkeypatch.setattr(
            cli, "PyMOLConnection", lambda: FakeConnection(execute_result="stdin")
        )
        args = _make_args(code=None)
        ret = cli.do_run_code(args)

        assert ret == 0
        assert "stdin" in capsys.readouterr().out

    def test_exec_file_not_found(self, monkeypatch, capsys, tmp_path):
        """When -f points to a nonexistent file, returns error."""
        args = _make_args(file=str(tmp_path / "nonexistent.py"))
        ret = cli.do_run_code(args)

        assert ret == 1
        captured = capsys.readouterr()
        assert "Cannot read file" in captured.err or "Cannot read file" in captured.out


# ---------------------------------------------------------------------------
# check_status / test_connection error paths
# ---------------------------------------------------------------------------


class TestStatusAndTestErrors:
    def test_check_status_connection_error(self, monkeypatch, capsys):
        """check_status returns 1 when connection fails."""
        monkeypatch.setattr(
            cli,
            "PyMOLConnection",
            lambda: FakeConnection(connect_error=ConnectionError("down")),
        )
        ret = cli.check_status()

        assert ret == 1
        assert "Not available" in capsys.readouterr().out

    def test_test_connection_error(self, monkeypatch, capsys):
        """test_connection returns 1 and prints error on failure."""
        monkeypatch.setattr(
            cli,
            "PyMOLConnection",
            lambda: FakeConnection(connect_error=ConnectionError("refused")),
        )
        ret = cli.test_connection()

        assert ret == 1
        assert "Connection failed" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# show_info
# ---------------------------------------------------------------------------


class TestShowInfo:
    def test_show_info_text(self, tmp_home, monkeypatch, capsys):
        """Text output includes version, paths."""
        monkeypatch.setattr(cli, "find_pymol_command", lambda: ["/usr/bin/pymol"])
        ret = cli.show_info()

        assert ret == 0
        out = capsys.readouterr().out
        assert "Version:" in out
        assert "Plugin:" in out
        assert "Wrapper:" in out

    def test_show_info_json(self, tmp_home, monkeypatch, capsys):
        """json_output=True produces valid JSON with expected keys."""
        monkeypatch.setattr(cli, "find_pymol_command", lambda: ["/usr/bin/pymol"])
        ret = cli.show_info(json_output=True)

        assert ret == 0
        parsed = json.loads(capsys.readouterr().out)
        assert "version" in parsed
        assert "plugin_path" in parsed
        assert "pymolrc_path" in parsed
        assert "wrapper_path" in parsed
        assert "config" in parsed


# ---------------------------------------------------------------------------
# do_launch
# ---------------------------------------------------------------------------


class TestDoLaunch:
    def test_do_launch_new_process(self, monkeypatch, capsys):
        """do_launch reports the PID when launching a new process."""
        import argparse

        class FakeProcess:
            pid = 12345

        monkeypatch.setattr(
            cli,
            "connect_or_launch",
            lambda file_path=None, headless=False: (FakeConnection(), FakeProcess()),
        )
        args = argparse.Namespace(file=None, headless=False)
        ret = cli.do_launch(args)

        assert ret == 0
        assert "12345" in capsys.readouterr().out

    def test_do_launch_existing_instance(self, monkeypatch, capsys):
        """do_launch reports connecting to existing when process is None."""
        import argparse

        monkeypatch.setattr(
            cli,
            "connect_or_launch",
            lambda file_path=None, headless=False: (FakeConnection(), None),
        )
        args = argparse.Namespace(file=None, headless=False)
        ret = cli.do_launch(args)

        assert ret == 0
        assert "existing" in capsys.readouterr().out.lower()

    def test_do_launch_error(self, monkeypatch, capsys):
        """do_launch returns 1 on exception."""
        import argparse

        def boom(**kwargs):
            raise RuntimeError("no pymol")

        monkeypatch.setattr(cli, "connect_or_launch", boom)
        args = argparse.Namespace(file=None, headless=False)
        ret = cli.do_launch(args)

        assert ret == 1
        assert "no pymol" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


class TestUninstall:
    def test_uninstall_removes_plugin_and_bridge_home(
        self, tmp_home, monkeypatch, capsys
    ):
        """uninstall removes plugin block and local bridge directory."""
        rc_path = tmp_home / ".pymolrc"
        rc_path.write_text(
            "set ray_shadow, 0\n# pymol-agent-bridge\nrun /tmp/pymol_agent_bridge/plugin.py\n"
        )
        bridge_home = tmp_home / ".pymol-agent-bridge"
        bridge_home.mkdir(parents=True)
        (bridge_home / "config.json").write_text("{}")

        monkeypatch.setattr(cli, "find_pymolrc_path", lambda: rc_path)
        monkeypatch.setattr(cli, "WRAPPER_DIR", bridge_home / "bin")

        import argparse

        ret = cli.do_uninstall(argparse.Namespace(yes=True))
        out = capsys.readouterr().out

        assert ret == 0
        assert "# pymol-agent-bridge" not in rc_path.read_text()
        assert "pymol_agent_bridge" not in rc_path.read_text()
        assert not bridge_home.exists()
        assert "Uninstall complete." in out

    def test_uninstall_noninteractive_requires_yes(
        self, tmp_home, monkeypatch, capsys
    ):
        """uninstall exits with error in non-interactive mode without --yes."""
        rc_path = tmp_home / ".pymolrc"
        monkeypatch.setattr(cli, "find_pymolrc_path", lambda: rc_path)
        monkeypatch.setattr("os.isatty", lambda _: False)

        import argparse

        ret = cli.do_uninstall(argparse.Namespace(yes=False))
        err = capsys.readouterr().err

        assert ret == 1
        assert "without --yes" in err


# ---------------------------------------------------------------------------
# main() dispatch
# ---------------------------------------------------------------------------


class TestMainDispatch:
    def test_no_command_shows_help(self, monkeypatch, capsys):
        """No subcommand -> prints help, returns 0."""
        monkeypatch.setattr(sys, "argv", ["pymol-agent-bridge"])
        ret = cli.main()

        assert ret == 0
        assert "usage:" in capsys.readouterr().out.lower()

    def test_dispatches_status(self, monkeypatch):
        """'status' subcommand calls check_status."""
        monkeypatch.setattr(sys, "argv", ["pymol-agent-bridge", "status"])
        called = {"yes": False}

        def fake_check_status():
            called["yes"] = True
            return 0

        monkeypatch.setattr(cli, "check_status", fake_check_status)
        cli.main()
        assert called["yes"]

    def test_run_code_alias(self, monkeypatch):
        """'run-code' is silently rewritten to 'exec'."""
        monkeypatch.setattr(sys, "argv", ["pymol-agent-bridge", "run-code", "print(1)"])
        called = {"yes": False}

        def fake_do_run_code(args):
            called["yes"] = True
            return 0

        monkeypatch.setattr(cli, "do_run_code", fake_do_run_code)
        cli.main()
        assert called["yes"]

    def test_dispatches_uninstall(self, monkeypatch):
        """'uninstall' subcommand calls do_uninstall."""
        monkeypatch.setattr(sys, "argv", ["pymol-agent-bridge", "uninstall", "--yes"])
        called = {"yes": False}

        def fake_do_uninstall(args):
            called["yes"] = True
            assert args.yes is True
            return 0

        monkeypatch.setattr(cli, "do_uninstall", fake_do_uninstall)
        cli.main()
        assert called["yes"]
