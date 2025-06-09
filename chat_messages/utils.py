from sqlmodel import select, Session
from chat_messages.models import ChatSession
from typing import Optional


def create_or_identify_chat_session(account_unique_id: str, session: Session):
    """
    Create or Identify Chat Session
    """
    chat_session = session.exec(
        select(ChatSession).where(ChatSession.account_unique_id == account_unique_id)
    ).first()

    if not chat_session:
        chat_session = ChatSession(account_unique_id=account_unique_id)
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)

    return chat_session