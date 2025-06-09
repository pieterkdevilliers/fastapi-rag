from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship
import uuid
# Conditional import for type checking
if TYPE_CHECKING:
    from accounts.models import Account

class ChatSessionBase(SQLModel):
    """
    Chat Session Model Base
    """
    account_unique_id: str = Field(foreign_key="account.account_unique_id")


class ChatSession(ChatSessionBase, table=True):
    """
    Chat Session Model
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    account: "Account" = Relationship(back_populates="chat_sessions")
    visitor_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = Field(default=None, nullable=True)


class ChatMessageBase(SQLModel):
    """
    Chat Message Model Base
    """
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    chat_session_id: int = Field(foreign_key="chatsession.id")


class ChatMessage(ChatMessageBase, table=True):
    """
    Chat Message Model
    """
    sender_type: str = Field(default="user", nullable=False)  # 'user' or 'bot'
    message_text: str = Field(nullable=False)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
