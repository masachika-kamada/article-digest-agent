from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    provider: Literal["openai", "foundry"] = Field(
        default="openai",
        validation_alias="ARTICLE_AGENT_PROVIDER",
    )
    model: str = Field(
        default="gpt-4.1-mini",
        validation_alias=AliasChoices(
            "ARTICLE_AGENT_MODEL",
            "OPENAI_CHAT_MODEL",
            "FOUNDRY_MODEL_DEPLOYMENT_NAME",
        ),
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )
    foundry_project_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "FOUNDRY_PROJECT_ENDPOINT",
            "AZURE_AI_PROJECT_ENDPOINT",
        ),
    )

    @model_validator(mode="after")
    def validate_provider_settings(self) -> "Settings":
        if self.provider == "openai" and self.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required when provider is 'openai'")
        if self.provider == "foundry" and not self.foundry_project_endpoint:
            raise ValueError("FOUNDRY_PROJECT_ENDPOINT is required when provider is 'foundry'")
        return self
