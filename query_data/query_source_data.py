import argparse
import os
import requests
# from dataclasses import dataclass
from sqlmodel import select, Session
from accounts.models import Account
from typing import List
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from chromadb.api.types import EmbeddingFunction
import chromadb
import openai 
from dotenv import load_dotenv


load_dotenv()

openai.api_key = os.environ['OPENAI_API_KEY']
CHAT_MODEL_NAME = os.environ.get('OPENAI_CHAT_MODEL', 'gpt-3.5-turbo')

CHROMA_PATH = "chroma"
ENVIRONMENT = os.environ.get('ENVIRONMENT')

# Chroma API endpoint and credentials
CHROMA_ENDPOINT = os.environ.get('CHROMA_ENDPOINT')
CHROMA_SERVER_AUTHN_CREDENTIALS = os.environ.get('CHROMA_SERVER_AUTHN_CREDENTIALS')

headers = {
    'X-Chroma-Token': CHROMA_SERVER_AUTHN_CREDENTIALS,
    'Content-Type': 'application/json'
}
embedding_function = OpenAIEmbeddings()
# sample_text = "Sample text to check embedding size."
# embedding = embedding_function.embed_documents([sample_text])
# print(f"Embedding size: {len(embedding[0])}")

class ChromaEmbeddingFunction(EmbeddingFunction):
    def __init__(self):
        self.embedding_function = OpenAIEmbeddings()

    def __call__(self, input):
        # Ensure that the input is a list of strings
        if not isinstance(input, list):
            input = [input]
        return self.embedding_function.embed_documents(input)
    
    def get_dimension(self):
        return self.embedding_function.get_dimension()
    

# PROMPT_TEMPLATE = """
# Answer the question based only on the following context:

# {context}

# ---

# Answer the question based on the above context: {question}
# """


PROMPT_TEMPLATE = """
You are a helpful and knowledgeable assistant, working for a business. Use the information provided below to answer the question.
Strive for a natural, conversational tone in your answer. Do not explicitly mention that your answer is based on 'the provided context' or 'the information given'. If you don't find an answer in the supplied context, simply state that you don't know the answer. Do not make things up just to be helpful.

Information:
{context}

---

Question: {question}
Answer:
"""


def prepare_db_and_perform_query(query, account_unique_id, session: Session):
    """
    Main function performing the query"""

    query_text = query
    
    statement = select(Account).filter(Account.account_unique_id == account_unique_id)
    result = session.exec(statement)
    account = result.first()
    print(f"account: {account}")
    relevance_score = account.relevance_score
    k_value = account.k_value

    db = prepare_db(account_unique_id)

    result = search_db(db, query_text, relevance_score, k_value, account_unique_id)

    return result


def query_source_data(query: str, account_unique_id: str, session: Session):
    """
    Query Source Data and de-duplicate sources.
    """
    if not query:
        return {"error": "No query provided"}
    
    # This variable holds the entire dictionary returned by your query engine
    query_engine_response = prepare_db_and_perform_query(query, account_unique_id, session)
    
    
    # Check if query_engine_response is a dictionary and has a 'sources' key,
    # and if 'sources' is a list. This makes the de-duplication robust.
    if isinstance(query_engine_response, dict) and \
       'sources' in query_engine_response and \
       isinstance(query_engine_response.get('sources'), list):
        
        original_sources: List[str] = query_engine_response['sources']
        
        if original_sources: # Only process if the list is not empty
            # For Python 3.7+, dict.fromkeys preserves insertion order and creates unique keys.
            # Converting it back to a list gives unique sources in their original order of appearance.
            unique_sources = list(dict.fromkeys(original_sources))
            
            # Update the 'sources' in the query_engine_response dictionary
            query_engine_response['sources'] = unique_sources
        else:
            print("Sources list is empty, no de-duplication needed.")
            
    else:
        # This handles cases where query_engine_response is not a dict, 
        # 'sources' key is missing, or 'sources' is not a list.
        print(f"Warning: 'sources' key not found, not a list, or response is not a dict. Skipping de-duplication. query_engine_response: {query_engine_response}")

    # Return the final structure with the query and the (potentially modified) response
    return {
        "query": query,
        "response": query_engine_response 
    }


def prepare_db(account_unique_id):
    """
    Prepare the DB
    """
    embedding_function = OpenAIEmbeddings()
    
    if ENVIRONMENT == 'development':
        chroma_path = f"./chroma/{account_unique_id}"
        db = Chroma(persist_directory=chroma_path, embedding_function=embedding_function)
    else:
        response_data = requests.get(f'{CHROMA_ENDPOINT}/collections/collection-{account_unique_id}', headers=headers).json()
        collection_id = response_data.get('id', None)
        
        data = {
            "name": (f"collection-{account_unique_id}"),
            }
        db = requests.post(f'{CHROMA_ENDPOINT}/collections/{collection_id}/get', headers=headers, json=data)
        print(f"db: {db}")
        # Assuming 'db' is the response object
        if db.status_code == 200:
            print(f"Type of db_data: {type(db)}")
        else:
            print(f"Failed to retrieve data: {db.status_code} - {db.text}")
    return db


def search_db(db, query, relevance_score, k_value, account_unique_id):
    """
    Search the DB
    """
    print(f"Relevant score: {relevance_score}")
    print(f"k value: {k_value}")
    print(f"Type of db: {type(db)}")
    
    embedding_function = ChromaEmbeddingFunction()
    
    if ENVIRONMENT == 'development':
        results = db.similarity_search_with_relevance_scores(query, k=k_value)
        if len(results) == 0 or results[0][1] < relevance_score:
            return f"Unable to find matching results for: {query}"
    
    else:
        client = chromadb.HttpClient(host='https://fastapi-rag-chroma.onrender.com', port=8000, headers=headers)
        db_data = db.json()  # Extract the JSON data from the response
        collection_name = f'collection-{account_unique_id}'
        print(f"Collection name: {collection_name}")
        collection = client.get_collection(name=collection_name, embedding_function=embedding_function)

        # Use the query method to perform the search
        results = collection.query(
            query_texts=query,  # Pass the query as text
            n_results=k_value,   # Specify the number of results to return
            include=["metadatas", "documents", "distances"],  # Include relevant fields
        )

    # Log the results to inspect the structure
    print(f"Query results: {results}")

    # Adjust based on the actual structure of results
    if isinstance(results, dict):
        # Extract the first element of documents list
        documents = results.get("documents", [[]])[0]  # Get the first sublist
    else:
        documents = []

    # Create context text from the list of document strings
    context_text = "\n\n---\n\n".join(doc for doc in documents)

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query)

    model = ChatOpenAI(model=CHAT_MODEL_NAME)
    response_text = model.predict(prompt)

    # Collect source metadata from the first element of metadatas
    sources = [meta.get("source", None) for meta in results.get("metadatas", [[]])[0]]

    return {
        "query": query,
        "response_text": response_text,
        "sources": sources,
    }