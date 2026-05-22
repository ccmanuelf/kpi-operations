"""Regression tests for backend.config.Settings env-file robustness."""

from backend.config import Settings


def test_settings_ignores_unknown_dotenv_keys(tmp_path):
    """Settings must not crash when its .env carries non-field keys.

    The repo-root .env is shared with Docker Compose, which references
    orchestration-only vars (DEMO_MODE, RUN_MIGRATIONS) that are not Settings
    fields. pydantic-settings forbids extra keys read from a dotenv FILE unless
    extra="ignore" is set, so without it the backend crashes at import whenever
    it is started from a directory whose .env holds such keys (e.g. pytest /
    uvicorn run from the repo root). Regression guard for that fix.
    """
    env = tmp_path / ".env"
    env.write_text(
        "SECRET_KEY=regression-secret-value-1234567890\n"
        "RUN_MIGRATIONS=true\n"
        "DEMO_MODE=false\n"
        "TOTALLY_UNKNOWN_KEY=value\n"
    )

    settings = Settings(_env_file=str(env))

    assert settings.SECRET_KEY == "regression-secret-value-1234567890"
    assert not hasattr(settings, "TOTALLY_UNKNOWN_KEY")
    assert not hasattr(settings, "RUN_MIGRATIONS")
