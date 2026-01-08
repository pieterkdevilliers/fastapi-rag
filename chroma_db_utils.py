import os
import chromadb
from typing import Optional
from chromadb.config import DEFAULT_TENANT, DEFAULT_DATABASE


CHROMA_SERVER_AUTHN_CREDENTIALS = os.environ['CHROMA_SERVER_AUTHN_CREDENTIALS']
chroma_headers = {'X-Chroma-Token': CHROMA_SERVER_AUTHN_CREDENTIALS}


def delete_chunks_from_chroma(
    s3_key: str,
    account_unique_id: str,
    chroma_endpoint: Optional[str] = None
) -> dict:
    """
    Deletes all chunks from ChromaDB that belong to a specific source file (s3_key)
    within the account-specific collection.

    Args:
        s3_key (str): The full S3 key of the file (e.g., 'account123/docs/report.pdf')
                      This is stored in the metadata["source"] field during ingestion.
        account_unique_id (str): The unique ID for the account (used in collection name).
        chroma_endpoint (str, optional): ChromaDB endpoint URL. If not provided,
                                         reads from environment variable CHROMA_ENDPOINT.

    Returns:
        dict: Summary of deletion operation (count deleted, collection name, etc.)
    """
    if not chroma_endpoint:
        chroma_endpoint = os.environ.get('CHROMA_ENDPOINT')
        if not chroma_endpoint:
            raise ValueError("CHROMA_ENDPOINT environment variable not set")

    print(f"Connecting to ChromaDB at {chroma_endpoint} to delete chunks for source: {s3_key}")

    try:
        chroma_client = chromadb.HttpClient(
            host=chroma_endpoint,
            headers=chroma_headers,
            tenant=DEFAULT_TENANT,
            database=DEFAULT_DATABASE
        )

        collection_name = f"collection-{account_unique_id}"
        collection = chroma_client.get_collection(name=collection_name)

        print(f"Deleting chunks from collection '{collection_name}' where metadata.source == '{s3_key}'")

        # Perform the deletion using metadata filter
        collection.delete(where={"source": s3_key})

        # Verify by fetching only IDs (efficient, no documents/embeddings returned)
        results = collection.get(
            where={"source": s3_key},
            include=[]  # Returns only 'ids' (fastest way)
        )
        remaining_with_source = len(results.get('ids', []))

        print(f"Deletion complete. Remaining chunks with source '{s3_key}': {remaining_with_source}")

        return {
            "status": "success",
            "collection": collection_name,
            "deleted_source": s3_key,
            "remaining_with_same_source": remaining_with_source
        }

    except Exception as e:
        error_msg = f"Failed to delete chunks for {s3_key} in collection collection-{account_unique_id}: {str(e)}"
        print(error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "collection": f"collection-{account_unique_id}",
            "deleted_source": s3_key
        }