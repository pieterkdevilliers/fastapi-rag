import hashlib
import hmac
import base64
from fastapi import HTTPException
from sqlmodel import Session
from sqlmodel.sql.expression import select


SIGNING_SECRET = "12345"

def validate_webhook_signature(signature: str, body_bytes: bytes):
    """
    Validate the incoming webhook signature - ScoreApp
    """
    # Compute hex digest
    computed_hex = hmac.new(
        SIGNING_SECRET.encode(),
        body_bytes,
        hashlib.sha256
    ).hexdigest()

    # Compute base64 digest (some platforms send base64 instead)
    computed_base64 = base64.b64encode(
        hmac.new(SIGNING_SECRET.encode(), body_bytes, hashlib.sha256).digest()
    ).decode()

    print("Signature from header: ", signature)
    print("Computed hex:        ", computed_hex)
    print("Computed base64:     ", computed_base64)

    if not (hmac.compare_digest(signature, computed_hex) or
            hmac.compare_digest(signature, computed_base64)):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    print("✅ Webhook signature matched")


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