from sqlmodel import select, Session
from chat_messages.models import ChatSession, ChatMessage
from accounts.models import Account
from typing import Optional
from datetime import datetime, timezone


def create_or_identify_chat_session(account_unique_id: str, visitor_uuid: str, session: Session):
    """
    Create or Identify Chat Session
    """
    chat_session = session.exec(
        select(ChatSession).where(ChatSession.account_unique_id == account_unique_id, ChatSession.visitor_uuid == visitor_uuid)
    ).first()

    if not chat_session:
        chat_session = ChatSession(account_unique_id=account_unique_id, visitor_uuid=visitor_uuid)
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


def create_chat_message(chat_session_id: int, message_text: str, sender_type: str, session: Session) -> Optional[ChatSession]:
    """
    Create a new chat message in the session
    """
    chat_message = ChatMessage(
        chat_session_id=chat_session_id,
        message_text=message_text,
        sender_type=sender_type,
        timestamp=datetime.now(timezone.utc)
    )
    
    session.add(chat_message)
    session.commit()
    session.refresh(chat_message)

    # Optionally return the updated chat session
    return chat_message