import httpx
import os
import json
from urllib.parse import urlparse
from sqlmodel import Session
from sqlmodel.sql.expression import select
from integration.models import ScoreCardResult
from .query_data_schema import Query
import chat_messages.utils as chat_utils
from wordcloud import STOPWORDS
from collections import Counter
import re
from dotenv import load_dotenv
load_dotenv()

REPO_B_URL = os.getenv("REPO_B_URL")
REPO_B_API_KEY = os.getenv("REPO_B_API_KEY")

# Modified utility function to stream from Repo B
async def call_repo_b_stream(query_payload: Query):
    """
    Stream response from Repo B (ExpertEcho Agents Service)
    """
    headers = {
        "x-api-key": REPO_B_API_KEY,
        "Content-Type": "application/json"
    }
    
    print('Query being sent for streaming: ', query_payload)
    print('Headers: ', headers)
    print('Repo B URL: ', REPO_B_URL)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream(
                "POST",
                f"{REPO_B_URL}",
                json=query_payload.model_dump(),
                headers=headers
            ) as response:
                response.raise_for_status()
                
                # Stream SSE events from Repo B
                buffer = ""
                async for raw_line in response.aiter_raw():
                    buffer += raw_line.decode("utf-8")
                    while "\n\n" in buffer:
                        event, buffer = buffer.split("\n\n", 1)
                        if event.startswith("data: "):
                            try:
                                data = json.loads(event[6:])
                                yield data
                            except json.JSONDecodeError:
                                print(f"Failed to parse SSE data: {raw_line}")
                                continue
                            
        except httpx.HTTPStatusError as http_err:
            yield {
                "type": "error",
                "content": f"HTTP {http_err.response.status_code}: {http_err.response.text}"
            }
        except httpx.RequestError as req_err:
            yield {
                "type": "error",
                "content": f"Request failed: {str(req_err)}"
            }
        except Exception as e:
            yield {
                "type": "error",
                "content": f"Unexpected error: {str(e)}"
            }


async def get_initial_query_sentiment(query_payload: Query):
    """
    Get initial sentiment analysis from Repo B for the given query
    """
    headers = {
        "x-api-key": REPO_B_API_KEY,
        "Content-Type": "application/json"
    } 

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{REPO_B_URL}/initial-question-sentiment",
                json=query_payload.model_dump(),
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error calling Repo B: {e}")
            return {"error": str(e)}


def normalize_origin(origin: str) -> str:
    """
    Normalizes an origin URL for consistent comparison.

    - Strips protocol (http://, https://).
    - Strips 'www.' subdomain.
    - Handles cases where no protocol is given.
    - Returns the cleaned hostname.

    Examples:
        'https://www.mydomain.com' -> 'mydomain.com'
        'https://mydomain.com'     -> 'mydomain.com'
        'http://mydomain.com'      -> 'mydomain.com'
        'mydomain.com'             -> 'mydomain.com'
    """
    if not origin or not isinstance(origin, str):
        return ""

    # urlparse works best if a scheme is present.
    # If not, we add a dummy one to parse the netloc correctly.
    if not origin.startswith(('http://', 'https://')):
        parsed = urlparse(f"//{origin.strip()}", scheme="https")
    else:
        parsed = urlparse(origin.strip())
    
    hostname = parsed.hostname
    
    if not hostname:
        return ""

    # Remove 'www.' prefix if it exists
    if hostname.startswith("www."):
        hostname = hostname[4:]
        
    return hostname.lower()


def get_scoreapp_report(accout_unique_id: str, visitor_email: str, session: Session):
    """
    Retrieve the visitor's ScoreApp Report if one exists
    """
    statement = select(ScoreCardResult).where(ScoreCardResult.account_unique_id == accout_unique_id, ScoreCardResult.email == visitor_email)
    result = session.exec(statement)
    scoreapp_report = result.first()
    if scoreapp_report:
        scoreapp_report_text = scoreapp_report.extracted_report_text
    else:
        scoreapp_report_text = ""
    return {"scoreapp_report_text": scoreapp_report_text}


def generate_wordcloud_data(account_unique_id: str, session: Session) -> dict:
    """
    Generate wordcloud data from chat messages in the last 7 days for the given account
    """
    chats_sessions = chat_utils.get_chat_sessions_last_7_days(account_unique_id, session)
    if not chats_sessions:
        return {}

    all_text = []

    for chat_session in chats_sessions:
        messages = chat_utils.get_chat_messages_for_chat_session(chat_session.id, session)
        for msg in messages:
            # Clean a bit – adjust as needed
            text = re.sub(r'[^a-zA-Z\s]', '', msg.message_text.lower())
            all_text.append(text)

    if not all_text:
        return {}

    # Count frequencies properly
    words = " ".join(all_text).split()
    freq = Counter(w for w in words if w not in STOPWORDS and len(w) > 2)

    return dict(freq.most_common(500))