import argparse
import os
# from dataclasses import dataclass
from sqlmodel import select, Session
from accounts.models import Account
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import openai 
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.environ['OPENAI_API_KEY']

CHROMA_PATH = "chroma"

PROMPT_TEMPLATE = """
Answer the question based only on the following context:

{context}

---

Answer the question based on the above context: {question}
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

    result = search_db(db, query_text, relevance_score, k_value)

    return result


def query_source_data(query, account_unique_id, session: Session):
    """
    Query Source Data
    """
    if not query:
        return {"error": "No query provided"}
    
    response = prepare_db_and_perform_query(query, account_unique_id, session)
    return {
        "query": query,
        "response": response
        }


def prepare_db(account_unique_id):
    """
    Prepare the DB
    """
    embedding_function = OpenAIEmbeddings()
    chroma_path = f"./chroma/{account_unique_id}"
    db = Chroma(persist_directory=chroma_path, embedding_function=embedding_function)
    return db


def search_db(db, query, relevance_score, k_value):
    """
    Search the DB
    """
    print(f"relevant score: {relevance_score}")
    print(f"k value: {k_value}")
    results = db.similarity_search_with_relevance_scores(query, k=k_value)
    if len(results) == 0 or results[0][1] < relevance_score:
        return (f"Unable to find matching results for: {query}")
    
    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query)

    model = ChatOpenAI()
    response_text = model.predict(prompt)

    sources = [doc.metadata.get("source", None) for doc, _score in results]

    return {
        "query": query,
        "response_text": response_text,
        "sources": sources
    }