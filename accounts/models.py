from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class AccountBase(SQLModel):
    """
    User Account Model Base
    """
    account_organisation: str
    account_unique_id: str


class Account(AccountBase, table=True):
    """
    User Account Model
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    users: List["User"] = Relationship(back_populates="account")
    source_files: List["SourceFile"] = Relationship(back_populates="account")
    relevance_score: float = Field(default=0.7, nullable=True)
    k_value: int = Field(default=3, nullable=True)

from file_management.models import SourceFile


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
