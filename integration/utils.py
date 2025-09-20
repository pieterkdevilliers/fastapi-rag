import hashlib
import hmac
from fastapi import HTTPException
from sqlmodel import Session
from sqlmodel.sql.expression import select


SIGNING_SECRET = "12345"


def validate_webhook_signature(signature: str, body: bytes):
    """
    Validate incoming ScoreApp webhook signature.
    """
    print("SECRET: ", SIGNING_SECRET)
    
    # Use raw bytes approach (matches ScoreApp's Python Flask example)
    computed_signature = hmac.new(
        SIGNING_SECRET.encode(), 
        body, 
        hashlib.sha256
    ).hexdigest()

    print("Signature header:", signature)
    print("Computed signature:", computed_signature)
    print("Body bytes length:", len(body))

    if not hmac.compare_digest(signature, computed_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    print("✅ Webhook signature matched")
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