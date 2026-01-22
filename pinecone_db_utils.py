import os
from pinecone import Pinecone
from typing import Dict, Any
from fastapi import HTTPException, status

def check_pinecone_namespace_status(account_unique_id: str) -> Dict[str, Any]:
    """
    Checks if a Pinecone namespace (equivalent to Chroma collection) has any data.
    Returns similar structure to your original: status code + message or stats.
    """
    api_key = os.environ['PINECONE_EXPERTECHO_API_KEY']  # or your env var name
    index_name = "expert-echo-rag"  # ← your actual index name from dashboard

    print(f"Connecting to Pinecone index '{index_name}'...")
    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)
    print("Successfully connected to Pinecone.")

    namespace = f"account-{account_unique_id}"  # consistent with your ingestion

    try:
        # Get index stats filtered to this namespace
        stats = index.describe_index_stats(filter_by_namespace=True)  # or .describe() if SDK variant

        # In serverless, namespaces appear only if they have data or were explicitly created
        # But describe_index_stats() includes all namespaces with record_count
        namespace_stats = stats.get('namespaces', {}).get(namespace, {})

        record_count = namespace_stats.get('record_count', 0)

        if record_count > 0:
            # Exists and has data → return "status" info
            return {
                "status": 200,
                "message": f"Namespace '{namespace}' exists with {record_count} vectors",
                "record_count": record_count,
                # Add more from stats if useful, e.g. dimension, index_fullness
                "dimension": stats.get('dimension'),
                "index_fullness": stats.get('index_fullness', 0.0)
            }
        else:
            # Namespace doesn't exist or is empty
            return {"status": 404, "message": f"Namespace '{namespace}' does not exist or is empty"}

    except Exception as e:
        # Handle connection/auth errors, etc.
        print(f"Error checking namespace status: {str(e)}")
        return {"status": 500, "message": f"Error: {str(e)}"}
    

def clear_pinecone_namespace_for_replace(account_unique_id: str) -> Dict[str, Any]:
    """
    Clears (deletes all vectors from) the Pinecone namespace for the given account.
    This prepares it for replacement with new data.
    """
    print(f"Received request to clear Pinecone namespace for account {account_unique_id}")

    api_key = os.environ['PINECONE_EXPERTECHO_API_KEY']
    index_name = "expert-echo-rag"

    print(f"Connecting to Pinecone index '{index_name}'...")
    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)
    print("Successfully connected to Pinecone.")

    namespace = f"account-{account_unique_id}"

    try:
        # Delete ALL vectors in the namespace (idempotent if empty/non-existent)
        index.delete(delete_all=True, namespace=namespace)
        print(f"Successfully cleared all vectors from namespace: {namespace}")

        return {
            "response": f"success, namespace '{namespace}' cleared (all vectors deleted)",
            "status": 200
        }

    except Exception as e:
        # Catch network/auth/Pinecone errors
        error_msg = str(e)
        print(f"Error clearing namespace '{namespace}': {error_msg}")

        if "not found" in error_msg.lower() or "namespace" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Namespace '{namespace}' not found or already empty."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred while clearing the namespace: {error_msg}"
            )