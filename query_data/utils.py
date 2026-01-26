import httpx
import os
import json
from urllib.parse import urlparse
from sqlmodel import Session
from sqlmodel.sql.expression import select
from integration.models import ScoreCardResult
from .query_data_schema import Query
import chat_messages.utils as chat_utils
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

# async def call_repo_b(query_payload: Query):
#     """
#     Call to ExpertEcho Agents Service
#     """
#     headers = {
#         "x-api-key": REPO_B_API_KEY,
#         "Content-Type": "application/json"
#     }
#     print('Query being sent: ', query_payload)
#     print('Query being sent model_dump: ', query_payload.model_dump())
#     print('Headers: ', headers)
#     print('Repo B URL: ', REPO_B_URL)
#     async with httpx.AsyncClient(timeout=60.0) as client:
#         try:
            
#             response = await client.post(
#                 REPO_B_URL, 
#                 json=query_payload.model_dump(),
#                 headers=headers
#             )
            
#             # Check if the response was successful
#             print('response: ', response)
#             response.raise_for_status()
            
#             # Check if response has content before trying to parse JSON
#             if not response.text.strip():
#                 return {"error": "Empty response from Repo B"}
            
#             # Try to parse JSON
#             try:
#                 return response.json()
#             except json.JSONDecodeError as json_err:
#                 return {"error": "Invalid JSON response from Repo B", "content": response.text}
                
#         except httpx.HTTPStatusError as http_err:
#             # Try to parse error response as JSON if possible
#             try:
#                 error_data = http_err.response.json()
#                 return {"error": f"HTTP {http_err.response.status_code}", "details": error_data}
#             except json.JSONDecodeError:
#                 return {"error": f"HTTP {http_err.response.status_code}", "details": http_err.response.text}
                
#         except httpx.RequestError as req_err:
#             return {"error": "Request failed", "details": str(req_err)}
        
#         except Exception as e:
#             return {"error": "Unexpected error", "details": str(e)}

    

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


def generate_wordcloud_data(account_unique_id:str,session: Session):
    """
    Fetch chats for the last 7 days and generate wordcloud data
    """

    chats_sessions = chat_utils.get_chat_sessions_last_7_days(account_unique_id, session)

    if not chats_sessions:
        return {"error": "No chat sessions found for the last 7 days"}
    chats = []
    for chat_session in chats_sessions:
        chat_messages = chat_utils.get_chat_messages_for_chat_session(chat_session.id, session)
        for message in chat_messages:
            chat = [message]
            chats.append(chat)
    wordcloud_data = {}

    # Generate wordcloud data from chat messages
    for chat in chats:
        for message in chat:
            words = message.content.split()
            for word in words:
                wordcloud_data[word] = wordcloud_data.get(word, 0) + 1

    return wordcloud_data