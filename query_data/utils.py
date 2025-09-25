from urllib.parse import urlparse
from sqlmodel import Session
from sqlmodel.sql.expression import select
from integration.models import ScoreCardResult

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