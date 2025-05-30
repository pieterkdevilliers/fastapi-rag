from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import Column
from sqlalchemy.sql.sqltypes import JSON
from sqlmodel import SQLModel, Field, Relationship
from file_management.models import SourceFile, Folder


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
    relevance_score: float = Field(default=0.7, nullable=True)
    k_value: int = Field(default=3, nullable=True)
    chunk_size: int = Field(default=1000, nullable=True)
    chunk_overlap: int = Field(default=500, nullable=True)


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