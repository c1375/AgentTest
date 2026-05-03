from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Placeholder lets the AsyncAnthropic client wire up cleanly at startup
    # before the operator drops a real key into .env. Mirrors MyKefi's
    # `${ANTHROPIC_API_KEY:sk-placeholder-for-startup}` pattern in
    # application.yml. Real API calls will fail until a valid key is set.
    anthropic_api_key: str = "sk-placeholder-for-startup"
    github_token: str = ""

    data_dir: Path = Path("data")
    configs_dir: Path = Path("configs")


settings = Settings()
