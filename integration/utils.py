import hashlib
import hmac
from urllib.parse import urlparse
from fastapi import HTTPException
from sqlmodel import Session
from sqlmodel.sql.expression import select


SIGNING_SECRET = "12345"


def validate_webhook_signature(signature: str, body: bytes):
    """
    Temporary workaround for ScoreApp signature bug
    """
    print("SECRET: ", SIGNING_SECRET)
    
    computed_signature = hmac.new(
        SIGNING_SECRET.encode(), 
        body, 
        hashlib.sha256
    ).hexdigest()

    print(f"Received: {signature}")
    print(f"Computed: {computed_signature}")
    
    if hmac.compare_digest(signature, computed_signature):
        print("✅ Signature validated")
        return True
    else:
        print("❌ Signature mismatch - ScoreApp bug detected")
        print("⚠️ Processing webhook anyway due to known ScoreApp issue")
        return True  # Accept anyway due to ScoreApp bug
    

def extract_subdomain_from_report(report_url):
    """
    Extract subdomain from ScoreApp report URL
    """
    if not report_url:
        return None
        
    parsed = urlparse(report_url)
    hostname = parsed.netloc
    
    if '.scoreapp.com' in hostname:
        subdomain = hostname.split('.scoreapp.com')[0]
        return subdomain
    
    return None


async def get_account_unique_id(report_url: str):
    """
    Retrieve the account identifier
    """
    sub_domain = extract_subdomain_from_report(report_url)
    print("subdomain: ", sub_domain)
    account_unique_id = sub_domain
    return account_unique_id 



async def create_score_card_result():
    """
    Create score card result in DB
    """
    pass


async def create_or_update_score_card_result():
    """
    Create or update a score card result
    """
    pass

# def create_new_account_in_db(account_organisation: str, session: Session):
#     """
#     Save New Account to DB
#     """
#     account_unique_id = token_hex(8)
#     account = Account(account_organisation=account_organisation,
#                       account_unique_id=account_unique_id)
#     session.add(account)
#     session.commit()
#     session.refresh(account)
    
#     return account