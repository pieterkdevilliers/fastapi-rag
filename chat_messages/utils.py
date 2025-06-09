from sqlmodel import select, Session
from chat_messages.models import ChatSession
from accounts.models import Account
from typing import Optional
from datetime import datetime, timezone


def create_or_identify_chat_session(account_unique_id: str, session: Session):
    """
    Create or Identify Chat Session
    """
    chat_session = session.exec(
        select(ChatSession).where(ChatSession.account_unique_id == account_unique_id)
    ).first()

    if not chat_session:
        chat_session = ChatSession(account_unique_id=account_unique_id)
        chat_session.account = session.exec(
            select(Account).where(Account.account_unique_id == account_unique_id)
        ).first().account_organisation
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
    else:
        # Optionally, you can update the session's end time if needed
        chat_session.end_time = datetime.now(timezone.utc)
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)

    return chat_session