import aiohttp
import os
import chromadb
from fastapi import HTTPException, status

async def create_render_chroma_db(chroma_endpoint: str, headers: dict = None, data: dict = None):
    """
    Sends an asynchronous HTTP POST request to the ChromaDB endpoint to create a new database.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(chroma_endpoint, headers=headers, json=data) as response:
                if response.status == 200:
                    response_data = await response.json()
                    print("ChromaDB database created successfully.")
                    print("Response:", response_data)
                else:
                    print(f"Failed to create ChromaDB database. Status code: {response.status}")
                    response_text = await response.text()
                    print("Response:", response_text)

    except Exception as e:
        print(f"Error occurred while trying to create ChromaDB database: {e}")
        
        
CHROMA_SERVER_AUTHN_CREDENTIALS = os.environ['CHROMA_SERVER_AUTHN_CREDENTIALS']
chroma_headers = {'X-Chroma-Token': CHROMA_SERVER_AUTHN_CREDENTIALS}
CHROMA_ENDPOINT = os.environ['CHROMA_ENDPOINT']


def clear_chroma_db_datastore_for_replace(account_unique_id: str):
    """
    Clear Chroma DB
    """
    print(f"Received request to clear Chroma DB for account {account_unique_id}")
    print(f"Connecting to ChromaDB at {CHROMA_ENDPOINT}...")
    chroma_client = chromadb.HttpClient(
        host=CHROMA_ENDPOINT,
        headers=chroma_headers
    )

    print(f"Successfully connected to ChromaDB.")
    collection_name = f"collection-{account_unique_id}"

    collection_status = chroma_client.get_collection(name=collection_name)
    print("Collection Status: ", collection_status)
    if collection_status:
        try:
            # This is the correct way to delete a collection from the ChromaDB server.
            chroma_client.delete_collection(name=collection_name)
            print(f"Successfully deleted collection: {collection_name}")
            return {"response": f"success, collection '{collection_name}' deleted", "status": 200}

        except ValueError as e:
            # The chromadb client raises a ValueError if the collection doesn't exist.
            # This is not necessarily an error in our endpoint's logic.
            print(f"Attempted to delete a non-existent collection: {collection_name}. Error: {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found for this account."
            )
        except Exception as e:
            # Catch other potential errors (e.g., network issues connecting to Chroma)
            print(f"An unexpected error occurred: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while trying to clear the database."
            )

# Example usage
# CHROMA_ENDPOINT = 'https://fastapi-rag-chroma.onrender.com/api/v1'
# CHROMA_SERVER_AUTHN_CREDENTIALS = os.environ.get('CHROMA_SERVER_AUTHN_CREDENTIALS')
# final_endpoint = f'{CHROMA_ENDPOINT}/databases'

# # Data to create the database
# data = {
#     'name': 'test_db22',
# }

# headers = {
#     'X-Chroma-Token': CHROMA_SERVER_AUTHN_CREDENTIALS,
#     'Content-Type': 'application/json'
# }

# # Call the function to create the ChromaDB database
# create_render_chroma_db(final_endpoint, headers=headers, data=data)
