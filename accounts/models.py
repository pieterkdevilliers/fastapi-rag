from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from file_management.models import SourceFile


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
    users: list["User"] = Relationship(back_populates="account")
    source_files: list[SourceFile] = Relationship(back_populates="account")


class UserBase(SQLModel):
    """
    User Model Base
    """
    user_email: str
    user_password: str
    user_account_id: str = Field(foreign_key="account.id")


class User(UserBase, table=True):
    """
    User Model
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    account: Account = Relationship(back_populates="users")
    
