"""CLI helper to crawl GitBook documentation and export JSONL."""
from __future__ import annotations

import argparse
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.gitbook_service import crawl_gitbook_documents, save_documents_as_jsonl  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl GitBook docs and save JSONL text snapshots")
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPO_ROOT / "gitbook_docs.jsonl"),
        help="Destination JSONL file"
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
        help="Path under the GitBook space to start crawling"
    )
    args = parser.parse_args()

    documents = crawl_gitbook_documents(
        start_path=args.start_path,
        max_pages=args.max_pages
    )
    save_documents_as_jsonl(documents, args.output)

    print(f"Saved {len(documents)} GitBook documents to {args.output}")


if __name__ == "__main__":
    main()
