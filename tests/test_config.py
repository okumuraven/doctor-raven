from doctor_raven import config as config_module


def test_load_config_creates_default_file_with_secure_permissions(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_dir / "config.toml")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)

    cfg = config_module.load_config()

    config_path = config_dir / "config.toml"
    assert config_path.exists()
    assert oct(config_path.stat().st_mode)[-3:] == "600"
    assert cfg.ollama_model == "llama3.2"
    assert cfg.gemini_model == "gemini-2.5-flash"
    assert cfg.temp_warn_c == 75.0
    assert cfg.temp_critical_c == 90.0
    assert cfg.workspace_root == "~/PROJECTS"
    assert cfg.lookback_days == 3
    assert cfg.anthropic_api_key is None
    assert cfg.gemini_api_keys == []


def test_load_config_reads_custom_values_and_env_key(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(
        '[llm]\nollama_model = "mistral"\n\n'
        "[system_health]\ntemp_critical_c = 95\n\n"
        '[research]\nworkspace_root = "~/code"\nlookback_days = 7\n'
    )
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)

    cfg = config_module.load_config()

    assert cfg.ollama_model == "mistral"
    assert cfg.temp_critical_c == 95.0
    assert cfg.workspace_root == "~/code"
    assert cfg.lookback_days == 7
    assert cfg.anthropic_api_key == "sk-test"
    assert cfg.gemini_api_keys == ["gm-test"]


def test_load_config_reads_multiple_gemini_keys_for_rotation(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_dir / "config.toml")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEYS", "key-a, key-b ,key-c")

    cfg = config_module.load_config()

    assert cfg.gemini_api_keys == ["key-a", "key-b", "key-c"]


def test_gemini_api_keys_prefers_plural_env_var_over_singular(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_dir / "config.toml")
    monkeypatch.setenv("GEMINI_API_KEY", "singular-key")
    monkeypatch.setenv("GEMINI_API_KEYS", "key-a,key-b")

    cfg = config_module.load_config()

    assert cfg.gemini_api_keys == ["key-a", "key-b"]


def test_discord_webhook_url_defaults_to_none(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_dir / "config.toml")
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    cfg = config_module.load_config()

    assert cfg.discord_webhook_url is None


def test_discord_webhook_url_read_from_env(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_dir / "config.toml")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")

    cfg = config_module.load_config()

    assert cfg.discord_webhook_url == "https://discord.example/webhook"
