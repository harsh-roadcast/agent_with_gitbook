"""Bulk indexing background tasks."""
import logging
from typing import Dict, Any, List
from celery import current_task

from celery_app import celery_app
from services.bulk_index_service import bulk_index_documents, create_index_if_not_exists
from util.redis_client import redis_client

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="tasks.bulk_index_tasks.bulk_index_documents_async")
def bulk_index_documents_async(self, index_name: str, documents: List[Dict[str, Any]],
                               user_id: str = None, create_index: bool = True) -> Dict[str, Any]:
    """
    Background task for bulk indexing large document sets.

    Args:
        index_name: Elasticsearch index name
        documents: List of documents to index
        user_id: User ID for tracking
        create_index: Whether to create index if not exists

    Returns:
        Bulk indexing results
    """
    try:
        total_docs = len(documents)
        current_task.update_state(
            state="PROGRESS",
            meta={"status": f"Starting bulk index of {total_docs} documents", "progress": 0}
        )

        logger.info(f"Starting background bulk indexing to '{index_name}' with {total_docs} documents")

        # Create index if requested
        if create_index:
            current_task.update_state(
                state="PROGRESS",
                meta={"status": "Creating index", "progress": 10}
            )

            index_result = create_index_if_not_exists(index_name)

        # Process documents in batches of 500
        batch_size = 500
        total_indexed = 0
        total_failed = 0
        all_results = []

        for i in range(0, total_docs, batch_size):
            batch = documents[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_docs + batch_size - 1) // batch_size

            current_task.update_state(
                state="PROGRESS",
                meta={
                    "status": f"Processing batch {batch_num}/{total_batches}",
                    "progress": int(((i + len(batch)) / total_docs) * 90) + 10
                }
            )

            # Index batch
            result = bulk_index_documents(index_name, batch, max_docs=500)
            all_results.append(result)

            total_indexed += result.get("indexed_count", 0)
            total_failed += result.get("failed_count", 0)

            logger.info(f"Batch {batch_num} completed: {result.get('indexed_count', 0)} indexed")

        # Store result summary
        final_result = {
            "status": "completed",
            "index_name": index_name,
            "total_documents": total_docs,
            "total_indexed": total_indexed,
            "total_failed": total_failed,
            "batches_processed": len(all_results),
            "batch_results": all_results
        }

        # Cache result for user
        if user_id:
            result_key = f"bulk_index_result:{user_id}:{index_name}"
            redis_client.setex(result_key, 3600, str(final_result))

        current_task.update_state(
            state="SUCCESS",
            meta={"status": "Bulk indexing completed", "progress": 100, "result": final_result}
        )

        logger.info(f"Background bulk indexing completed: {total_indexed} indexed, {total_failed} failed")
        return final_result

    except Exception as e:
        logger.error(f"Error in background bulk indexing: {e}", exc_info=True)
        current_task.update_state(
            state="FAILURE",
            meta={"status": "Bulk indexing failed", "error": str(e)}
        )
        raise

@celery_app.task(bind=True, name="tasks.bulk_index_tasks.bulk_index_from_file")
def bulk_index_from_file(self, file_content: str, index_name: str, file_format: str = "json",
                        user_id: str = None) -> Dict[str, Any]:
    """
    Background task to bulk index documents from uploaded file.

    Args:
        file_content: File content as string
        index_name: Elasticsearch index name
        file_format: File format (json, csv, etc.)
        user_id: User ID for tracking

    Returns:
        Processing results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Parsing file content", "progress": 0}
        )

        # Parse file content based on format
        if file_format.lower() == "json":
            import json
            documents = json.loads(file_content)
            if not isinstance(documents, list):
                documents = [documents]
        elif file_format.lower() == "csv":
            import csv
            import io
            documents = []
            reader = csv.DictReader(io.StringIO(file_content))
            for row in reader:
                documents.append(row)
        else:
            raise ValueError(f"Unsupported file format: {file_format}")

        current_task.update_state(
            state="PROGRESS",
            meta={"status": f"Parsed {len(documents)} documents", "progress": 20}
        )

        # Call the bulk indexing task
        result = bulk_index_documents_async.apply_async(
            args=[index_name, documents, user_id, True],
            task_id=f"{self.request.id}_bulk"
        )

        return {
            "status": "delegated",
            "bulk_task_id": result.id,
            "documents_count": len(documents),
            "index_name": index_name
        }

    except Exception as e:
        logger.error(f"Error processing file for bulk index: {e}", exc_info=True)
        current_task.update_state(
            state="FAILURE",
            meta={"status": "File processing failed", "error": str(e)}
        )
        raise

@celery_app.task(bind=True, name="tasks.bulk_index_tasks.reindex_documents")
def reindex_documents(self, source_index: str, target_index: str,
                     query: Dict = None, transform_func: str = None) -> Dict[str, Any]:
    """
    Background task to reindex documents from one index to another.

    Args:
        source_index: Source Elasticsearch index
        target_index: Target Elasticsearch index
        query: Optional query to filter documents
        transform_func: Optional transformation function name

    Returns:
        Reindexing results
    """
    try:
        from services.search_service import es_client

        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Starting reindex operation", "progress": 0}
        )

        # Create target index
        create_index_if_not_exists(target_index)

        current_task.update_state(
            state="PROGRESS",
            meta={"status": "Fetching source documents", "progress": 20}
        )

        # Scroll through source index
        search_body = query or {"query": {"match_all": {}}}

        response = es_client.search(
            index=source_index,
            body=search_body,
            scroll="2m",
            size=1000
        )

        scroll_id = response["_scroll_id"]
        total_docs = response["hits"]["total"]["value"]
        processed = 0
        reindexed = 0

        while response["hits"]["hits"]:
            documents = []

            for hit in response["hits"]["hits"]:
                doc = hit["_source"]

                # Apply transformation if specified
                if transform_func:
                    # This would need to be implemented based on your needs
                    pass

                documents.append(doc)

            # Bulk index to target
            if documents:
                result = bulk_index_documents(target_index, documents)
                reindexed += result.get("indexed_count", 0)

            processed += len(response["hits"]["hits"])
            progress = int((processed / total_docs) * 80) + 20

            current_task.update_state(
                state="PROGRESS",
                meta={
                    "status": f"Reindexed {reindexed}/{total_docs} documents",
                    "progress": progress
                }
            )

            # Get next batch
            response = es_client.scroll(scroll_id=scroll_id, scroll="2m")

        # Clear scroll
        es_client.clear_scroll(scroll_id=scroll_id)

        final_result = {
            "status": "completed",
            "source_index": source_index,
            "target_index": target_index,
            "total_documents": total_docs,
            "reindexed_documents": reindexed
        }

        current_task.update_state(
            state="SUCCESS",
            meta={"status": "Reindexing completed", "progress": 100, "result": final_result}
        )

        return final_result

    except Exception as e:
        logger.error(f"Error in reindexing: {e}", exc_info=True)
        current_task.update_state(
            state="FAILURE",
            meta={"status": "Reindexing failed", "error": str(e)}
        )
        raise
