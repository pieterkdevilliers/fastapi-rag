from sqlmodel import SQLModel, Field
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

class ProductBase(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_title: str

class Product(ProductBase, table=True):
    """
    Product Model
    """
    __tablename__ = "product"
    
    product_id: str = Field(default="", index=True, unique=True)
    product_description: str = Field(default="")
    product_statement_descriptor: str = Field(default="")
    product_price: float = Field(default=0.0)
    product_plan_cycle: str = Field(default="")
    price_id: Optional[str] = Field(default=None, index=True, nullable=True, unique=True)


class PasswordResetTokenBase(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)

class PasswordResetToken(PasswordResetTokenBase, table=True):
    __tablename__ = "passwordresettoken"

    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    token: str = Field(unique=True,  index=True, nullable=False)
    expires_at: Optional[datetime] = Field(default=None)

    def is_expired(self):
        return datetime.now() > self.expires_at


# --- The Single Source of Truth for the Contact Payload ---
class ContactPayload(BaseModel):
    name: str
    email: str
    message: str
    sessionId: int
    visitorUuid: str

# --- Models for the Webhook ---
class WebhookChatMessage(BaseModel):
    timestamp: datetime
    sender_type: str
    message_text: str

class WebhookData(BaseModel):
    contact_info: ContactPayload # Use the shared model here
    transcript: Optional[List[WebhookChatMessage]] = None
    account_unique_id: str