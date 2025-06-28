"""Document processing service for PDF upload and vectorization."""

# Import CPU configuration FIRST to set environment variables
from util.cpu_config import *

import os
import tempfile
import logging
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime

# Now import ML libraries after environment is configured
import torch
torch.set_default_device("cpu")

from elasticsearch.helpers import bulk
from services.search_service import get_es_client, get_sentence_transformer_model

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Simplified document processing service to avoid segmentation faults."""

    def __init__(self):
        self.es_client = get_es_client()
        self.embedding_model = get_sentence_transformer_model()
        self.index_name = "docling_documents"

        # Simplified converter - avoid heavy ML models that cause crashes
        self.use_simple_processing = True
        logger.info("DocumentProcessor initialized with simple text processing")

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
                        "dims": 384,
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

        if not self.es_client.indices.exists(index=self.index_name):
            self.es_client.indices.create(index=self.index_name, body=index_mapping)
            logger.info(f"Created Elasticsearch index: {self.index_name}")

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using sentence transformer with CPU-only processing."""
        # Force CPU usage for this specific operation
        with torch.no_grad():
            # Ensure the model is on CPU
            if hasattr(self.embedding_model, 'device'):
                self.embedding_model = self.embedding_model.to('cpu')

            # Generate embedding with explicit CPU device
            embedding = self.embedding_model.encode(
                text,
                convert_to_tensor=False,
                device='cpu',
                show_progress_bar=False,
                batch_size=1  # Process one at a time to avoid memory issues
            )
            return embedding.tolist()

    def simple_pdf_text_extraction(self, file_path: str) -> str:
        """Simple PDF text extraction using multiple fallback methods."""
        # Try PyPDF2 first
        try:
            import PyPDF2
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            if text.strip():
                logger.info("Successfully extracted text using PyPDF2")
                return text
        except ImportError:
            logger.info("PyPDF2 not available, trying pdfplumber")
        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed: {e}, trying pdfplumber")

        # Try pdfplumber as backup
        try:
            import pdfplumber
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            if text.strip():
                logger.info("Successfully extracted text using pdfplumber")
                return text
        except ImportError:
            logger.info("pdfplumber not available, trying pymupdf")
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}, trying pymupdf")

        # Try pymupdf (fitz) as another backup
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            if text.strip():
                logger.info("Successfully extracted text using PyMuPDF")
                return text
        except ImportError:
            logger.info("PyMuPDF not available, trying basic file reading")
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}, trying basic file reading")

        # Last resort: try to read as plain text (will likely fail for PDFs but worth trying)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                text = file.read()
            if text.strip():
                logger.warning("Extracted text using basic file reading - may be corrupted")
                return text
        except Exception as e:
            logger.error(f"Basic file reading failed: {e}")

        logger.error("All PDF extraction methods failed")
        return ""

    def simple_chunking(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Simple text chunking without ML dependencies."""
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
        return chunks

    def process_pdf_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """Process PDF file with simple, stable text extraction."""
        logger.info(f"Processing PDF: {filename}")

        self.create_index_if_not_exists()

        # Extract text using simple methods
        text = self.simple_pdf_text_extraction(file_path)
        if not text:
            return {
                "status": "error",
                "filename": filename,
                "error": "Failed to extract text from PDF"
            }

        logger.info(f"Extracted {len(text)} characters from {filename}")

        # Simple chunking
        chunks = self.simple_chunking(text)
        logger.info(f"Created {len(chunks)} chunks")

        # Process chunks and create embeddings
        docs = []
        for i, chunk_text in enumerate(chunks):
            try:
                embedding = self.generate_embedding(chunk_text)

                doc = {
                    "_index": self.index_name,
                    "_id": f"{filename}_chunk_{i}",
                    "_source": {
                        "filename": filename,
                        "chunk_id": i,
                        "text": chunk_text,
                        "embedding": embedding,
                        "metadata": {
                            "chunk_size": len(chunk_text),
                            "upload_timestamp": datetime.now().isoformat(),
                            "document_type": "pdf",
                            "processing_method": "simple"
                        }
                    }
                }
                docs.append(doc)

            except Exception as e:
                logger.warning(f"Failed to process chunk {i}: {e}")
                continue

        # Bulk index
        success_count = 0
        try:
            for doc in docs:
                self.es_client.index(
                    index=doc["_index"],
                    id=doc["_id"],
                    body=doc["_source"]
                )
                success_count += 1
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")

        return {
            "status": "success" if success_count > 0 else "error",
            "filename": filename,
            "total_chunks": len(chunks),
            "indexed_chunks": success_count,
            "failed_chunks": len(chunks) - success_count
        }

# Global instance
document_processor = DocumentProcessor()
