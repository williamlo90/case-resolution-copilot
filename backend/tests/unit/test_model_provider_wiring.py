from fastapi.testclient import TestClient

from app.analysis.ai_assisted_decision_engine import OpenAIAssistedDecisionEngine
from app.analysis.deterministic_decision_engine import DeterministicDecisionEngine
from app.config import Settings
from app.main import create_app


def test_default_runtime_uses_deterministic_decision_controls() -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    assert isinstance(app.state.decision_engine, DeterministicDecisionEngine)


def test_openai_runtime_wraps_deterministic_decision_controls() -> None:
    app = create_app(
        Settings(
            environment="test",
            model_provider="openai",
            openai_api_key="sk-test-placeholder",
            _env_file=None,
        )
    )

    with TestClient(app):
        assert isinstance(app.state.decision_engine, OpenAIAssistedDecisionEngine)
