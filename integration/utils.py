import hashlib
import hmac
import base64
from fastapi import HTTPException
from sqlmodel import Session
from sqlmodel.sql.expression import select


SIGNING_SECRET = "12345"

def validate_webhook_signature(signature: str, body_bytes: bytes):
    """
    Validate ScoreApp webhook signature.
    """
    # Compute HMAC digest (raw bytes)
    digest = hmac.new(SIGNING_SECRET.encode(), body_bytes, hashlib.sha256).digest()

    # Hex string (lowercase) of the digest
    computed_hex = digest.hex()

    print("Signature header:", signature)
    print("Computed hex:", computed_hex)

    if not hmac.compare_digest(signature, computed_hex):
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