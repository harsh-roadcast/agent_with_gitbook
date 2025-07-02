import logging
from typing import List, Dict, Any, Optional

from elasticsearch.helpers import bulk

from services.search_service import es_client

logger = logging.getLogger(__name__)


def bulk_index_documents(
    index_name: str,
    documents: List[Dict[str, Any]],
    max_docs: int = 500
) -> Dict[str, Any]:
    """
    Bulk index documents into Elasticsearch with a maximum document limit.

    Args:
        index_name: Name of the Elasticsearch index
        documents: List of documents to index (max 500)
        max_docs: Maximum number of documents to process (default 500)

    Returns:
        Dictionary containing indexing results and statistics
    """
    logger.info(f"Starting bulk indexing to index '{index_name}' with {len(documents)} documents")

    # Enforce maximum document limit
    if len(documents) > max_docs:
        logger.warning(f"Document count ({len(documents)}) exceeds maximum ({max_docs}). Truncating.")
        documents = documents[:max_docs]

    # Prepare documents for bulk indexing
    bulk_docs = []
    for i, doc in enumerate(documents):
        bulk_doc = {
            "_index": index_name,
            "_source": doc
        }

        # If document has an 'id' field, use it as the document ID
        if "id" in doc:
            bulk_doc["_id"] = doc["id"]

        bulk_docs.append(bulk_doc)

    logger.info(f"Prepared {len(bulk_docs)} documents for bulk indexing")

    # Execute bulk indexing
    success_count, failed_items = bulk(
        es_client,
        bulk_docs,
        index=index_name,
        refresh=True,  # Refresh index after indexing
        request_timeout=60,
        max_retries=3,
        initial_backoff=2,
        max_backoff=600
    )

    failed_count = len(failed_items) if failed_items else 0

    logger.info(f"Bulk indexing completed: {success_count} successful, {failed_count} failed")

    result = {
        "success": True,
        "indexed_count": success_count,
        "failed_count": failed_count,
        "total_documents": len(documents),
        "index_name": index_name
    }

    if failed_items:
        result["failed_items"] = failed_items[:10]  # Return first 10 failed items for debugging
        result["warning"] = f"{failed_count} documents failed to index"

    return result


def create_index_if_not_exists(
    index_name: str,
    mapping: Optional[Dict[str, Any]] = None,
    settings: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create an Elasticsearch index if it doesn't exist.

    Args:
        index_name: Name of the index to create
        mapping: Optional mapping configuration
        settings: Optional index settings

    Returns:
        Dictionary containing creation result
    """
    logger.info(f"Checking if index '{index_name}' exists")

    if es_client.indices.exists(index=index_name):
        logger.info(f"Index '{index_name}' already exists")
        return {
            "success": True,
            "message": f"Index '{index_name}' already exists",
            "created": False,
            "index_name": index_name
        }

    # Prepare index body
    index_body = {}
    if settings:
        index_body["settings"] = settings
    if mapping:
        index_body["mappings"] = mapping

    # Create the index
    response = es_client.indices.create(index=index_name, body=index_body)

    logger.info(f"Index '{index_name}' created successfully")
    return {
        "success": True,
        "message": f"Index '{index_name}' created successfully",
        "created": True,
        "index_name": index_name,
        "response": response
    }


def get_index_info(index_name: str) -> Dict[str, Any]:
    """
    Get information about an Elasticsearch index.

    Args:
        index_name: Name of the index

    Returns:
        Dictionary containing index information
    """
    # Get index stats
    stats = es_client.indices.stats(index=index_name)

    # Get index mapping
    mapping = es_client.indices.get_mapping(index=index_name)

    # Get index settings
    settings = es_client.indices.get_settings(index=index_name)

    index_stats = stats["indices"][index_name]

    return {
        "success": True,
        "index_name": index_name,
        "document_count": index_stats["total"]["docs"]["count"],
        "size_in_bytes": index_stats["total"]["store"]["size_in_bytes"],
        "mapping": mapping[index_name]["mappings"],
        "settings": settings[index_name]["settings"]
    }
