from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy import Column
from sqlalchemy.sql.sqltypes import JSON
from sqlmodel import SQLModel, Field, Relationship
from file_management.models import SourceFile, Folder
# Conditional import for type checking
if TYPE_CHECKING:
    from chat_messages.models import ChatSession


class AccountBase(SQLModel):
    """
    User Account Model Base
    """
    account_organisation: str
    account_unique_id: str = Field(unique=True)


class Account(AccountBase, table=True):
    """
    User Account Model
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    users: List["User"] = Relationship(back_populates="account")
    folders: List["Folder"] = Relationship(back_populates="account")
    source_files: List["SourceFile"] = Relationship(back_populates="account")
    widget_api_keys: List["WidgetAPIKey"] = Relationship(back_populates="account")
    chat_sessions: List["ChatSession"] = Relationship(back_populates="account")
    stripe_subscription: Optional["StripeSubscription"] = Relationship(
        back_populates="account",
        sa_relationship_kwargs={"uselist": False}
    )
    relevance_score: float = Field(default=0.7, nullable=True)
    k_value: int = Field(default=3, nullable=True)
    chunk_size: int = Field(default=1000, nullable=True)
    chunk_overlap: int = Field(default=500, nullable=True)
    webhook_url: str = Field(default=None, nullable=True)


class UserBase(SQLModel):
    """
    User Model Base
    """
    user_email: str
    user_password: str
    account_unique_id: str = Field(foreign_key="account.account_unique_id")


class User(UserBase, table=True):
    """
    User Model
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    account: Account = Relationship(back_populates="users")
    receive_notifications: bool = Field(default=False, nullable=True)

class WidgetAPIKeyBase(SQLModel):
    """
    WidgetAPIKey Model Base
    """
    account_unique_id: str = Field(
        foreign_key="account.account_unique_id",
        index=True
    )
    name: Optional[str] = Field(default=None, nullable=True)
    display_prefix: Optional[str] = Field(default=None, nullable=True, index=True)


class WidgetAPIKey(WidgetAPIKeyBase, table=True):
    """
    WidgetAPIKey Model
    """
    __tablename__ = "widgetapikey"

    id: Optional[int] = Field(default=None, primary_key=True)
    api_key_hash: str = Field(
        unique=True,
        index=True,
        description="Hash of the full API key."
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: Optional[datetime] = Field(default=None, nullable=True)
    is_active: bool = Field(default=True)
    allowed_origins: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON), # Explicitly use SQLAlchemy's JSON type
        description="List of allowed HTTP origins. Empty list or ['*'] means allow all."
    )

    account: "Account" = Relationship(back_populates="widget_api_keys")


class StripeSubscriptionBase(SQLModel):
    """
    Stripe Subscription Model Base
    """
    account_unique_id: Optional[str] = Field(
        default=None, 
        foreign_key="account.account_unique_id",
        nullable=True
    )
    stripe_subscription_id: str = Field(unique=True, index=True)
    stripe_customer_id: str = Field(unique=True, index=True)
    status: str = Field(default="active", nullable=True)
    current_period_end: Optional[datetime] = Field(
        default=None, 
        nullable=True
    ) 


class StripeSubscription(StripeSubscriptionBase, table=True):
    """
    Stripe Subscription Model
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    account: Optional[Account] = Relationship(back_populates="stripe_subscription")
    type: Optional[str] = Field(default=None, nullable=True, index=True)
    trial_start: Optional[datetime] = Field(default=None, nullable=True)
    trial_end: Optional[datetime] = Field(default=None, nullable=True)
    subscription_start: Optional[datetime] = Field(default=None, nullable=True)
    stripe_account_url: Optional[str] = Field(default=None, nullable=True, index=True)
    related_product_title: Optional[str] = Field(default=None, nullable=True)

    def __repr__(self):
        return f"<StripeSubscription(id={self.id}, stripe_subscription_id={self.stripe_subscription_id}, status={self.status})>"