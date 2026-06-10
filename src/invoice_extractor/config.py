"""Application configuration, loaded from the environment / ``.env``.

All secrets and environment-specific values live here, never in source. Copy
``.env.example`` to ``.env`` and fill in the Azure credentials to enable the LLM
(Pipeline A) and Azure Document Intelligence (Pipeline C) pipelines. The rules
pipeline (Pipeline B) needs none of these and always runs.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view over the environment. Field names map to upper-cased env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Pipeline A — Azure OpenAI (LLM structured extraction)
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-10-21"

    # Pipeline C — Azure Document Intelligence (optional, off by default)
    azure_di_endpoint: str | None = None
    azure_di_key: str | None = None

    # Behaviour
    llm_temperature: float = 0.0
    tesseract_cmd: str | None = None  # path to the tesseract binary, if not on PATH

    @property
    def llm_enabled(self) -> bool:
        """True when Pipeline A has the credentials it needs to run."""
        return bool(
            self.azure_openai_endpoint
            and self.azure_openai_api_key
            and self.azure_openai_deployment
        )

    @property
    def azure_di_enabled(self) -> bool:
        """True when Pipeline C has the credentials it needs to run."""
        return bool(self.azure_di_endpoint and self.azure_di_key)


def load_settings() -> Settings:
    """Load settings from the environment / ``.env``."""
    return Settings()
