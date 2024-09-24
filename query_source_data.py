import argparse
import os
# from dataclasses import dataclass
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


def prepare_db_and_perform_query(query):
    """
    Main function performing the query"""

    query_text = query

    db = prepare_db()

    result = search_db(db, query_text)

    return result


def query_source_data(query):
    """
    Query Source Data
    """
    if not query:
        return {"error": "No query provided"}
    
    response = prepare_db_and_perform_query(query)
    return {
        "query": query,
        "response": response
        }


def prepare_db():
    """
    Prepare the DB
    """
    embedding_function = OpenAIEmbeddings()
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)
    return db


def search_db(db, query):
    """
    Search the DB
    """
    results = db.similarity_search_with_relevance_scores(query, k=3)
    if len(results) == 0 or results[0][1] < 0.7:
        print(f"Unable to find matching results for: {query}")
        return (f"Unable to find matching results for: {query}")
    
    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query)

    model = ChatOpenAI()
    response_text = model.predict(prompt)

    sources = [doc.metadata.get("source", None) for doc, _score in results]

    return {
        "query": query,
        "response": response_text,
        "sources": sources
    }