"""Utility script to crawl GitBook content and dump it into JSON."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.gitbook_crawler import GitBookCrawler, GitBookCrawlerConfig  # noqa: E402


def dump_gitbook(output_path: pathlib.Path, max_pages: int | None, start_path: str) -> dict:
    """Crawl GitBook docs and persist them as JSON array."""
    config = GitBookCrawlerConfig()
    if max_pages is not None:
        config.max_pages = max_pages

    crawler = GitBookCrawler(config)
    documents = crawler.crawl(start_path=start_path)

    payload = {
        "space": config.base_url.split("/")[-1],
        "base_url": config.base_url,
        "pages_ingested": len(documents),
        "documents": documents,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl GitBook and export JSON snapshot")
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPO_ROOT / "gitbook_dump.json"),
        help="Destination JSON file"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional limit on number of pages to crawl"
    )
    parser.add_argument(
        "--start-path",
        type=str,
        default="/documentation",
        help="Start path within the GitBook space"
    )
    args = parser.parse_args()

    output_path = pathlib.Path(args.output)
    summary = dump_gitbook(output_path, args.max_pages, args.start_path)
    print(
        f"Saved {summary['pages_ingested']} GitBook documents to {output_path}"
    )


if __name__ == "__main__":
    main()
