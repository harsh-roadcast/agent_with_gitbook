"""Simple document processing service using Docling exclusively."""

import logging
from datetime import datetime
from typing import List, Dict, Any

import torch

torch.set_default_device("cpu")

import dspy
from docling.document_converter import DocumentConverter
from services.search_service import get_es_client, get_sentence_transformer_model, generate_embedding
from modules.signatures import DocumentMetadataExtractor

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Simple document processing using Docling only."""

    def __init__(self):
        self.es_client = get_es_client()
        self.embedding_model = get_sentence_transformer_model()
        self.index_name = "docling_documents"
        self.docling_converter = DocumentConverter()
        self.metadata_extractor = dspy.ChainOfThought(DocumentMetadataExtractor)

        logger.info("DocumentProcessor initialized with Docling")

    def extract_text(self, file_path: str) -> str:
        """Extract text from PDF using Docling."""
        result = self.docling_converter.convert(file_path)
        return result.document.export_to_markdown()

    def create_chunks(self, text: str, chunk_size: int = 1000) -> List[str]:
        """Simple text chunking."""
        chunks = []
        words = text.split()

        for i in range(0, len(words), chunk_size):
            chunk_words = words[i:i + chunk_size]
            chunk = ' '.join(chunk_words)
            if len(chunk.strip()) > 20:  # Only keep meaningful chunks
                chunks.append(chunk)

        return chunks

    def extract_metadata(self, text: str, filename: str) -> Dict[str, Any]:
        """Extract metadata using DSPy."""
        try:
            result = self.metadata_extractor(
                document_text=text[:5000],  # Use first 5k chars
                filename=filename
            )
            return {
                "document_title": result.document_title,
                "document_type": result.document_type,
                "main_topics": result.main_topics,
                "key_entities": result.key_entities,
                "language": result.language,
                "summary": result.summary,
                "keywords": result.keywords
            }
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")
            return {"document_title": filename, "document_type": "unknown"}

    def create_embedding(self, text: str) -> List[float]:
        """Create embedding for text."""
        return generate_embedding(text)

    def process_pdf_file(self, file_path: str, filename: str, index_name: str = None) -> Dict[str, Any]:
        """Process PDF file - simplified version."""
        try:
            logger.info(f"Processing PDF: {filename}")

            # Use provided index name or fallback to default
            target_index = index_name or self.index_name

            # Extract text
            text = self.extract_text(file_path)
            if not text or len(text.strip()) < 10:
                return {"status": "error", "error": "No text extracted"}

            # Extract metadata
            metadata = self.extract_metadata(text, filename)

            # Create chunks
            chunks = self.create_chunks(text)
            logger.info(f"Created {len(chunks)} chunks")

            # Index chunks
            success_count = 0
            for i, chunk_text in enumerate(chunks):
                try:
                    embedding = self.create_embedding(chunk_text)

                    doc = {
                        "filename": filename,
                        "chunk_id": i,
                        "text": chunk_text,
                        "embedding": embedding,
                        "metadata": {
                            "upload_timestamp": datetime.now().isoformat(),
                            "processing_method": "docling_simple",
                            **metadata
                        }
                    }

                    self.es_client.index(
                        index=target_index,
                        id=f"{filename}_chunk_{i}",
                        body=doc
                    )
                    success_count += 1

                except Exception as e:
                    logger.warning(f"Failed to index chunk {i}: {e}")

            return {
                "status": "success" if success_count > 0 else "error",
                "filename": filename,
                "total_chunks": len(chunks),
                "indexed_chunks": success_count,
                "extracted_metadata": metadata,
                "target_index": target_index
            }

        except Exception as e:
            logger.error(f"Processing failed for {filename}: {e}")
            return {
                "status": "error",
                "filename": filename,
                "error": str(e)
            }

# Global instance
document_processor = DocumentProcessor()
