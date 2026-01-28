"""Document processing background tasks."""
import logging
import os
import tempfile
from typing import Any, Dict, Optional

from celery import current_task

from celery_app import celery_app
from services.document_service import document_processor
from services.gitbook_service import ingest_space
from util.redis_client import redis_client
from core.config import config_manager

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="tasks.document_tasks.process_pdf_document")
def process_pdf_document(self, file_content: bytes, filename: str, user_id: str = None) -> Dict[str, Any]:
    """
    Background task to process PDF document with vectorization.

    Args:
        file_content: PDF file content as bytes
        filename: Original filename
        user_id: User ID for tracking

    Returns:
        Processing results
    """
    try:
        # Update task status
        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Starting PDF processing", "progress": 0}
        )

        logger.info(f"Starting background PDF processing for: {filename}")

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            # Update progress
            current_task.update_state(
                state="PROGRESS",
                meta={"status": "Converting document", "progress": 25}
            )

            # Process the PDF
            result = document_processor.process_pdf_file(temp_file_path, filename)

            # Update progress
            current_task.update_state(
                state="PROGRESS",
                meta={"status": "Generating embeddings", "progress": 75}
            )

            # Store result in Redis for quick access
            if user_id:
                result_key = f"document_result:{user_id}:{filename}"
                redis_client.setex(result_key, 3600, str(result))  # Store for 1 hour

            # Final update
            current_task.update_state(
                state="SUCCESS",
                meta={"status": "Processing completed", "progress": 100, "result": result}
            )

            logger.info(f"PDF processing completed for: {filename}")
            return result

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except Exception as e:
        logger.error(f"Error processing PDF {filename}: {e}", exc_info=True)
        current_task.update_state(
            state="FAILURE",
            meta={"status": "Processing failed", "error": str(e)}
        )
        raise

@celery_app.task(bind=True, name="tasks.document_tasks.vectorize_document_batch")
def vectorize_document_batch(self, documents: list, batch_size: int = 10) -> Dict[str, Any]:
    """
    Background task to vectorize a batch of documents.

    Args:
        documents: List of document data to vectorize
        batch_size: Number of documents to process in each batch

    Returns:
        Vectorization results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Starting batch vectorization", "progress": 0}
        )

        total_docs = len(documents)
        processed = 0
        results = []

        for i in range(0, total_docs, batch_size):
            batch = documents[i:i + batch_size]

            # Process batch
            for doc in batch:
                try:
                    # Generate embedding for document text
                    embedding = document_processor.generate_embedding(doc.get("text", ""))
                    results.append({
                        "document_id": doc.get("id"),
                        "embedding": embedding,
                        "status": "success"
                    })
                except Exception as e:
                    results.append({
                        "document_id": doc.get("id"),
                        "error": str(e),
                        "status": "failed"
                    })

                processed += 1
                progress = int((processed / total_docs) * 100)

                # Update progress
                current_task.update_state(
                    state="PROGRESS",
                    meta={
                        "status": f"Processed {processed}/{total_docs} documents",
                        "progress": progress
                    }
                )

        success_count = sum(1 for r in results if r["status"] == "success")
        failed_count = len(results) - success_count

        final_result = {
            "total_documents": total_docs,
            "successful": success_count,
            "failed": failed_count,
            "results": results
        }

        current_task.update_state(
            state="SUCCESS",
            meta={"status": "Batch vectorization completed", "progress": 100, "result": final_result}
        )

        return final_result

    except Exception as e:
        logger.error(f"Error in batch vectorization: {e}", exc_info=True)
        current_task.update_state(
            state="FAILURE",
            meta={"status": "Batch vectorization failed", "error": str(e)}
        )
        raise

@celery_app.task(bind=True, name="tasks.document_tasks.extract_document_structure")
def extract_document_structure(self, file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    Background task to extract document structure using Docling.

    Args:
        file_content: Document file content as bytes
        filename: Original filename

    Returns:
        Document structure analysis
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Extracting document structure", "progress": 0}
        )

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            current_task.update_state(
                state="PROGRESS",
                meta={"status": "Analyzing document structure", "progress": 50}
            )

            # Extract structure
            structure = document_processor.extract_document_structure(temp_file_path)

            current_task.update_state(
                state="SUCCESS",
                meta={"status": "Structure extraction completed", "progress": 100, "result": structure}
            )

            return structure

        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except Exception as e:
        logger.error(f"Error extracting structure for {filename}: {e}", exc_info=True)
        current_task.update_state(
            state="FAILURE",
            meta={"status": "Structure extraction failed", "error": str(e)}
        )
        raise

@celery_app.task(bind=True, name="tasks.document_tasks.crawl_gitbook_repository")
def crawl_gitbook_repository(self, max_pages: Optional[int] = None, force_reindex: bool = False) -> Dict[str, Any]:
    """Run the full GitBook crawl, chunk, and index pipeline."""
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Starting GitBook pipeline", "progress": 0}
        )

        space_name = config_manager.config.gitbook.base_url
        logger.info("Starting GitBook pipeline for %s", space_name)

        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Collecting GitBook pages", "progress": 10}
        )

        result = ingest_space(max_pages=max_pages, force_reindex=force_reindex)

        current_task.update_state(
            state="SUCCESS",
            meta={
                "status": "GitBook pipeline completed",
                "progress": 100,
                "result": result
            }
        )

        logger.info(
            "GitBook pipeline succeeded: %s documents indexed (%s chunks)",
            result.get("pages_ingested"),
            result.get("documents_indexed")
        )
        return result

    except Exception as exc:
        logger.error("GitBook pipeline failed: %s", exc, exc_info=True)
        current_task.update_state(
            state="FAILURE",
            meta={"status": "GitBook pipeline failed", "error": str(exc)}
        )
        raise
