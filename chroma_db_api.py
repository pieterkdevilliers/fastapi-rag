import aiohttp
import os

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
