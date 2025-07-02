"""Metadata search service for checking vector store content."""
import logging
from typing import List, Dict, Any

from services.search_service import get_es_client

logger = logging.getLogger(__name__)

def search_vector_metadata(search_terms: List[str], key_concepts: List[str]) -> Dict[str, Any]:
    """
    Search vector metadata to check if relevant documents exist.

    Args:
        search_terms: List of search terms from ThinkingSignature
        key_concepts: List of key concepts from ThinkingSignature

    Returns:
        Dict with metadata_found, metadata_summary, and relevant_documents count
    """
    try:
        es_client = get_es_client()

        # Combine search terms and key concepts for metadata search
        all_terms = search_terms + key_concepts

        # Create a metadata search query
        metadata_query = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": " ".join(all_terms),
                                "fields": ["filename", "document_title", "main_topics", "keywords", "summary"],
                                "type": "best_fields",
                                "fuzziness": "AUTO"
                            }
                        },
                        {
                            "terms": {
                                "keywords": all_terms
                            }
                        },
                        {
                            "terms": {
                                "main_topics": all_terms
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": 10,
            "_source": ["filename", "document_title", "main_topics", "keywords", "summary"]
        }

        # Search in metadata index (assuming it exists)
        try:
            response = es_client.search(index="document_metadata", body=metadata_query)
            hits = response.get('hits', {}).get('hits', [])

            metadata_found = len(hits) > 0
            relevant_documents = len(hits)

            if metadata_found:
                # Create summary of found metadata
                titles = [hit['_source'].get('document_title', 'Unknown') for hit in hits[:5]]
                topics = []
                for hit in hits[:5]:
                    topics.extend(hit['_source'].get('main_topics', []))

                unique_topics = list(set(topics))[:10]  # Top 10 unique topics

                metadata_summary = f"Found {relevant_documents} relevant documents including: {', '.join(titles)}. Main topics: {', '.join(unique_topics)}"
            else:
                metadata_summary = "No relevant documents found in vector metadata"

        except Exception as e:
            logger.warning(f"Metadata index search failed, trying main docling index: {e}")
            # Fallback to main document index
            response = es_client.search(index="docling_documents", body=metadata_query)
            hits = response.get('hits', {}).get('hits', [])

            metadata_found = len(hits) > 0
            relevant_documents = len(hits)

            if metadata_found:
                filenames = [hit['_source'].get('filename', 'Unknown') for hit in hits[:5]]
                metadata_summary = f"Found {relevant_documents} relevant documents in main index: {', '.join(filenames)}"
            else:
                metadata_summary = "No relevant documents found in any index"

        return {
            "metadata_found": metadata_found,
            "metadata_summary": metadata_summary,
            "relevant_documents": relevant_documents
        }

    except Exception as e:
        logger.error(f"Error in metadata search: {e}")
        return {
            "metadata_found": False,
            "metadata_summary": f"Metadata search failed: {str(e)}",
            "relevant_documents": 0
        }
