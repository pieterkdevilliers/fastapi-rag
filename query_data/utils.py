import httpx
import os
import json
from urllib.parse import urlparse
from sqlmodel import Session
from sqlmodel.sql.expression import select
from integration.models import ScoreCardResult
from .query_data_schema import Query
from dotenv import load_dotenv
load_dotenv()

REPO_B_URL = os.getenv("REPO_B_URL")
REPO_B_API_KEY = os.getenv("REPO_B_API_KEY")

async def call_repo_b(query_payload: Query):
    """
    Call to ExpertEcho Agents Service
    """
    headers = {
        "x-api-key": REPO_B_API_KEY,
        "Content-Type": "application/json"
    }
    print('Query being sent: ', query_payload)
    print('Query being sent model_dump: ', query_payload.model_dump())
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            
            response = await client.post(
                REPO_B_URL, 
                json=query_payload.model_dump(),
                headers=headers
            )
            
            # Check if the response was successful
            response.raise_for_status()
            
            # Check if response has content before trying to parse JSON
            if not response.text.strip():
                return {"error": "Empty response from Repo B"}
            
            # Try to parse JSON
            try:
                return response.json()
            except json.JSONDecodeError as json_err:
                return {"error": "Invalid JSON response from Repo B", "content": response.text}
                
        except httpx.HTTPStatusError as http_err:
            # Try to parse error response as JSON if possible
            try:
                error_data = http_err.response.json()
                return {"error": f"HTTP {http_err.response.status_code}", "details": error_data}
            except json.JSONDecodeError:
                return {"error": f"HTTP {http_err.response.status_code}", "details": http_err.response.text}
                
        except httpx.RequestError as req_err:
            return {"error": "Request failed", "details": str(req_err)}
        
        except Exception as e:
            return {"error": "Unexpected error", "details": str(e)}

    

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