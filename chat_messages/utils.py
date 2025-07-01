from sqlmodel import select, Session, func
from chat_messages.models import ChatSession, ChatMessage
from accounts.models import Account
from typing import Optional
from datetime import datetime, timezone, timedelta


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

def get_session_id_by_visitor_uuid(account_unique_id: str, visitor_uuid: str, session: Session) -> Optional[int]:
    """
    Get Chat Session ID by Visitor UUID
    """
    chat_session = session.exec(
        select(ChatSession.id).where(ChatSession.visitor_uuid == visitor_uuid, ChatSession.account_unique_id == account_unique_id)
    ).first()
    
    return chat_session if chat_session else None


def get_chat_messages_by_session_id(chat_session_id: int, session: Session) -> list[ChatMessage]:
    """
    Get Chat Messages by Session ID
    """
    chat_messages = session.exec(
        select(ChatMessage).where(ChatMessage.chat_session_id == chat_session_id)
    ).all()
    if not chat_messages:
        return []
    
    chat_messages.sort(key=lambda x: x.timestamp)  # Sort messages by timestamp
    print('chat_messages:', chat_messages)
    return chat_messages


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


def get_chat_session_count(account_unique_id: str, session: Session):
    """
    Returns the number of chat sessions for the account in the last 30 days
    """
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    statement = select(func.count()).where(
            ChatSession.account_unique_id == account_unique_id,
            ChatSession.start_time >= thirty_days_ago
        )
    
    chat_session_count = session.exec(statement).one()

    return chat_session_count


def get_questions_answered_count(account_unique_id: str, session: Session):
    """
    Returns the number of questions answered for the account in the last 30 days.
    This is done in a single, efficient database query.
    """
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # Build a single statement that joins the tables
    statement = select(func.count(ChatMessage.id)).join(ChatSession).where(
        # Filter on the ChatSession table
        ChatSession.account_unique_id == account_unique_id,
        
        # Filter on the ChatMessage table
        ChatMessage.timestamp >= thirty_days_ago,
        ChatMessage.sender_type == 'user'
    )
    
    # Execute the single query and get the final integer count
    questions_answered_count = session.exec(statement).one()

    return questions_answered_count