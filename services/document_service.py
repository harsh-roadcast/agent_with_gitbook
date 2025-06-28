"""Document processing service for PDF upload and vectorization."""

import os
import tempfile
import logging
import ssl
import urllib.request
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

import requests
from elasticsearch.helpers import bulk, streaming_bulk
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from sentence_transformers import SentenceTransformer

from services.search_service import get_es_client, get_sentence_transformer_model

logger = logging.getLogger(__name__)

# Fix SSL certificate issues on macOS
def _fix_ssl_context():
    """Fix SSL context for macOS certificate issues."""
    try:
        # Create unverified SSL context (use with caution, only for internal tools)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context
    except Exception as e:
        logger.warning(f"Could not create SSL context: {e}")
        return None

class DocumentProcessor:
    """Service for processing documents with Docling and storing in Elasticsearch."""

    def __init__(self):
        self.es_client = get_es_client()
        self.embedding_model = get_sentence_transformer_model()

        # Configure DocumentConverter with minimal dependencies to avoid OCR issues
        try:
            # Create a lightweight converter configuration
            pdf_options = PdfFormatOption(
                # Disable OCR-based features that require model downloads
                ocr_enabled=False,
                extract_images=False
            )

            self.converter = DocumentConverter(
                format_options={
                    "pdf": pdf_options
                }
            )
            logger.info("DocumentConverter initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to create DocumentConverter with OCR disabled: {e}")
            # Fallback to basic converter
            self.converter = DocumentConverter()

        self.index_name = "docling_documents"

    def create_index_if_not_exists(self):
        """Create the Elasticsearch index for documents if it doesn't exist."""
        index_mapping = {
            "mappings": {
                "properties": {
                    "filename": {"type": "keyword"},
                    "chunk_id": {"type": "integer"},
                    "text": {"type": "text"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": 384,  # all-MiniLM-L6-v2 embedding size
                        "index": True,
                        "similarity": "cosine"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "page_number": {"type": "integer"},
                            "chunk_size": {"type": "integer"},
                            "upload_timestamp": {"type": "date"}
                        }
                    }
                }
            }
        }

        try:
            if not self.es_client.indices.exists(index=self.index_name):
                self.es_client.indices.create(index=self.index_name, body=index_mapping)
                logger.info(f"Created Elasticsearch index: {self.index_name}")
            else:
                logger.debug(f"Index {self.index_name} already exists")
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using sentence transformer."""
        try:
            embedding = self.embedding_model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def process_pdf_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Process a PDF file using Docling and store chunks in Elasticsearch.

        Args:
            file_path: Path to the PDF file
            filename: Original filename

        Returns:
            Dictionary with processing results
        """
        try:
            logger.info(f"Starting processing of PDF: {filename}")

            # Ensure index exists
            self.create_index_if_not_exists()

            # Set up SSL context fix for any network requests
            ssl_context = _fix_ssl_context()
            if ssl_context:
                # Apply SSL fix globally
                original_context = ssl._create_default_https_context
                ssl._create_default_https_context = lambda: ssl_context

            try:
                # Convert document with Docling
                logger.info("Converting document with Docling...")
                result = self.converter.convert(file_path)
                doc = result.document

                logger.info(f"Document converted: {len(result.pages) if hasattr(result, 'pages') else 'unknown'} pages")

                # Get text content from document
                if hasattr(doc, 'export_to_markdown'):
                    full_text = doc.export_to_markdown()
                elif hasattr(doc, 'export_to_text'):
                    full_text = doc.export_to_text()
                else:
                    # Fallback: extract text from document structure
                    full_text = str(doc)

                logger.info(f"Extracted text length: {len(full_text)} characters")

                # Use HybridChunker for semantic chunking
                logger.info("Chunking document...")
                try:
                    chunker = HybridChunker(tokenizer="BAAI/bge-small-en-v1.5")
                    chunk_iter = chunker.chunk(doc)
                    chunks = list(chunk_iter)
                except Exception as chunker_error:
                    logger.warning(f"HybridChunker failed: {chunker_error}, falling back to simple chunking")
                    # Fallback to simple text chunking
                    chunk_size = 500
                    overlap = 50
                    chunks = []
                    for i in range(0, len(full_text), chunk_size - overlap):
                        chunk_text = full_text[i:i + chunk_size]
                        if chunk_text.strip():
                            # Create a simple chunk object
                            class SimpleChunk:
                                def __init__(self, text):
                                    self.text = text
                            chunks.append(SimpleChunk(chunk_text))

            finally:
                # Restore original SSL context
                if ssl_context:
                    ssl._create_default_https_context = original_context

            # Prepare documents for bulk indexing
            logger.info("Generating embeddings and preparing for indexing...")
            docs = []
            chunk_count = 0

            for i, chunk in enumerate(chunks):
                text = chunk.text.strip() if hasattr(chunk, 'text') else str(chunk).strip()
                if not text:
                    continue

                chunk_count += 1

                # Generate embedding
                try:
                    embedding = self.generate_embedding(text)
                except Exception as embed_error:
                    logger.warning(f"Failed to generate embedding for chunk {i}: {embed_error}")
                    continue

                # Prepare document for Elasticsearch
                doc_body = {
                    "_index": self.index_name,
                    "_id": f"{filename}_chunk_{i}",
                    "_source": {
                        "filename": filename,
                        "chunk_id": i,
                        "text": text,
                        "embedding": embedding,
                        "metadata": {
                            "chunk_size": len(text),
                            "upload_timestamp": datetime.now().isoformat(),
                            "page_number": getattr(chunk, 'page_number', None) if hasattr(chunk, 'page_number') else None,
                            "chunk_type": getattr(chunk, 'chunk_type', 'text') if hasattr(chunk, 'chunk_type') else 'text',
                            "document_type": "pdf",
                            "processing_method": "docling"
                        }
                    }
                }
                docs.append(doc_body)

                if chunk_count % 10 == 0:
                    logger.debug(f"Processed {chunk_count} chunks")

            # Bulk index documents
            logger.info(f"Indexing {len(docs)} chunks into Elasticsearch...")

            # Use safer bulk indexing with better error handling
            try:
                indexed_count = 0
                failed_count = 0
                failures = []

                # Use streaming bulk with error handling for each document
                for success, info in streaming_bulk(
                    self.es_client,
                    docs,
                    index=self.index_name,
                    chunk_size=100,  # Process in smaller chunks
                    max_retries=2,
                    initial_backoff=1,
                    max_backoff=600,
                    raise_on_error=False,  # Don't raise exceptions, handle errors manually
                    raise_on_exception=False
                ):
                    if success:
                        indexed_count += 1
                    else:
                        failed_count += 1
                        failures.append(info)
                        logger.warning(f"Failed to index document: {info}")

                        # Log detailed error information
                        if isinstance(info, dict):
                            error_info = info.get('index', {}).get('error', {})
                            if error_info:
                                logger.error(f"Indexing error details: {error_info}")

                success = indexed_count

            except Exception as bulk_error:
                logger.error(f"Bulk indexing failed completely: {bulk_error}")
                # Fallback: try indexing documents one by one
                logger.info("Attempting to index documents individually...")

                success = 0
                failures = []

                for doc in docs:
                    try:
                        self.es_client.index(
                            index=doc["_index"],
                            id=doc["_id"],
                            body=doc["_source"]
                        )
                        success += 1
                    except Exception as single_error:
                        failures.append({
                            "doc_id": doc["_id"],
                            "error": str(single_error)
                        })
                        logger.warning(f"Failed to index individual document {doc['_id']}: {single_error}")

            if failures:
                logger.warning(f"Some chunks failed to index: {len(failures)} failures out of {len(docs)} total")
                # Log a few example failures for debugging
                for i, failure in enumerate(failures[:3]):
                    logger.error(f"Index failure {i+1}: {failure}")
            else:
                logger.info(f"All {success} chunks indexed successfully")

            logger.info(f"Processing complete: {success} chunks indexed successfully, {len(failures)} failed")

            return {
                "status": "success" if success > 0 else "error",
                "filename": filename,
                "total_chunks": chunk_count,
                "indexed_chunks": success,
                "failed_chunks": len(failures),
                "pages": len(result.pages) if hasattr(result, 'pages') else 1,
                "errors": failures[:5] if failures else []  # Include first 5 errors for debugging
            }

        except Exception as e:
            logger.error(f"Error processing PDF {filename}: {e}", exc_info=True)
            return {
                "status": "error",
                "filename": filename,
                "error": str(e)
            }

    def search_documents(self, query: str, size: int = 10) -> List[Dict[str, Any]]:
        """
        Search documents using vector similarity.

        Args:
            query: Search query text
            size: Number of results to return

        Returns:
            List of matching document chunks
        """
        try:
            # Generate embedding for query
            query_embedding = self.generate_embedding(query)

            # Elasticsearch query with vector similarity
            es_query = {
                "size": size,
                "query": {
                    "script_score": {
                        "query": {"match_all": {}},
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                            "params": {"query_vector": query_embedding}
                        }
                    }
                },
                "_source": ["filename", "text", "metadata"]
            }

            response = self.es_client.search(index=self.index_name, body=es_query)

            results = []
            for hit in response['hits']['hits']:
                results.append({
                    "filename": hit['_source']['filename'],
                    "text": hit['_source']['text'],
                    "score": hit['_score'],
                    "metadata": hit['_source'].get('metadata', {})
                })

            return results

        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all indexed documents with statistics."""
        try:
            # Aggregation query to get document statistics
            agg_query = {
                "size": 0,
                "aggs": {
                    "documents": {
                        "terms": {
                            "field": "filename",
                            "size": 1000
                        },
                        "aggs": {
                            "chunk_count": {"value_count": {"field": "chunk_id"}},
                            "latest_upload": {"max": {"field": "metadata.upload_timestamp"}}
                        }
                    }
                }
            }

            response = self.es_client.search(index=self.index_name, body=agg_query)

            documents = []
            for bucket in response['aggregations']['documents']['buckets']:
                documents.append({
                    "filename": bucket['key'],
                    "chunk_count": bucket['chunk_count']['value'],
                    "upload_timestamp": bucket['latest_upload']['value_as_string']
                })

            return documents

        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    def extract_document_structure(self, file_path: str) -> Dict[str, Any]:
        """
        Extract detailed structure from document using Docling.

        Args:
            file_path: Path to the document file

        Returns:
            Dictionary with document structure and metadata
        """
        try:
            logger.info(f"Extracting document structure from: {file_path}")

            # Convert document
            result = self.converter.convert(file_path)
            doc = result.document

            # Extract structure information
            structure = {
                "pages": len(result.pages) if hasattr(result, 'pages') else 0,
                "tables": [],
                "headings": [],
                "paragraphs": [],
                "images": [],
                "metadata": {}
            }

            # Extract different document elements
            if hasattr(doc, 'texts'):
                for text_element in doc.texts:
                    if hasattr(text_element, 'tag'):
                        if text_element.tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                            structure["headings"].append({
                                "level": text_element.tag,
                                "text": text_element.text,
                                "page": getattr(text_element, 'page', None)
                            })
                        elif text_element.tag == 'p':
                            structure["paragraphs"].append({
                                "text": text_element.text,
                                "page": getattr(text_element, 'page', None)
                            })

            # Extract tables
            if hasattr(doc, 'tables'):
                for table in doc.tables:
                    table_data = {
                        "rows": len(table.data) if hasattr(table, 'data') else 0,
                        "columns": len(table.data[0]) if hasattr(table, 'data') and table.data else 0,
                        "page": getattr(table, 'page', None),
                        "data": table.data if hasattr(table, 'data') else []
                    }
                    structure["tables"].append(table_data)

            # Extract images
            if hasattr(doc, 'images'):
                for img in doc.images:
                    img_data = {
                        "page": getattr(img, 'page', None),
                        "size": getattr(img, 'size', None),
                        "format": getattr(img, 'format', None)
                    }
                    structure["images"].append(img_data)

            # Document metadata
            if hasattr(doc, 'metadata'):
                structure["metadata"] = doc.metadata

            return structure

        except Exception as e:
            logger.error(f"Error extracting document structure: {e}")
            return {"error": str(e)}

    def process_with_custom_chunking(self, file_path: str, filename: str,
                                   chunk_size: int = 500, overlap: int = 50) -> Dict[str, Any]:
        """
        Process document with custom chunking parameters.

        Args:
            file_path: Path to the document
            filename: Original filename
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks in characters

        Returns:
            Processing results
        """
        try:
            logger.info(f"Processing {filename} with custom chunking (size: {chunk_size}, overlap: {overlap})")

            # Convert document
            result = self.converter.convert(file_path)
            doc = result.document

            # Extract full text
            if hasattr(doc, 'export_to_markdown'):
                full_text = doc.export_to_markdown()
            else:
                full_text = str(doc)

            # Custom chunking
            chunks = []
            for i in range(0, len(full_text), chunk_size - overlap):
                chunk_text = full_text[i:i + chunk_size]
                if chunk_text.strip():
                    chunks.append({
                        "text": chunk_text,
                        "start_pos": i,
                        "end_pos": min(i + chunk_size, len(full_text))
                    })

            # Generate embeddings and store
            docs = []
            for i, chunk in enumerate(chunks):
                embedding = self.generate_embedding(chunk["text"])

                doc_body = {
                    "_index": self.index_name,
                    "_id": f"{filename}_custom_chunk_{i}",
                    "_source": {
                        "filename": filename,
                        "chunk_id": i,
                        "text": chunk["text"],
                        "embedding": embedding,
                        "metadata": {
                            "chunk_size": len(chunk["text"]),
                            "start_position": chunk["start_pos"],
                            "end_position": chunk["end_pos"],
                            "chunking_method": "custom",
                            "overlap": overlap,
                            "upload_timestamp": datetime.now().isoformat()
                        }
                    }
                }
                docs.append(doc_body)

            # Bulk index
            success, failures = bulk(self.es_client, docs)

            return {
                "status": "success",
                "filename": filename,
                "total_chunks": len(chunks),
                "indexed_chunks": success,
                "failed_chunks": len(failures) if failures else 0,
                "chunking_method": "custom",
                "chunk_size": chunk_size,
                "overlap": overlap
            }

        except Exception as e:
            logger.error(f"Error in custom chunking process: {e}")
            return {"status": "error", "error": str(e)}

# Global instance
document_processor = DocumentProcessor()
