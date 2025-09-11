import argparse
import os
import requests
from sqlmodel import select, Session
from accounts.models import Account
from accounts.utils import get_most_recent_prompt
from typing import List, Optional, Dict, Any
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from chromadb.api.types import EmbeddingFunction
import chromadb
import openai 
from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from dataclasses import dataclass

load_dotenv()

openai.api_key = os.environ['OPENAI_API_KEY']
CHAT_MODEL_NAME = os.environ.get('OPENAI_CHAT_MODEL', 'gpt-3.5-turbo')
print(f"Using OpenAI chat model: {CHAT_MODEL_NAME}")

CHROMA_PATH = "chroma"
ENVIRONMENT = os.environ.get('ENVIRONMENT')
CHROMA_ENDPOINT = os.environ.get('CHROMA_ENDPOINT')
CHROMA_SERVER_AUTHN_CREDENTIALS = os.environ.get('CHROMA_SERVER_AUTHN_CREDENTIALS')

headers = {
    'X-Chroma-Token': CHROMA_SERVER_AUTHN_CREDENTIALS,
    'Content-Type': 'application/json'
}

# === STEP 1: Define Pydantic Models for Tool Input/Output ===
# These models define the structure of data that flows in and out of our RAG tool

class RAGQueryInput(BaseModel):
    """Input model for the RAG tool - defines what data the tool needs"""
    query: str
    k_value: Optional[int] = None  # Allow override of default k_value
    relevance_score: Optional[float] = None  # Allow override of default relevance_score

class RAGQueryOutput(BaseModel):
    """Output model for the RAG tool - defines what the tool returns"""
    query: str
    response_text: str
    sources: List[str]
    context_used: str  # The actual context that was retrieved

class ChatMessage(BaseModel):
    """Model for chat history messages"""
    sender_type: str  # 'user' or 'assistant'
    message_text: str

# === STEP 2: Define Agent State ===
# This replaces the parameter passing in your original code
@dataclass
class AgentState:
    """
    Agent state holds all the persistent information across tool calls.
    This replaces the need to pass parameters like account_unique_id, session, etc.
    """
    account_unique_id: str
    session: Session
    account: Account
    chat_history: List[ChatMessage]
    
    def __post_init__(self):
        """Load account data when state is initialized"""
        if not self.account:
            statement = select(Account).filter(Account.account_unique_id == self.account_unique_id)
            result = self.session.exec(statement)
            self.account = result.first()
            if not self.account:
                raise ValueError(f"Account not found: {self.account_unique_id}")

# === STEP 3: Keep Your Existing Helper Classes ===
class ChromaEmbeddingFunction(EmbeddingFunction):
    def __init__(self):
        self.embedding_function = OpenAIEmbeddings()

    def __call__(self, input):
        if not isinstance(input, list):
            input = [input]
        return self.embedding_function.embed_documents(input)
    
    def get_dimension(self):
        return self.embedding_function.get_dimension()

# === STEP 4: Create the Pydantic-AI Agent ===
# This is the core agent that will orchestrate tool usage

agent = Agent(
    f'openai:{CHAT_MODEL_NAME}',  # Model as first argument with openai: prefix
    system_prompt="""You are an intelligent assistant with access to a knowledge base through a RAG (Retrieval-Augmented Generation) system.

When users ask questions:
1. If the question seems to require specific information from the knowledge base, use the 'rag_search' tool
2. If the question is general or conversational, you can answer directly
3. Always be helpful and provide clear, accurate responses
4. When using RAG results, cite the sources when relevant

You have access to the following tools:
- rag_search: Search the knowledge base for relevant information""",
)

# === STEP 5: Define the RAG Tool ===
# This is where we refactor your existing RAG functionality into a tool

@agent.tool
async def rag_search(ctx: RunContext[AgentState], query_input: RAGQueryInput) -> RAGQueryOutput:
    """
    Search the knowledge base using RAG.
    
    This tool takes a query and searches through the vector database to find
    relevant documents, then returns a response based on the retrieved context.
    """
    
    # Get the agent state which contains all our persistent data
    state = ctx.deps
    account = state.account
    
    # Use account defaults or provided overrides
    relevance_score = query_input.relevance_score or account.relevance_score
    k_value = query_input.k_value or account.k_value
    temperature = account.temperature
    
    print(f"RAG Tool - Account: {account.account_unique_id}")
    print(f"RAG Tool - Query: {query_input.query}")
    print(f"RAG Tool - K Value: {k_value}, Relevance Score: {relevance_score}")
    
    # Prepare database connection
    db = prepare_db(account.account_unique_id)
    
    # Get the current prompt template
    prompt_text = get_most_recent_prompt(account.account_unique_id, state.session).prompt_text
    
    # Perform the search
    result = search_db(
        db=db,
        query=query_input.query,
        relevance_score=relevance_score,
        k_value=k_value,
        account_unique_id=account.account_unique_id,
        chat_history=state.chat_history,
        prompt_text=prompt_text,
        temperature=temperature
    )
    
    # Handle the case where no results are found
    if isinstance(result, str):  # Error message
        return RAGQueryOutput(
            query=query_input.query,
            response_text=result,
            sources=[],
            context_used=""
        )
    
    # Return structured output
    return RAGQueryOutput(
        query=result["query"],
        response_text=result["response_text"],
        sources=result["sources"],
        context_used=result.get("context_used", "")  # We'll modify search_db to include this
    )

# === STEP 6: Agent Initialization Function ===
def create_agent_state(account_unique_id: str, session: Session, chat_history: List[Dict] = None) -> AgentState:
    """
    Create agent state for a specific user session.
    This replaces the parameter passing in your original query functions.
    """
    
    # Convert chat history to our Pydantic model if provided
    structured_history = []
    if chat_history:
        structured_history = [
            ChatMessage(
                sender_type=msg.get('sender_type', 'user'),
                message_text=msg.get('message_text', '')
            )
            for msg in chat_history
        ]
    
    return AgentState(
        account_unique_id=account_unique_id,
        session=session,
        account=None,  # Will be loaded in __post_init__
        chat_history=structured_history
    )

# === STEP 7: Main Agent Query Function ===
async def query_agent(query: str, agent_state: AgentState) -> Dict[str, Any]:
    """
    Main function to query the agent. This replaces your original query_source_data function.
    """
    
    # Add the current query to chat history
    agent_state.chat_history.append(ChatMessage(sender_type="user", message_text=query))
    
    # Run the agent with the query and state
    result = await agent.run(query, deps=agent_state)
    
    # Add the agent's response to chat history
    agent_state.chat_history.append(ChatMessage(sender_type="assistant", message_text=result.data))
    
    return {
        "query": query,
        "response": result.data,
        "sources": [],  # We'll extract this from tool results if RAG was used
        "tool_calls": [call for call in result.all_messages() if hasattr(call, 'tool_name')]
    }

# === STEP 8: Keep Your Existing Helper Functions (with minor modifications) ===

def prepare_db(account_unique_id):
    """
    Prepare the DB - keeping your existing logic
    """
    embedding_function = OpenAIEmbeddings()
    
    if ENVIRONMENT == 'development':
        chroma_path = f"./chroma/{account_unique_id}"
        db = Chroma(persist_directory=chroma_path, embedding_function=embedding_function)
    else:
        response_data = requests.get(f'{CHROMA_ENDPOINT}/collections/collection-{account_unique_id}', headers=headers).json()
        collection_id = response_data.get('id', None)
        
        data = {"name": (f"collection-{account_unique_id}")}
        db = requests.post(f'{CHROMA_ENDPOINT}/collections/{collection_id}/get', headers=headers, json=data)
        print(f"db: {db}")
        if db.status_code == 200:
            print(f"Type of db_data: {type(db)}")
        else:
            print(f"Failed to retrieve data: {db.status_code} - {db.text}")
    return db


def search_db(db, query, relevance_score, k_value, account_unique_id, chat_history=None, prompt_text=None, temperature=0.2):
    """
    Search the DB - modified to return context_used for better tool output
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
        
        # Extract documents and metadata for development
        documents = [doc.page_content for doc, score in results]
        metadatas = [doc.metadata for doc, score in results]
        
    else:
        client = chromadb.HttpClient(host='https://fastapi-rag-chroma.onrender.com', port=8000, headers=headers)
        collection_name = f'collection-{account_unique_id}'
        collection = client.get_collection(name=collection_name, embedding_function=embedding_function)

        results = collection.query(
            query_texts=query,
            n_results=k_value,
            include=["metadatas", "documents", "distances"],
        )
        
        # Extract documents from results
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

    # Create context text from documents
    context_text = "\n\n---\n\n".join(doc for doc in documents)

    # Build chat history text
    history_text = ""
    if chat_history:
        history_text = "\n".join(
            f"{msg.sender_type.capitalize()}: {msg.message_text}"
            for msg in chat_history
        )

    # Use your existing prompt template
    PROMPT_TEMPLATE = """
Prompt Text:
{prompt_text}

---

Chat History:
{history}

Information:
{context}

---

Question: {question}
Answer:
"""

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(
        history=history_text,
        context=context_text,
        question=query,
        prompt_text=prompt_text,
    )

    # For now, we'll use the existing LangChain approach
    # Later we can integrate this more tightly with Pydantic-AI
    from langchain_openai import ChatOpenAI
    model = ChatOpenAI(model=CHAT_MODEL_NAME, temperature=temperature)
    result = model.invoke(prompt)

    # Extract response text
    if isinstance(result, str):
        response_text = result
    elif hasattr(result, "content"):
        response_text = result.content
    elif isinstance(result, dict) and "text" in result:
        response_text = result["text"]
    else:
        response_text = str(result)

    # Collect sources
    sources = [meta.get("source", "Unknown") for meta in metadatas if isinstance(meta, dict)]

    return {
        "query": query,
        "response_text": response_text,
        "sources": sources,
        "context_used": context_text,  # Added this for better tool output
    }


# === STEP 9: Backwards Compatibility Function ===
def query_source_data(query: str,
                      account_unique_id: str,
                      session: Session,
                      chat_history: Optional[List[Dict[str, Any]]] = None):
    """
    Backwards compatible function that uses the new agent system.
    This allows you to transition gradually without breaking existing code.
    """
    
    # Create agent state
    agent_state = create_agent_state(account_unique_id, session, chat_history)
    
    # Query the agent (Note: this needs to be called from an async context)
    import asyncio
    result = asyncio.run(query_agent(query, agent_state))
    
    # Format response to match your existing API
    return {
        "query": query,
        "response": {
            "response_text": result["response"],
            "sources": result.get("sources", [])
        }
    }