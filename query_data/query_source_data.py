import argparse
import os
import requests
# from dataclasses import dataclass
from sqlmodel import select, Session
from accounts.models import Account
from accounts.utils import get_most_recent_prompt
import query_data.utils as query_utils
from typing import List, Optional, Dict, Any
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from chromadb.api.types import EmbeddingFunction
from chromadb.config import Settings
import chromadb
import openai 
from dotenv import load_dotenv


load_dotenv()

openai.api_key = os.environ['OPENAI_API_KEY']
CHAT_MODEL_NAME = os.environ.get('OPENAI_CHAT_MODEL', 'gpt-3.5-turbo')
print(f"Using OpenAI chat model: {CHAT_MODEL_NAME}")

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



PROMPT_TEMPLATE = """

Prompt Text:
{prompt_text}

---

ScoreApp Report:
{scoreapp_report}

---

Chat History:
{history}

Information:
{context}

---

Question: {question}
Answer:
"""


def prepare_db_and_perform_query(query,
                                 visitor_email,
                                 account_unique_id,
                                 session: Session,
                                 chat_history: list = None):
    """
    Main function performing the query"""

    query_text = query
    
    statement = select(Account).filter(Account.account_unique_id == account_unique_id)
    result = session.exec(statement)
    account = result.first()
    print(f"account: {account}")
    relevance_score = account.relevance_score
    k_value = account.k_value
    temperature = account.temperature

    db = prepare_db(account_unique_id)


    prompt_text = get_most_recent_prompt(account_unique_id, session).prompt_text

    result = search_db(db, query_text, relevance_score, k_value, account_unique_id, visitor_email, session, chat_history=chat_history, prompt_text=prompt_text, temperature=temperature)

    return result


def query_source_data(query: str,
                      visitor_email: str,
                      account_unique_id: str,
                      session: Session,
                      chat_history: Optional[List[Dict[str, Any]]] = None):
    """
    Query Source Data and de-duplicate sources.
    """
    if not query:
        return {"error": "No query provided"}
    
    # This variable holds the entire dictionary returned by your query engine
    query_engine_response = prepare_db_and_perform_query(query, visitor_email, account_unique_id, session, chat_history=chat_history)
    
    
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
    Prepare the DB.
    - Local dev uses embedded Chroma (duckdb+parquet) with persistence.
    - Other environments use remote Chroma HTTP API.
    """

    if ENVIRONMENT == 'development':
        print("Using local embedded Chroma DB")
        chroma_path = f"./chroma/{account_unique_id}"

        # Ensure the directory exists
        os.makedirs(chroma_path, exist_ok=True)

        # Simple approach - just use PersistentClient
        client = chromadb.PersistentClient(path=chroma_path)
        
        db = Chroma(
            client=client,
            embedding_function=embedding_function
        )
    else:
        # Remote Chroma HTTP API
        response_data = requests.get(
            f'{CHROMA_ENDPOINT}/collections/collection-{account_unique_id}',
            headers=headers
        ).json()

        collection_id = response_data.get('id', None)
        data = {"name": f"collection-{account_unique_id}"}
        db = requests.post(
            f'{CHROMA_ENDPOINT}/collections/{collection_id}/get',
            headers=headers,
            json=data,
        )

        if db.status_code != 200:
            print(f"Failed to retrieve data: {db.status_code} - {db.text}")
        else:
            print(f"Retrieved remote collection for account {account_unique_id}")

    return db


def search_db(db, query, relevance_score, k_value, account_unique_id, visitor_email, session, chat_history=None, prompt_text=None, temperature=0.2):
    """
    Search the DB
    """
    print(f"Relevant score: {relevance_score}")
    print(f"k value: {k_value}")
    print(f"Type of db: {type(db)}")
    print(f"Temperature: {temperature}")
    
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

    # Build chat history text
    history_text = ""
    if chat_history:
        history_text = "\n".join(
            f"{(msg.sender_type if hasattr(msg, 'sender_type') else msg['sender_type']).capitalize()}: "
            f"{(msg.message_text if hasattr(msg, 'message_text') else msg['message_text'])}"
            for msg in chat_history
        )

    scoreapp_report_text = query_utils.get_scoreapp_report(account_unique_id, visitor_email, session)
    print('************CoreApp Report Text: ', scoreapp_report_text)

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(
        history=history_text,
        context=context_text,
        question=query,
        prompt_text=prompt_text,
        scoreapp_report=scoreapp_report_text,
    )

    print(f"Final prompt to LLM: {prompt}")

    model = ChatOpenAI(model=CHAT_MODEL_NAME, temperature=temperature)

    # NEW
    result = model.invoke(prompt)

    # Ensure it's always a string
    if isinstance(result, str):
        response_text = result
    elif hasattr(result, "content"):  # BaseMessage
        response_text = result.content
    elif isinstance(result, dict) and "text" in result:
        response_text = result["text"]
    else:
        response_text = str(result)  # fallback

    # Collect source metadata from the first element of metadatas
    sources = [meta.get("source", None) for meta in results.get("metadatas", [[]])[0]]

    return {
        "query": query,
        "response_text": response_text,
        "sources": sources,
    }