from typing import Optional
from sqlmodel import SQLModel, Field, Relationship

class SourceFile(SQLModel, table=True):
    """
    DB Table for Source Files - Not the generated / chunked documents
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    file_name: str
    file_path: str
    included_in_source_data: bool = Field(default=False, nullable=True)
    account_unique_id: str = Field(default=None, foreign_key="account.account_unique_id")
    account: "Account" = Relationship(back_populates="source_files")

from accounts.models import Account
