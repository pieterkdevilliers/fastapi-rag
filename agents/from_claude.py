import os
import requests
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from sqlmodel import select, Session
from dotenv import load_dotenv
import openai
import chromadb
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from accounts.models import Account
from accounts.utils import get_most_recent_prompt

load_dotenv()

# === Environment & API Keys ===
openai.api_key = os.environ['OPENAI_API_KEY']
CHAT_MODEL_NAME = os.environ.get('OPENAI_CHAT_MODEL', 'gpt-3.5-turbo')
print(f"Using OpenAI chat model: {CHAT_MODEL_NAME}")

ENVIRONMENT = os.environ.get('ENVIRONMENT')
CHROMA_ENDPOINT = os.environ.get('CHROMA_ENDPOINT')
CHROMA_SERVER_AUTHN_CREDENTIALS = os.environ.get('CHROMA_SERVER_AUTHN_CREDENTIALS')

HEADERS = {
    'X-Chroma-Token': CHROMA_SERVER_AUTHN_CREDENTIALS,
    'Content-Type': 'application/json'
}

# === STEP 1: Pydantic Models ===
class RAGQueryInput(BaseModel):
    query: str
    k_value: Optional[int] = None
    relevance_score: Optional[float] = None

class RAGQueryOutput(BaseModel):
    query: str
    response_text: str
    sources: List[str]
    context_used: str

class ChatMessage(BaseModel):
    sender_type: str
    message_text: str

# === STEP 2: Agent State ===
@dataclass
class AgentState:
    account_unique_id: str
    session: Session
    account: Account
    chat_history: List[ChatMessage]

    def __post_init__(self):
        if not self.account:
            stmt = select(Account).filter(Account.account_unique_id == self.account_unique_id)
            result = self.session.exec(stmt)
            self.account = result.first()
            if not self.account:
                raise ValueError(f"Account not found: {self.account_unique_id}")

# === STEP 3: ChromaDB Helper ===
def prepare_db(account_unique_id: str):
    """
    Returns a Chroma collection or local DB connection.
    """
    if ENVIRONMENT == 'development':
        # Local Chroma
        from chromadb import PersistentClient
        client = PersistentClient(path=f"./chroma/{account_unique_id}")
        return client.get_collection(name=f"collection-{account_unique_id}")
    else:
        # Remote Chroma HTTP API
        response = requests.get(f'{CHROMA_ENDPOINT}/collections/collection-{account_unique_id}', headers=HEADERS)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch collection: {response.text}")
        return response.json()

def embed_text(texts: List[str]) -> List[List[float]]:
    """Get embeddings from OpenAI"""
    response = openai.Embedding.create(
        input=texts,
        model="text-embedding-3-small"
    )
    return [item['embedding'] for item in response['data']]

def similarity_search(db, query: str, k: int, relevance_score: float):
    """
    Perform similarity search directly against Chroma DB (local or remote).
    Returns documents, metadata.
    """
    query_embedding = embed_text([query])[0]

    if ENVIRONMENT == 'development':
        # Local Chroma
        results = db.query(query_embeddings=[query_embedding], n_results=k, include=["documents", "metadatas", "distances"])
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
    else:
        # Remote Chroma HTTP API
        collection_name = f'collection-{db["name"].split("-")[-1]}'
        payload = {
            "query_embeddings": [query_embedding],
            "n_results": k,
            "include": ["documents", "metadatas", "distances"]
        }
        response = requests.post(f"{CHROMA_ENDPOINT}/collections/{collection_name}/query", headers=HEADERS, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Chroma query failed: {response.text}")
        res = response.json()
        documents = res.get("documents", [[]])[0]
        metadatas = res.get("metadatas", [[]])[0]
        distances = res.get("distances", [[]])[0]

    # Filter by relevance_score
    filtered_docs = [
        (doc, meta) for doc, meta, dist in zip(documents, metadatas, distances)
        if 1 - dist >= relevance_score
    ]

    if not filtered_docs:
        return [], []

    docs, metas = zip(*filtered_docs)
    return list(docs), list(metas)

# === STEP 4: Pydantic-AI Agent ===
agent = Agent(
    f"openai:{CHAT_MODEL_NAME}",
    system_prompt="""
You are an intelligent assistant with access to a knowledge base through a RAG system.
Use the 'rag_search' tool if the user query requires specific knowledge.
Always be clear, helpful, and cite sources when relevant.
"""
)

@agent.tool
async def rag_search(ctx: RunContext[AgentState], query_input: RAGQueryInput) -> RAGQueryOutput:
    state = ctx.deps
    account = state.account

    k_value = query_input.k_value or account.k_value
    relevance_score = query_input.relevance_score or account.relevance_score
    temperature = account.temperature

    db = prepare_db(account.account_unique_id)

    documents, metadatas = similarity_search(db, query_input.query, k=k_value, relevance_score=relevance_score)
    if not documents:
        return RAGQueryOutput(
            query=query_input.query,
            response_text=f"Unable to find matching results for: {query_input.query}",
            sources=[],
            context_used=""
        )

    context_text = "\n\n---\n\n".join(documents)
    sources = [meta.get("source", "Unknown") for meta in metadatas if isinstance(meta, dict)]

    # Construct prompt
    prompt_text = get_most_recent_prompt(account.account_unique_id, state.session).prompt_text
    history_text = "\n".join(f"{m.sender_type.capitalize()}: {m.message_text}" for m in state.chat_history)
    full_prompt = f"""
Prompt Text:
{prompt_text}

---

Chat History:
{history_text}

Information:
{context_text}

---

Question: {query_input.query}
Answer:
"""

    # Call OpenAI directly
    completion = openai.ChatCompletion.create(
        model=CHAT_MODEL_NAME,
        messages=[{"role": "user", "content": full_prompt}],
        temperature=temperature
    )

    response_text = completion.choices[0].message.content.strip()

    return RAGQueryOutput(
        query=query_input.query,
        response_text=response_text,
        sources=sources,
        context_used=context_text
    )

# === STEP 5: Agent State Helpers ===
def create_agent_state(account_unique_id: str, session: Session, chat_history: Optional[List[Dict]] = None) -> AgentState:
    structured_history = []
    if chat_history:
        structured_history = [ChatMessage(sender_type=m.get("sender_type", "user"), message_text=m.get("message_text", "")) for m in chat_history]
    return AgentState(account_unique_id=account_unique_id, session=session, account=None, chat_history=structured_history)

async def query_agent(query: str, agent_state: AgentState) -> Dict[str, Any]:
    agent_state.chat_history.append(ChatMessage(sender_type="user", message_text=query))
    result = await agent.run(query, deps=agent_state)
    agent_state.chat_history.append(ChatMessage(sender_type="assistant", message_text=result.data))
    return {"query": query, "response": result.data, "tool_calls": [call for call in result.all_messages() if hasattr(call, "tool_name")]}

# === STEP 6: Backwards Compatibility ===
async def query_source_data(query: str, account_unique_id: str, session: Session, chat_history: Optional[List[Dict[str, Any]]] = None):
    agent_state = create_agent_state(account_unique_id, session, chat_history)
    import asyncio
    result = await query_agent(query, agent_state)
    return {"query": query, "response": {"response_text": result["response"], "sources": []}}
