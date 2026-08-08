from types import SimpleNamespace

import pytest

from article_digest_agent.agent import ArticleDigestService, ArticleTools
from article_digest_agent.models import ArticleDocument


class FakeFetcher:
    def __init__(self) -> None:
        self.requested_urls: list[str] = []

    async def fetch(self, url: str) -> ArticleDocument:
        self.requested_urls.append(url)
        return ArticleDocument(
            url=url,
            title="Example",
            content="Article content",
            character_count=15,
        )


class FakeAgent:
    def __init__(self) -> None:
        self.prompt = ""

    async def run(self, prompt: str) -> SimpleNamespace:
        self.prompt = prompt
        return SimpleNamespace(text="# 技術記事ダイジェスト\n\n比較結果")


class FakeChatClient:
    def __init__(self) -> None:
        self.agent = FakeAgent()
        self.agent_options: dict[str, object] = {}

    def as_agent(self, **kwargs: object) -> FakeAgent:
        self.agent_options = kwargs
        return self.agent


async def test_article_tool_fetches_only_user_supplied_url() -> None:
    fetcher = FakeFetcher()
    tools = ArticleTools(["https://example.com/allowed"], fetcher=fetcher)  # type: ignore[arg-type]

    result = await tools.fetch_article("https://example.com/allowed")

    assert '"title":"Example"' in result.replace(" ", "").replace("\n", "")
    assert fetcher.requested_urls == ["https://example.com/allowed"]

    with pytest.raises(ValueError, match="not supplied"):
        await tools.fetch_article("https://example.com/injected")


async def test_digest_builds_agent_with_tool_and_exact_urls() -> None:
    client = FakeChatClient()
    urls = ["https://example.com/one", "https://example.com/two"]
    service = ArticleDigestService(client)

    report = await service.digest(urls)

    assert report.startswith("# 技術記事ダイジェスト")
    assert all(url in client.agent.prompt for url in urls)
    assert client.agent_options["name"] == "ArticleDigestAgent"
    assert len(client.agent_options["tools"]) == 1  # type: ignore[arg-type]


async def test_digest_rejects_duplicate_urls() -> None:
    service = ArticleDigestService(FakeChatClient())

    with pytest.raises(ValueError, match="Duplicate"):
        await service.digest(["https://example.com/one", "https://example.com/one"])
