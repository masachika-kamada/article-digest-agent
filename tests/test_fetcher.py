import httpx
import pytest
import respx

from article_digest_agent.fetcher import ArticleFetcher, UnsafeUrlError, UrlGuard


class AllowAllGuard(UrlGuard):
    async def validate(self, url: str) -> str:
        return url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost/admin",
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://user:password@example.com/article",
    ],
)
async def test_url_guard_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        await UrlGuard().validate(url)


@respx.mock
async def test_fetch_extracts_article_metadata_and_content() -> None:
    url = "https://example.com/article"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="""
                <html>
                  <head>
                    <title>Agent Framework入門</title>
                    <meta name="author" content="Example Author">
                    <meta property="article:published_time" content="2026-08-08">
                  </head>
                                    <body>
                                        <article>
                                            <h1>Agent Framework入門</h1>
                                            <p>これは十分に長い記事本文です。</p>
                                        </article>
                                    </body>
                </html>
            """,
        )
    )

    article = await ArticleFetcher(guard=AllowAllGuard()).fetch(url)

    assert article.title == "Agent Framework入門"
    assert article.author == "Example Author"
    assert "十分に長い記事本文" in article.content
    assert article.character_count == len(article.content)
