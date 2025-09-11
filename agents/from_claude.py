import os
import requests
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from accounts.models import Account
from sqlmodel import select, Session
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

import openai
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.environ['OPENAI_API_KEY']
CHAT_MODEL_NAME = os.environ.get('OPENAI_CHAT_MODEL', 'gpt-3.5-turbo')
print(f"Using OpenAI chat model: {CHAT_MODEL_NAME}")

CHROMA_ENDPOINT = os.environ.get('CHROMA_ENDPOINT')
CHROMA_SERVER_AUTHN_CREDENTIALS = os.environ.get('CHROMA_SERVER_AUTHN_CREDENTIALS')
ENVIRONMENT = os.environ.get('ENVIRONMENT')

HEADERS = {
    'X-Chroma-Token': CHROMA_SERVER_AUTHN_CREDENTIALS,
    'Content-Type': 'application/json'
}


# === STEP 1: Define Pydantic Models ===

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
    sender_type: str  # "user" or "assistant"
    message_text: str


# === STEP 2: Define Agent State ===

@dataclass
class AgentState:
    account_unique_id: str
    session: Session
    account: Any
    chat_history: List[ChatMessage]
    account_model: Optional[Any] = None  # <-- add this

    def __post_init__(self):
        if not self.account:
            if not self.account_model:
                raise ValueError("account_model must be provided to fetch account from DB")
            statement = select(self.account_model).filter(
                self.account_model.account_unique_id == self.account_unique_id
            )
            result = self.session.exec(statement)
            self.account = result.first()
            if not self.account:
                raise ValueError(f"Account not found: {self.account_unique_id}")



# === STEP 3: Embedding Helper ===

def embed_text(texts: list[str]) -> list[list[float]]:
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )
    return [e.embedding for e in response.data]


# === STEP 4: Similarity Search ===

async def similarity_search(
    db,
    query: str,
    k: int,
    relevance_score: float
):
    """
    Perform a vector similarity search using local or remote Chroma.
    Returns documents and metadata.
    """
    query_embedding = (embed_text([query]))[0]

    if ENVIRONMENT == 'development':
        results = db.similarity_search_with_relevance_scores(query, k=k)
        if len(results) == 0 or results[0][1] < relevance_score:
            return [], []
        documents = [doc.page_content for doc, _ in results]
        metadatas = [doc.metadata for doc, _ in results]
    else:
        # Remote Chroma via HTTP
        client_resp = requests.post(
            f"{CHROMA_ENDPOINT}/collections/collection-{db}/query",
            headers=HEADERS,
            json={"query_embeddings": [query_embedding], "n_results": k}
        )
        client_data = client_resp.json()
        documents = client_data.get("documents", [[]])[0]
        metadatas = client_data.get("metadatas", [[]])[0]

    return documents, metadatas


# === STEP 5: Prepare DB ===

def prepare_db(account_unique_id: str):
    if ENVIRONMENT == "development":
        from langchain_chroma import Chroma  # only for local dev
        from langchain_openai import OpenAIEmbeddings
        embedding_fn = OpenAIEmbeddings()
        chroma_path = f"./chroma/{account_unique_id}"
        return Chroma(persist_directory=chroma_path, embedding_function=embedding_fn)
    else:
        return account_unique_id  # for remote HTTP query


# === STEP 6: Pydantic-AI Agent ===

agent = Agent(
    f"openai:{CHAT_MODEL_NAME}",
    system_prompt="""You are an intelligent assistant with access to a knowledge base via a RAG system.
If the question requires retrieval, use the 'rag_search' tool."""
)


@agent.tool
async def rag_search(ctx: RunContext[AgentState], query_input: RAGQueryInput) -> RAGQueryOutput:
    state = ctx.deps
    account = state.account

    k_value = query_input.k_value or account.k_value
    relevance_score = query_input.relevance_score or account.relevance_score

    db = prepare_db(account.account_unique_id)
    documents, metadatas = await similarity_search(
        db, query_input.query, k=k_value, relevance_score=relevance_score
    )

    if not documents:
        return RAGQueryOutput(
            query=query_input.query,
            response_text=f"No results found for query: {query_input.query}",
            sources=[],
            context_used=""
        )

    # Merge context
    context_text = "\n\n---\n\n".join(documents)

    # Build prompt with chat history
    history_text = "\n".join(
        f"{msg.sender_type.capitalize()}: {msg.message_text}" for msg in state.chat_history
    )

    prompt = f"""
Prompt Text:
Use the retrieved context to answer the user question.

---

Chat History:
{history_text}

Information:
{context_text}

---

Question: {query_input.query}
Answer:
"""

    # Query OpenAI chat model
    chat_response = await openai.chat.completions.create(
        model=CHAT_MODEL_NAME,
        messages=[{"role": "system", "content": prompt}],
        temperature=account.temperature
    )

    response_text = chat_response.choices[0].message.content

    sources = [meta.get("source", "Unknown") for meta in metadatas if isinstance(meta, dict)]

    return RAGQueryOutput(
        query=query_input.query,
        response_text=response_text,
        sources=sources,
        context_used=context_text
    )


# === STEP 7: Agent State Creation ===

def create_agent_state(account_unique_id: str, session: Session, chat_history: Optional[List[Dict]] = None):
    structured_history = [
        ChatMessage(sender_type=msg.get("sender_type", "user"), message_text=msg.get("message_text", ""))
        for msg in chat_history or []
    ]
    return AgentState(
        account_unique_id=account_unique_id,
        session=session,
        account=None,
        account_model=Account,  # <- Pass the model class here
        chat_history=structured_history
    )


# === STEP 8: Query Agent ===

async def query_agent(query: str, agent_state: AgentState) -> Dict[str, Any]:
    agent_state.chat_history.append(ChatMessage(sender_type="user", message_text=query))
    result = await agent.run(query, deps=agent_state)
    agent_state.chat_history.append(ChatMessage(sender_type="assistant", message_text=result.data))
    return {"query": query, "response": result.data, "tool_calls": [call for call in result.all_messages() if hasattr(call, 'tool_name')]}


# === STEP 9: Backwards Compatibility ===

async def query_source_data(query: str, account_unique_id: str, session: Session, chat_history: Optional[List[Dict]] = None):
    agent_state = create_agent_state(account_unique_id, session, chat_history)
    result = await query_agent(query, agent_state)
    return {"query": query, "response": {"response_text": result["response"], "sources": []}}
