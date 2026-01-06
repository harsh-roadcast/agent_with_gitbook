#!/usr/bin/env python3
"""
GitBook documentation ingester.

Parses JSONL documents from GitBook export, chunks them, generates embeddings,
and prepares for bulk indexing into Elasticsearch.
"""
import json
import logging
import sys
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 128) -> List[str]:
    """
    Split text into overlapping chunks for better context preservation.
    
    Args:
        text: Text to chunk
        chunk_size: Max chars per chunk
        overlap: Overlap between chunks in chars
    
    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap if end < len(text) else end
    
    return chunks


def parse_gitbook_jsonl(jsonl_path: str) -> List[Dict[str, Any]]:
    """
    Parse GitBook JSONL export into structured documents with metadata.
    
    Args:
        jsonl_path: Path to .jsonl file
    
    Returns:
        List of documents ready for indexing
    """
    documents = []
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            
            try:
                raw_doc = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Skipping malformed JSON at line {line_num}: {e}")
                continue
            
            url = raw_doc.get('url', '')
            title = raw_doc.get('title', 'Untitled')
            content = raw_doc.get('content', '')
            source = raw_doc.get('source', 'gitbook')
            
            # Extract module/section from URL
            # Example: https://roadcast.gitbook.io/roadcast-docs/getting-started
            parts = url.split('/')
            module = parts[-1] if len(parts) > 1 else 'general'
            
            # Skip empty content
            if not content or len(content.strip()) < 10:
                logger.debug(f"Skipping document '{title}' (too short or empty)")
                continue
            
            # Chunk content
            chunks = chunk_text(content, chunk_size=512, overlap=128)
            
            # Create a document for each chunk
            for chunk_idx, chunk in enumerate(chunks, 1):
                doc = {
                    "url": url,
                    "title": title,
                    "module": module,
                    "section": title.split('|')[0].strip() if '|' in title else title,
                    "content": chunk,
                    "chunk_id": chunk_idx,
                    "source": source,
                    "doc_type": "gitbook"
                }
                documents.append(doc)
            
            logger.info(f"Processed '{title}' → {len(chunks)} chunks")
    
    return documents


def generate_embeddings(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate embeddings for document chunks using SentenceTransformer.
    
    Args:
        documents: List of documents with 'content' field
    
    Returns:
        Documents with added 'embedding' field
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
        sys.exit(1)
    
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    texts = [doc['content'] for doc in documents]
    embeddings = model.encode(texts, show_progress_bar=True).tolist()
    
    for doc, embedding in zip(documents, embeddings):
        doc['embedding'] = embedding
    
    logger.info(f"Generated {len(documents)} embeddings")
    return documents


def save_for_bulk_index(documents: List[Dict[str, Any]], output_path: str) -> None:
    """
    Save documents in Elasticsearch bulk indexing format.
    
    Args:
        documents: Documents with embeddings
        output_path: Output JSONL file path
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for doc in documents:
            # Bulk index action line
            action = {
                "index": {
                    "_index": "gitbook_docs",
                    "_id": f"{doc['module']}_{doc['title'].replace(' ', '_')}_{doc['chunk_id']}"
                }
            }
            f.write(json.dumps(action) + '\n')
            # Document line
            f.write(json.dumps(doc) + '\n')
    
    logger.info(f"Saved {len(documents)} documents to {output_path}")


def ingest_gitbook(input_jsonl: str, output_jsonl: str = None) -> List[Dict[str, Any]]:
    """
    Complete pipeline: parse → chunk → embed → format for bulk indexing.
    
    Args:
        input_jsonl: Path to GitBook JSONL export
        output_jsonl: Path to save bulk-index formatted JSONL (optional)
    
    Returns:
        List of documents ready for indexing
    """
    logger.info(f"Starting GitBook ingestion from {input_jsonl}")
    
    # Parse documents
    documents = parse_gitbook_jsonl(input_jsonl)
    logger.info(f"Parsed {len(documents)} document chunks")
    
    # Generate embeddings
    documents = generate_embeddings(documents)
    
    # Save if output path provided
    if output_jsonl:
        save_for_bulk_index(documents, output_jsonl)
    
    return documents


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest GitBook docs into Elasticsearch")
    parser.add_argument("input", help="Path to GitBook JSONL export")
    parser.add_argument("--output", help="Output path for bulk-index formatted JSONL")
    parser.add_argument("--log-level", default="INFO", help="Log level (DEBUG, INFO, WARNING)")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    ingest_gitbook(args.input, args.output)
