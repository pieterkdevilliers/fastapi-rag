from pydantic import BaseModel
from typing import Any,  List, Dict


class Query(BaseModel):
    """
    Basic Query Structure
    """
    query: str
    prompt: str
    visitor_email: str
    visitor_uuid: str
    account_unique_id: str
    chat_history: List[Dict[str, Any]]
    relevance_score: float
    k_value: int
    sources_returned: int
    temperature: float
    chat_session_id: str
    scoreapp_report_text: Dict
    user_products_prompt: str