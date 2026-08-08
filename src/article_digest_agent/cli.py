import argparse
import asyncio
import sys
from pathlib import Path

from pydantic import ValidationError

from article_digest_agent.agent import ArticleDigestService
from article_digest_agent.config import Settings
from article_digest_agent.fetcher import ArticleFetcher
from article_digest_agent.providers import create_chat_client


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="article-digest-agent",
        description="技術記事を取得し、Microsoft Agent Frameworkで比較します。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="LLMを使わず記事本文を抽出する")
    fetch_parser.add_argument("urls", nargs="+", help="取得する公開HTTP(S) URL")

    digest_parser = subparsers.add_parser("digest", help="記事を比較してMarkdownを生成する")
    digest_parser.add_argument("urls", nargs="+", help="比較する公開HTTP(S) URL")
    digest_parser.add_argument("-o", "--output", type=Path, help="Markdownの保存先")
    digest_parser.add_argument("--provider", choices=["openai", "foundry"])
    digest_parser.add_argument("--model", help="使用するモデルまたはデプロイ名")

    return parser


async def _run_fetch(urls: list[str]) -> None:
    fetcher = ArticleFetcher()
    for url in urls:
        article = await fetcher.fetch(url)
        print(article.model_dump_json(indent=2))


async def _run_digest(args: argparse.Namespace) -> None:
    overrides = {
        key: value
        for key, value in {"provider": args.provider, "model": args.model}.items()
        if value is not None
    }
    settings = Settings(**overrides)
    service = ArticleDigestService(create_chat_client(settings))
    report = await service.digest(args.urls)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
        print(f"Saved report to {args.output}")
    else:
        print(report)


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "fetch":
            asyncio.run(_run_fetch(args.urls))
        else:
            asyncio.run(_run_digest(args))
    except (ValidationError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
