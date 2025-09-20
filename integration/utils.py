import hashlib
import hmac
from urllib.parse import urlparse
from fastapi import HTTPException
from sqlmodel import Session
from sqlmodel.sql.expression import select


SIGNING_SECRET = "12345"


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

def validate_webhook_signature(signature: str, body: bytes):
    """
    Validate incoming ScoreApp webhook signature with enhanced debugging.
    """
    print("=== SIGNATURE VALIDATION DEBUG ===")
    print("SECRET: ", repr(SIGNING_SECRET))  # Use repr to see exact string
    print("SECRET length:", len(SIGNING_SECRET))
    print("SECRET type:", type(SIGNING_SECRET))
    
    # Use raw bytes approach (matches ScoreApp's Python Flask example)
    computed_signature = hmac.new(
        SIGNING_SECRET.encode(), 
        body, 
        hashlib.sha256
    ).hexdigest()

    print("Signature header:", signature)
    print("Signature header length:", len(signature))
    print("Computed signature:", computed_signature)
    print("Computed signature length:", len(computed_signature))
    print("Body bytes length:", len(body))
    print("Body first 100 chars:", body.decode('utf-8')[:100])
    print("Body last 50 chars:", body.decode('utf-8')[-50:])
    
    # Test with known working secret from our previous success
    test_working_signature = hmac.new(
        "12345".encode(), 
        body, 
        hashlib.sha256
    ).hexdigest()
    print("Test with '12345':", test_working_signature)
    
    # Character by character comparison for debugging
    if len(signature) == len(computed_signature):
        print("Character-by-character comparison:")
        for i, (a, b) in enumerate(zip(signature, computed_signature)):
            if a != b:
                print(f"  Position {i}: received='{a}' computed='{b}'")
                break
        else:
            print("  All characters match (this shouldn't happen if validation fails)")
    
    print("=== END DEBUG ===")

    if not hmac.compare_digest(signature, computed_signature):
        print("❌ Signature validation FAILED")
        raise HTTPException(status_code=401, detail="Invalid signature")

    print("✅ Webhook signature matched")
    return True

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