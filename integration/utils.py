import hashlib
import hmac
import json
from fastapi import HTTPException
from sqlmodel import Session
from sqlmodel.sql.expression import select


SIGNING_SECRET = "12345"

def validate_webhook_signature_debug(signature: str, body: bytes):
    """
    Debug version - logs everything but always passes validation
    """
    print("=== SIGNATURE DEBUG ===")
    print("SECRET: ", SIGNING_SECRET)
    print("Signature header:", signature)
    print("Body bytes length:", len(body))
    print("Body content:", body.decode('utf-8'))
    
    # Try different approaches
    approaches = []
    
    # Approach 1: Raw bytes
    sig1 = hmac.new(SIGNING_SECRET.encode(), body, hashlib.sha256).hexdigest()
    approaches.append(("Raw bytes", sig1))
    
    # Approach 2: Compact JSON
    try:
        parsed = json.loads(body.decode('utf-8'))
        compact = json.dumps(parsed, separators=(',', ':'))
        sig2 = hmac.new(SIGNING_SECRET.encode(), compact.encode(), hashlib.sha256).hexdigest()
        approaches.append(("Compact JSON", sig2))
    except:
        approaches.append(("Compact JSON", "ERROR"))
    
    # Approach 3: Spaced JSON  
    try:
        parsed = json.loads(body.decode('utf-8'))
        spaced = json.dumps(parsed)
        sig3 = hmac.new(SIGNING_SECRET.encode(), spaced.encode(), hashlib.sha256).hexdigest()
        approaches.append(("Spaced JSON", sig3))
    except:
        approaches.append(("Spaced JSON", "ERROR"))
    
    print("\nComputed signatures:")
    for name, sig in approaches:
        match = "✅ MATCH" if hmac.compare_digest(signature, sig) else "❌ No match"
        print(f"{name}: {sig} {match}")
    
    # Try different secret keys (in case the secret is wrong)
    test_secrets = [
        "12345",
        "Your webhook secret key",  # Default from docs
        "",  # Empty
        "test",
        "webhook_secret"
    ]
    
    print("\nTrying different secret keys:")
    for test_secret in test_secrets:
        try:
            test_sig = hmac.new(test_secret.encode(), body, hashlib.sha256).hexdigest()
            match = "✅ MATCH" if hmac.compare_digest(signature, test_sig) else "❌ No match"
            print(f"Secret '{test_secret}': {test_sig} {match}")
        except Exception as e:
            print(f"Secret '{test_secret}': ERROR - {e}")
    
    print("=== END DEBUG ===\n")
    
    # TEMPORARY: Always return True to see the webhook data
    return True



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