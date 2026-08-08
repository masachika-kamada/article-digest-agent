import asyncio
import ipaddress
import socket
from collections.abc import AsyncIterator
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
import trafilatura

from article_digest_agent.models import ArticleDocument


class UnsafeUrlError(ValueError):
    pass


class ArticleFetchError(RuntimeError):
    pass


class UrlGuard:
    async def validate(self, url: str) -> str:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            raise UnsafeUrlError("Only http and https URLs are allowed")
        if parsed.username or parsed.password:
            raise UnsafeUrlError("URLs containing credentials are not allowed")
        if not parsed.hostname:
            raise UnsafeUrlError("URL must contain a host")

        hostname = parsed.hostname.rstrip(".").lower()
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise UnsafeUrlError("Localhost URLs are not allowed")

        try:
            addresses = [ipaddress.ip_address(hostname)]
        except ValueError:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            try:
                records = await asyncio.to_thread(
                    socket.getaddrinfo,
                    hostname,
                    port,
                    type=socket.SOCK_STREAM,
                )
            except socket.gaierror as error:
                raise UnsafeUrlError(f"Could not resolve URL host: {hostname}") from error
            addresses = list({ipaddress.ip_address(record[4][0]) for record in records})

        if not addresses or any(not address.is_global for address in addresses):
            raise UnsafeUrlError("URL host resolves to a non-public address")

        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


class ArticleFetcher:
    def __init__(
        self,
        *,
        guard: UrlGuard | None = None,
        max_download_bytes: int = 2_000_000,
        max_content_characters: int = 24_000,
        max_redirects: int = 5,
    ) -> None:
        self._guard = guard or UrlGuard()
        self._max_download_bytes = max_download_bytes
        self._max_content_characters = max_content_characters
        self._max_redirects = max_redirects

    async def fetch(self, url: str) -> ArticleDocument:
        current_url = await self._guard.validate(url)
        headers = {"User-Agent": "article-digest-agent/0.1 (+local learning project)"}

        async with httpx.AsyncClient(
            follow_redirects=False,
            headers=headers,
            timeout=httpx.Timeout(20.0),
        ) as client:
            for redirect_count in range(self._max_redirects + 1):
                async with client.stream("GET", current_url) as response:
                    if response.has_redirect_location:
                        if redirect_count == self._max_redirects:
                            raise ArticleFetchError("Too many redirects")
                        current_url = await self._guard.validate(
                            urljoin(current_url, response.headers["location"])
                        )
                        continue

                    response.raise_for_status()
                    self._validate_content_type(response.headers.get("content-type", ""))
                    payload = await self._read_limited(response.aiter_bytes())
                    encoding = response.encoding or "utf-8"
                    html = payload.decode(encoding, errors="replace")
                    return self._extract(current_url, html)

        raise ArticleFetchError("Unable to fetch article")

    async def _read_limited(self, chunks: AsyncIterator[bytes]) -> bytes:
        payload = bytearray()
        async for chunk in chunks:
            payload.extend(chunk)
            if len(payload) > self._max_download_bytes:
                raise ArticleFetchError(
                    f"Article exceeds the {self._max_download_bytes}-byte download limit"
                )
        return bytes(payload)

    @staticmethod
    def _validate_content_type(content_type: str) -> None:
        media_type = content_type.partition(";")[0].strip().lower()
        if media_type and media_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise ArticleFetchError(f"Unsupported content type: {media_type}")

    def _extract(self, url: str, html: str) -> ArticleDocument:
        metadata = trafilatura.extract_metadata(html)
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
        content = (extracted or trafilatura.html2txt(html)).strip()
        if not content:
            raise ArticleFetchError("No readable article content was found")

        character_count = len(content)
        truncated = character_count > self._max_content_characters
        if truncated:
            content = content[: self._max_content_characters].rstrip()

        parsed = urlsplit(url)
        title = metadata.title if metadata and metadata.title else parsed.hostname or url
        return ArticleDocument(
            url=url,
            title=title,
            author=metadata.author if metadata else None,
            published_at=metadata.date if metadata else None,
            content=content,
            truncated=truncated,
            character_count=character_count,
        )
