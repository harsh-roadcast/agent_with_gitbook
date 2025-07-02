"""Service for aggregating and managing document metadata for informed query decisions."""

import logging
import json
from typing import Dict, List, Any, Optional
from collections import defaultdict

from services.search_service import get_es_client

logger = logging.getLogger(__name__)

class DocumentMetadataService:
    """Service for retrieving and aggregating document metadata to inform query decisions."""

    def __init__(self):
        self.es_client = get_es_client()
        self.index_name = "docling_documents"

    def get_aggregated_metadata(self) -> Dict[str, Any]:
        """
        Retrieve and aggregate metadata from all indexed documents.

        Returns:
            Dictionary containing aggregated topics, entities, keywords, document types, etc.
        """
        try:
            # Query to get metadata from all documents
            query = {
                "size": 0,  # We only want aggregations, not documents
                "aggs": {
                    "document_titles": {
                        "terms": {
                            "field": "metadata.document_title.keyword",
                            "size": 100
                        }
                    },
                    "document_types": {
                        "terms": {
                            "field": "metadata.doc_type.keyword",
                            "size": 50
                        }
                    },
                    "languages": {
                        "terms": {
                            "field": "metadata.language.keyword",
                            "size": 20
                        }
                    },
                    "main_topics": {
                        "terms": {
                            "field": "metadata.main_topics.keyword",
                            "size": 100
                        }
                    },
                    "key_entities": {
                        "terms": {
                            "field": "metadata.key_entities.keyword",
                            "size": 200
                        }
                    },
                    "keywords": {
                        "terms": {
                            "field": "metadata.keywords.keyword",
                            "size": 200
                        }
                    }
                }
            }

            response = self.es_client.search(index=self.index_name, body=query)

            # Process aggregations
            aggs = response.get('aggregations', {})

            metadata = {
                "total_documents": response['hits']['total']['value'],
                "document_titles": [bucket['key'] for bucket in aggs.get('document_titles', {}).get('buckets', [])],
                "document_types": [bucket['key'] for bucket in aggs.get('document_types', {}).get('buckets', [])],
                "languages": [bucket['key'] for bucket in aggs.get('languages', {}).get('buckets', [])],
                "main_topics": [bucket['key'] for bucket in aggs.get('main_topics', {}).get('buckets', [])],
                "key_entities": [bucket['key'] for bucket in aggs.get('key_entities', {}).get('buckets', [])],
                "keywords": [bucket['key'] for bucket in aggs.get('keywords', {}).get('buckets', [])]
            }

            logger.info(f"Retrieved metadata for {metadata['total_documents']} documents")
            return metadata

        except Exception as e:
            logger.error(f"Error retrieving document metadata: {e}")
            return {
                "total_documents": 0,
                "document_titles": [],
                "document_types": [],
                "languages": [],
                "main_topics": [],
                "key_entities": [],
                "keywords": []
            }

    def get_detailed_metadata_sample(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get detailed metadata from a sample of documents for analysis.

        Args:
            limit: Number of documents to sample

        Returns:
            List of document metadata samples
        """
        try:
            query = {
                "size": limit,
                "_source": ["filename", "metadata"],
                "query": {
                    "exists": {
                        "field": "metadata.document_title"
                    }
                }
            }

            response = self.es_client.search(index=self.index_name, body=query)

            samples = []
            for hit in response['hits']['hits']:
                metadata = hit['_source'].get('metadata', {})
                samples.append({
                    "filename": hit['_source'].get('filename'),
                    "document_title": metadata.get('document_title'),
                    "document_type": metadata.get('doc_type'),
                    "main_topics": metadata.get('main_topics', []),
                    "key_entities": metadata.get('key_entities', []),
                    "keywords": metadata.get('keywords', []),
                    "language": metadata.get('language'),
                    "confidence_score": metadata.get('confidence_score', 0.0)
                })

            return samples

        except Exception as e:
            logger.error(f"Error retrieving detailed metadata samples: {e}")
            return []

    def search_by_metadata(self, topics: List[str] = None, entities: List[str] = None,
                          keywords: List[str] = None, document_types: List[str] = None) -> List[str]:
        """
        Search for documents based on metadata criteria.

        Args:
            topics: List of topics to match
            entities: List of entities to match
            keywords: List of keywords to match
            document_types: List of document types to match

        Returns:
            List of matching document filenames
        """
        try:
            must_clauses = []

            if topics:
                must_clauses.append({
                    "terms": {"metadata.main_topics.keyword": topics}
                })

            if entities:
                must_clauses.append({
                    "terms": {"metadata.key_entities.keyword": entities}
                })

            if keywords:
                must_clauses.append({
                    "terms": {"metadata.keywords.keyword": keywords}
                })

            if document_types:
                must_clauses.append({
                    "terms": {"metadata.doc_type.keyword": document_types}
                })

            if not must_clauses:
                return []

            query = {
                "size": 100,
                "_source": ["filename"],
                "query": {
                    "bool": {
                        "must": must_clauses
                    }
                }
            }

            response = self.es_client.search(index=self.index_name, body=query)

            filenames = []
            for hit in response['hits']['hits']:
                filename = hit['_source'].get('filename')
                if filename and filename not in filenames:
                    filenames.append(filename)

            return filenames

        except Exception as e:
            logger.error(f"Error searching by metadata: {e}")
            return []

    def get_metadata_json(self) -> str:
        """
        Get aggregated metadata as JSON string for use in DSPy signatures.

        Returns:
            JSON string of aggregated metadata
        """
        metadata = self.get_aggregated_metadata()
        return json.dumps(metadata, ensure_ascii=False)

# Global instance
metadata_service = DocumentMetadataService()
