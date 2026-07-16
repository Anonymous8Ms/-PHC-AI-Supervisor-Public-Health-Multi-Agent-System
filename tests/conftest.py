import importlib
import sys

import pytest


def _reload_project_modules():
    module_names = [
        "app",
        "config",
        "database",
        "demo_data",
        "models",
        "agents",
        "agents.ingestion_agent",
        "agents.prediction_agent",
        "agents.supervisor_agent",
        "agents.verification_agent",
    ]
    for module_name in module_names:
        if module_name in sys.modules:
            del sys.modules[module_name]


@pytest.fixture()
def loaded_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_health_agent.db"))
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("FLASK_DEBUG", "False")
    monkeypatch.setenv("PORT", "5000")
    _reload_project_modules()
    return importlib.import_module("app")


@pytest.fixture()
def client(loaded_app):
    return loaded_app.app.test_client()


@pytest.fixture()
def db_session(loaded_app):
    session = loaded_app.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        loaded_app.SessionLocal.remove()
