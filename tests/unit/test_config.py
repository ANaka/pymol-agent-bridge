"""Unit tests for config persistence."""

from pymol_agent_bridge import connection


class TestConfig:
    def test_save_and_load(self, tmp_home):
        """Config roundtrip: save then load."""
        connection.save_config({"python_path": "/usr/bin/python3"})
        result = connection.get_config()
        assert result == {"python_path": "/usr/bin/python3"}

    def test_get_config_missing_file(self, tmp_home):
        """Missing config file returns empty dict."""
        assert connection.get_config() == {}

    def test_get_config_malformed_json(self, tmp_home):
        """Malformed JSON returns empty dict."""
        connection.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        connection.CONFIG_FILE.write_text("not json{{{")
        assert connection.get_config() == {}
