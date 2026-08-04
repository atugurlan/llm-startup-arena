from llm_startup_arena.config import AppConfig


def test_app_config_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")
    monkeypatch.setenv("MODEL_COMPANY_A", "test-model")
    monkeypatch.setenv("TOTAL_ROUNDS", "7")

    config = AppConfig.from_env()

    assert config.ollama_base_url == "http://ollama.test:11434"
    assert config.models[0] == "test-model"
    assert config.game.total_rounds == 7
