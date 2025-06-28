"""Elasticsearch query management routes."""
import json
import logging
import os
import pandas as pd
import tempfile
import time
from typing import Dict, Any

from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse

from services.auth_service import get_current_user
from services.search_service import get_es_client
from util.redis_client import get_message_query, get_session_message_queries

logger = logging.getLogger(__name__)

router = APIRouter(tags=["elasticsearch"])

@router.get("/query/elasticsearch")
async def get_elasticsearch_query_csv(
    session_id: str = Query(..., description="Chat session identifier"),
    message_id: str = Query(..., description="Individual message identifier"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve Elasticsearch query from Redis, execute it in scan mode, and return all data as CSV.

    Args:
        session_id: Chat session identifier
        message_id: Individual message identifier
        current_user: Authenticated user information

    Returns:
        CSV file containing all Elasticsearch query results
    """
    try:
        logger.info(f"Executing ES query for session {session_id}, message {message_id}")

        # Retrieve the query from Redis
        es_query = get_message_query(session_id, message_id)
        if es_query is None:
            raise HTTPException(
                status_code=404,
                detail=f"No Elasticsearch query found for session {session_id}, message {message_id}"
            )

        # Get Elasticsearch client
        es_client = get_es_client()

        # Extract query details
        index = es_query.get('index')
        body = es_query.get('body', {})

        if not index:
            raise HTTPException(
                status_code=400,
                detail="Invalid Elasticsearch query: missing index"
            )

        # Remove size limit for full data extraction
        body.pop('size', None)

        logger.info(f"Executing ES query in scan mode for index: {index}")

        # Execute query with scroll to get all data
        all_data = []

        response = es_client.search(
            index=index,
            body=body,
            scroll='2m',
            size=1000,
            request_timeout=60
        )

        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']

        # Process first batch
        for hit in hits:
            source_data = hit.get('_source', {})
            source_data['_id'] = hit.get('_id')
            source_data['_score'] = hit.get('_score')
            all_data.append(source_data)

        # Continue scrolling through all results
        while len(hits) > 0:
            try:
                response = es_client.scroll(scroll_id=scroll_id, scroll='2m')
                scroll_id = response['_scroll_id']
                hits = response['hits']['hits']

                for hit in hits:
                    source_data = hit.get('_source', {})
                    source_data['_id'] = hit.get('_id')
                    source_data['_score'] = hit.get('_score')
                    all_data.append(source_data)

            except Exception as scroll_error:
                logger.warning(f"Error during scroll: {scroll_error}")
                break

        # Clear scroll context
        try:
            es_client.clear_scroll(scroll_id=scroll_id)
        except Exception as clear_error:
            logger.warning(f"Error clearing scroll: {clear_error}")

        if not all_data:
            raise HTTPException(
                status_code=404,
                detail="No data found for the given query"
            )

        logger.info(f"Retrieved {len(all_data)} documents from Elasticsearch")

        # Convert to pandas DataFrame and create CSV
        df = pd.DataFrame(all_data)

        temp_dir = tempfile.gettempdir()
        csv_filename = f"elasticsearch_query_{session_id}_{message_id}_{int(time.time())}.csv"
        csv_path = os.path.join(temp_dir, csv_filename)

        df.to_csv(csv_path, index=False, encoding='utf-8')

        logger.info(f"Created CSV file: {csv_path} with {len(df)} rows and {len(df.columns)} columns")

        return FileResponse(
            path=csv_path,
            filename=csv_filename,
            media_type='text/csv',
            headers={
                "Content-Disposition": f"attachment; filename={csv_filename}",
                "X-Total-Records": str(len(df)),
                "X-Session-ID": session_id,
                "X-Message-ID": message_id
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing ES query and generating CSV: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while processing query: {str(e)}"
        )

@router.get("/query/elasticsearch/raw")
async def get_elasticsearch_query_raw(
    session_id: str = Query(..., description="Chat session identifier"),
    message_id: str = Query(..., description="Individual message identifier"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve raw Elasticsearch query for a specific message from Redis.

    Args:
        session_id: Chat session identifier
        message_id: Individual message identifier
        current_user: Authenticated user information

    Returns:
        JSON response containing the raw Elasticsearch query
    """
    try:
        logger.info(f"Retrieving raw ES query for session {session_id}, message {message_id}")

        es_query = get_message_query(session_id, message_id)
        if es_query is None:
            raise HTTPException(
                status_code=404,
                detail=f"No Elasticsearch query found for session {session_id}, message {message_id}"
            )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "session_id": session_id,
                "message_id": message_id,
                "elasticsearch_query": es_query,
                "retrieved_at": int(time.time())
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving ES query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while retrieving query: {str(e)}"
        )

@router.get("/query/elasticsearch/session")
async def get_session_elasticsearch_queries(
    session_id: str = Query(..., description="Chat session identifier"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve all Elasticsearch queries for a session from Redis.

    Args:
        session_id: Chat session identifier
        current_user: Authenticated user information

    Returns:
        JSON response containing all Elasticsearch queries for the session
    """
    try:
        logger.info(f"Retrieving all ES queries for session {session_id}")

        session_queries = get_session_message_queries(session_id)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "session_id": session_id,
                "query_count": len(session_queries),
                "elasticsearch_queries": session_queries,
                "retrieved_at": int(time.time())
            }
        )

    except Exception as e:
        logger.error(f"Error retrieving ES queries for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while retrieving session queries: {str(e)}"
        )
