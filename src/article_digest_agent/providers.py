from typing import Any

from agent_framework.foundry import FoundryChatClient
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import AzureCliCredential

from article_digest_agent.config import Settings


def create_chat_client(settings: Settings) -> Any:
    if settings.provider == "foundry":
        return FoundryChatClient(
            project_endpoint=settings.foundry_project_endpoint,
            model=settings.model,
            credential=AzureCliCredential(),
        )

    return OpenAIChatClient(
        model=settings.model,
        api_key=settings.openai_api_key.get_secret_value() if settings.openai_api_key else None,
    )
