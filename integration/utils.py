import hashlib
import hmac
import json
from fastapi import HTTPException
from sqlmodel import Session
from sqlmodel.sql.expression import select


SIGNING_SECRET = "12345"

def validate_webhook_signature(signature: str, body: bytes):
    """
    Validate incoming ScoreApp webhook signature.
    """
    print("SECRET: ", SIGNING_SECRET)
    
    # Try multiple approaches based on ScoreApp documentation inconsistencies
    
    # Approach 1: Raw bytes (like Flask example)
    computed_signature_1 = hmac.new(
        SIGNING_SECRET.encode(), 
        body, 
        hashlib.sha256
    ).hexdigest()
    
    # Approach 2: Parse JSON then stringify (like Node.js example)
    try:
        parsed_json = json.loads(body.decode('utf-8'))
        json_string = json.dumps(parsed_json, separators=(',', ':'))  # Compact JSON
        computed_signature_2 = hmac.new(
            SIGNING_SECRET.encode(), 
            json_string.encode('utf-8'), 
            hashlib.sha256
        ).hexdigest()
    except:
        computed_signature_2 = "JSON_PARSE_ERROR"
    
    # Approach 3: JSON with spaces (default Python formatting)
    try:
        parsed_json = json.loads(body.decode('utf-8'))
        json_string_spaced = json.dumps(parsed_json)  # Default formatting
        computed_signature_3 = hmac.new(
            SIGNING_SECRET.encode(), 
            json_string_spaced.encode('utf-8'), 
            hashlib.sha256
        ).hexdigest()
    except:
        computed_signature_3 = "JSON_PARSE_ERROR"

    print("Signature header:", signature)
    print("Approach 1 (raw bytes):", computed_signature_1)
    print("Approach 2 (compact JSON):", computed_signature_2)  
    print("Approach 3 (spaced JSON):", computed_signature_3)
    print("Body bytes length:", len(body))
    print("Body content:", body.decode('utf-8')[:200])

    # Check all approaches
    if (hmac.compare_digest(signature, computed_signature_1) or 
        hmac.compare_digest(signature, computed_signature_2) or
        hmac.compare_digest(signature, computed_signature_3)):
        print("✅ Webhook signature matched")
        return True
    
    raise HTTPException(status_code=401, detail="Invalid signature")



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