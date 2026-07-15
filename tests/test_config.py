from assistant.config import load_settings


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("WHATSAPP_TOKEN", "tok")
    monkeypatch.setenv("ADMIN_PHONE", "15551234567")
    s = load_settings()
    assert s.whatsapp_token == "tok"
    assert s.admin_phone == "15551234567"


def test_load_settings_defaults(monkeypatch):
    for k in ("DB_PATH", "DEFAULT_TIMEZONE", "GEMINI_MODEL"):
        monkeypatch.delenv(k, raising=False)
    s = load_settings()
    assert s.db_path == "assistant.db"
    assert s.default_tz == "America/Los_Angeles"
    assert s.gemini_model == "gemini-2.5-flash"
