import hashlib
import hmac
import base64
from fastapi import HTTPException
from secrets import token_hex
from sqlmodel import Session
from sqlmodel.sql.expression import select


SIGNING_SECRET = "12345"

async def validate_webhook_signature(signature, body):
    """
    validate the incoming webhook signature - ScoreApp
    """
    print("Raw body bytes:", body)
    print("Raw body str:", body.decode("utf-8", errors="ignore"))
        # Compute signature
    computed_signature = hmac.new(
        SIGNING_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    computed_base64 = base64.b64encode(computed_base64).decode()

    print("Signature from header: ", signature)
    print("Computed hex:        ", computed_signature)
    print("Computed base64:     ", computed_base64)

    print("signature: ", signature)
    print("Conputed Signature: ", computed_signature)
    # Compare securely
    if not hmac.compare_digest(signature, computed_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Compare securely
    if hmac.compare_digest(signature, computed_signature):
        print("✅ Matched using hex")
    elif hmac.compare_digest(signature, computed_base64):
        print("✅ Matched using base64")
    else:
        raise HTTPException(status_code=401, detail="Invalid signature")
    
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