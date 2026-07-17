"""Unit tests for configuration and Gemini client helpers."""

import os

import pytest


def test_config_loads_gemini_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    import sys
    if "config" in sys.modules:
        del sys.modules["config"]
    import config

    assert config.GEMINI_API_KEY == "test-key-123"


def test_config_default_port(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("FLASK_PORT", raising=False)
    import sys
    if "config" in sys.modules:
        del sys.modules["config"]
    import config

    assert config.FLASK_PORT == 5000


def test_config_custom_port(monkeypatch):
    monkeypatch.setenv("PORT", "8080")
    import sys
    if "config" in sys.modules:
        del sys.modules["config"]
    import config

    assert config.FLASK_PORT == 8080


def test_config_debug_mode(monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "true")
    import sys
    if "config" in sys.modules:
        del sys.modules["config"]
    import config

    assert config.FLASK_DEBUG is True


def test_config_debug_off_by_default(monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "false")
    import sys
    if "config" in sys.modules:
        del sys.modules["config"]
    import config

    assert config.FLASK_DEBUG is False


def test_get_gemini_response_returns_fallback_without_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    import sys
    if "config" in sys.modules:
        del sys.modules["config"]
    import config

    result = config.get_gemini_response("system", "user")
    assert "unavailable" in result.lower()


def test_get_gemini_response_json_mode_returns_error_dict(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    import sys
    if "config" in sys.modules:
        del sys.modules["config"]
    import config

    result = config.get_gemini_response("system", "user", json_mode=True)
    assert isinstance(result, dict)
    assert "error" in result


def test_get_gemini_response_with_placeholder_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    import sys
    if "config" in sys.modules:
        del sys.modules["config"]
    import config

    result = config.get_gemini_response("system", "user")
    assert "unavailable" in result.lower()


def test_clean_json_payload_strips_markdown_fences():
    import config

    input_text = '```json\n{"key": "value"}\n```'
    result = config._clean_json_payload(input_text)
    assert result == '{"key": "value"}'


def test_clean_json_payload_handles_no_fences():
    import config

    input_text = '{"key": "value"}'
    result = config._clean_json_payload(input_text)
    assert result == '{"key": "value"}'


def test_clean_json_payload_handles_empty_input():
    import config

    result = config._clean_json_payload("")
    assert result == ""


def test_clean_json_payload_handles_whitespace():
    import config

    input_text = '```json\n{"key": "value"}\n```'
    result = config._clean_json_payload(input_text)
    assert result == '{"key": "value"}'


def test_database_config_defaults_to_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    import sys
    if "database" in sys.modules:
        del sys.modules["database"]
    import database

    assert "sqlite" in database.NORMALIZED_DATABASE_URL


def test_database_config_handles_heroku_postgres():
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        pytest.skip("psycopg2 not installed")

    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "postgres://user:pass@host/db"
    try:
        import sys
        if "database" in sys.modules:
            del sys.modules["database"]
        import database
        assert "postgresql" in database.NORMALIZED_DATABASE_URL
        assert "postgres://" not in database.NORMALIZED_DATABASE_URL
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
