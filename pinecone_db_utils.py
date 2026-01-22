import os
from pinecone import Pinecone
from typing import Dict, Any, Optional
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
        
def delete_chunks_from_pinecone(
    s3_key: str,
    account_unique_id: str,
    index_name: str = "expert-echo-rag"  # Make configurable or env var if needed
) -> Dict[str, Any]:
    """
    Deletes all chunks from Pinecone that belong to a specific source file (s3_key)
    within the account-specific namespace.

    Args:
        s3_key (str): The full S3 key of the file (e.g., 'account123/docs/report.pdf')
                      Stored in metadata["source"] during ingestion.
        account_unique_id (str): Unique ID for the account (used in namespace).
        index_name (str, optional): Name of the Pinecone index.

    Returns:
        dict: Summary of deletion operation (status, namespace, remaining count, etc.)
    """
    api_key = os.environ.get('PINECONE_EXPERTECHO_API_KEY')
    if not api_key:
        raise ValueError("PINECONE_EXPERTECHO_API_KEY environment variable not set")

    print(f"Connecting to Pinecone index '{index_name}' to delete chunks for source: {s3_key}")

    try:
        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)

        namespace = f"account-{account_unique_id}"

        print(f"Deleting chunks from namespace '{namespace}' where metadata.source == '{s3_key}'")

        # Delete using metadata filter (supported in serverless)
        index.delete(
            filter={"source": {"$eq": s3_key}},
            namespace=namespace
        )

        # Optional verification: Query with same filter to count remaining (low-cost, returns IDs only)
        # Use top_k=10000 or higher if expecting many chunks; Pinecone caps at 10k per query
        verify_response = index.query(
            vector=[0.0] * 3072,  # Dummy zero vector (dimension must match your embeddings!)
            top_k=10000,          # Adjust if you have >10k chunks per file (rare)
            filter={"source": {"$eq": s3_key}},
            include_values=False,
            include_metadata=False,
            namespace=namespace
        )

        remaining_ids = [match['id'] for match in verify_response.get('matches', [])]
        remaining_count = len(remaining_ids)

        print(f"Deletion complete. Remaining chunks with source '{s3_key}': {remaining_count}")

        return {
            "status": "success",
            "namespace": namespace,
            "deleted_source": s3_key,
            "remaining_with_same_source": remaining_count
        }

    except Exception as e:
        error_msg = f"Failed to delete chunks for {s3_key} in namespace {namespace}: {str(e)}"
        print(error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "namespace": f"account-{account_unique_id}",
            "deleted_source": s3_key
        }